#!/usr/bin/env python3
"""Single-fault recovery measurement.

Deletes one pod (the leader or a worker) of a healthy 3-pod group and measures how long
it takes until the whole group is Ready again (= group re-formed, leader serving).

  ./measure/recovery.py <lws|sts|sts-lp> <leader|worker> <iterations> [timeout_s]

Appends one CSV line per iteration to $RESULTS_DIR/recovery.csv (default: results/):
  system,fault,iter,t_kill_ms,recovered,recovery_s,restarts,reset_s
  restarts = container restarts in the group at recovery time (liveness-probe restarts)
  reset_s  = duration of the manual "delete every pod of the group" reset that follows
             (sts, sts-lp only; this is also what clears the kubelet restart back-off)
"""
import json, os, subprocess, sys, time

NS = "lws-demo"
SYSTEMS = {
    "lws":    {"leader": "lws-one-0",            "workers": ["lws-one-0-1", "lws-one-0-2"],                     "selector": None},
    "sts":    {"leader": "baseline-leader-0",    "workers": ["baseline-worker-0", "baseline-worker-1"],         "selector": "app=baseline"},
    "sts-lp": {"leader": "baseline-lp-leader-0", "workers": ["baseline-lp-worker-0", "baseline-lp-worker-1"],   "selector": "app=baseline-lp"},
}
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", os.environ.get("RESULTS_DIR", "results"),
                   "recovery.csv")


def kubectl(*args):
    return subprocess.run(["kubectl", "-n", NS, *args], capture_output=True, text=True)


def group(pods):
    """{pod: (uid, ready, restarts)} or None while any pod of the group is missing."""
    r = kubectl("get", "pods", *pods, "-o", "json")
    if r.returncode != 0:
        return None
    out = {}
    for p in json.loads(r.stdout)["items"]:
        cs = p["status"].get("containerStatuses", [])
        ready = bool(cs) and all(c.get("ready") for c in cs) and "deletionTimestamp" not in p["metadata"]
        out[p["metadata"]["name"]] = (p["metadata"]["uid"], ready, sum(c.get("restartCount", 0) for c in cs))
    return out if len(out) == len(pods) else None


def wait_ready(pods, timeout, changed=None):
    """Wait until all pods are Ready (and the uids listed in `changed` were replaced)."""
    t0 = time.time()
    while time.time() - t0 < timeout:
        g = group(pods)
        if g and all(v[1] for v in g.values()) and all(g[p][0] != u for p, u in (changed or {}).items()):
            return time.time() - t0, sum(v[2] for v in g.values())
        time.sleep(0.2)
    return None, None


def main():
    system, fault, n = sys.argv[1], sys.argv[2], int(sys.argv[3])
    timeout = float(sys.argv[4]) if len(sys.argv) > 4 else 120
    s = SYSTEMS[system]
    pods = [s["leader"], *s["workers"]]
    victim = s["leader"] if fault == "leader" else s["workers"][0]
    new = not os.path.exists(OUT)
    with open(OUT, "a", buffering=1) as f:
        if new:
            f.write("system,fault,iter,t_kill_ms,recovered,recovery_s,restarts,reset_s\n")
        for i in range(1, n + 1):
            if wait_ready(pods, 300)[0] is None:
                sys.exit(f"{system}: group never became healthy")
            time.sleep(8)                                   # settle
            old = group(pods)[victim][0]
            t_kill = time.time()
            kubectl("delete", "pod", victim, "--wait=false")
            rec, restarts = wait_ready(pods, timeout, {victim: old})
            reset = ""
            if s["selector"]:                               # manual fix: restart the whole group
                uids = {p: v[0] for p, v in (group(pods) or {}).items()}
                kubectl("delete", "pod", "-l", s["selector"], "--wait=false")
                r, _ = wait_ready(pods, 300, uids)
                reset = f"{r:.2f}" if r is not None else ""
            line = (f"{system},{fault},{i},{int(t_kill * 1000)},{int(rec is not None)},"
                    f"{'' if rec is None else f'{rec:.2f}'},{'' if restarts is None else restarts},{reset}")
            f.write(line + "\n")
            print(line, flush=True)


if __name__ == "__main__":
    main()
