#!/usr/bin/env python3
"""Rolling-update check for the two-replica LeaderWorkerSet "lws-sim".

Changes one argument of the leader template twice (200 ms -> 50 ms -> 200 ms time to first
token). Each change triggers a rolling update that replaces the two groups one after the
other. For both updates it records the duration and how many prober requests to lws-sim
failed meanwhile. Needs the measurement setup (the prober must be running).

Writes $RESULTS_DIR/rolling_update.json (default: results/).
"""
import json, os, subprocess, time

NS = "lws-demo"
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", os.environ.get("RESULTS_DIR", "results"),
                   "rolling_update.json")
PATH = "/spec/leaderWorkerTemplate/leaderTemplate/spec/containers/0/args/3"


def k(*args):
    return subprocess.run(["kubectl", "-n", NS, *args], capture_output=True, text=True).stdout


def rolled():
    st = json.loads(k("get", "lws", "lws-sim", "-o", "json")).get("status", {})
    return st.get("replicas") == 2 and st.get("updatedReplicas") == 2 and st.get("readyReplicas") == 2


def leaders():                                   # creation times of the two leader pods
    return k("get", "pods", "lws-sim-0", "lws-sim-1", "-o",
             "jsonpath={range .items[*]}{.metadata.creationTimestamp} {end}").split()


def main():
    results = []
    for value in ("--time-to-first-token=50ms", "--time-to-first-token=200ms"):
        deadline = time.time() + 300
        while not rolled():                      # start from a stable, fully Ready LeaderWorkerSet
            if time.time() > deadline:
                raise SystemExit("lws-sim did not become stable")
            time.sleep(2)
        time.sleep(5)
        before, t0 = leaders(), time.time()
        k("patch", "lws", "lws-sim", "--type=json", "-p",
          json.dumps([{"op": "replace", "path": PATH, "value": value}]))
        time.sleep(3)
        while True:                              # done when both leaders were replaced and are Ready
            now = leaders()
            if rolled() and len(now) == 2 and now[0] != before[0] and now[1] != before[1]:
                break
            time.sleep(1)
        t1 = time.time()
        time.sleep(4)
        rows = [l.split(",") for l in k("logs", "deploy/prober", "--since=180s").splitlines() if ",lws2," in l]
        window = [r for r in rows if t0 <= int(r[0]) / 1000 <= t1 + 3]
        failed = [r for r in window if r[2] != "200"]
        results.append({"change": value, "rollout_s": round(t1 - t0, 1), "requests": len(window), "failed": len(failed)})
        print(results[-1], flush=True)
    with open(OUT, "w") as f:
        json.dump(results, f, indent=1)


if __name__ == "__main__":
    main()
