#!/usr/bin/env python3
"""Evaluates the measurement campaign and draws the result charts.

Reads   recovery.csv, prober.csv, kubethanos.log and clock_offset_s from $RESULTS_DIR (default: results/)
Writes  summary.json there, and the two charts into --figdir (default: $RESULTS_DIR/figures)

Needs matplotlib:  python3 -m venv .venv && .venv/bin/pip install matplotlib
"""
import argparse, collections, csv, datetime, json, os, re, statistics

HERE = os.path.dirname(os.path.abspath(__file__))
RES = os.path.join(HERE, "..", os.environ.get("RESULTS_DIR", "results"))
INTERVAL = 0.2                                      # prober period [s]
# name in recovery.csv -> prober target
PROBE_OF = {"lws": "lws1", "sts-lp": "stslp", "sts": "sts"}
# prober target -> (label, pod-name prefix used to attribute kubethanos kills)
SYSTEMS = collections.OrderedDict([
    ("sts",   ("STS",    "baseline-")),
    ("stslp", ("STS+LP", "baseline-lp-")),
    ("lws1",  ("LWS×1",  "lws-one-")),
    ("lws2",  ("LWS×2",  "lws-sim-")),
])
INK, INK2, MUTED, GRID, AXIS = "#0b0b0b", "#52514e", "#898781", "#e1e0d9", "#c3c2b7"
COLOR = {"lws": "#2a78d6", "sts-lp": "#eb6834", "sts": "#1baf7a"}      # categorical slots 1-3
OK, FAIL = "#e1e0d9", "#d03b3b"                                          # neutral track, status "critical"


def load_probes():
    by = collections.defaultdict(list)
    with open(os.path.join(RES, "prober.csv")) as f:
        for row in csv.reader(f):
            if len(row) == 4 and row[0].isdigit():
                by[row[1]].append((int(row[0]) / 1000.0, int(row[2])))
    for v in by.values():
        v.sort()
    return by


def outages(samples):
    """[(start, end)] of consecutive failed probes."""
    out, start, last = [], None, None
    for t, code in samples:
        if code != 200:
            start = t if start is None else start
            last = t
        elif start is not None:
            out.append((start, last + INTERVAL)); start = None
    if start is not None:
        out.append((start, last + INTERVAL))
    return out


def recovery(probes, offset):
    rows = list(csv.DictReader(open(os.path.join(RES, "recovery.csv"))))
    res = collections.OrderedDict()
    for system in ("lws", "sts-lp", "sts"):
        for fault in ("worker", "leader"):
            rs = [r for r in rows if r["system"] == system and r["fault"] == fault]
            if not rs:
                continue
            rec = [float(r["recovery_s"]) for r in rs if r["recovered"] == "1"]
            reset = [float(r["reset_s"]) for r in rs if r["reset_s"]]
            down = []
            for r in rs:                                         # client-visible downtime of this fault
                t0 = int(r["t_kill_ms"]) / 1000.0 - offset
                t1 = t0 + (float(r["recovery_s"]) if r["recovered"] == "1" else 60) + 0.3
                fails = [1 for t, c in probes.get(PROBE_OF[system], []) if t0 <= t <= t1 and c != 200]
                down.append(len(fails) * INTERVAL)
            st = lambda v: None if not v else {"n": len(v), "mean": round(statistics.mean(v), 2),
                                               "min": round(min(v), 2), "max": round(max(v), 2),
                                               "stdev": round(statistics.stdev(v), 2) if len(v) > 1 else 0.0}
            res[f"{system}/{fault}"] = {"runs": len(rs), "recovered": len(rec), "recovery_s": st(rec),
                                        "client_downtime_s": st(down) if rec else None,
                                        "restarts": sorted({r["restarts"] for r in rs if r["restarts"]}),
                                        "manual_reset_s": st(reset)}
    return res


def chaos(probes):
    kills = []                                                    # (time, pod)
    for line in open(os.path.join(RES, "kubethanos.log")):
        m = re.search(r'time="([^"]+)".*terminating pod.*name=(\S+)', line)
        if m:
            t = datetime.datetime.strptime(m.group(1), "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=datetime.timezone.utc)
            kills.append((t.timestamp(), m.group(2).strip('"')))
    t0 = min(k[0] for k in kills)
    t1 = max(k[0] for k in kills) + 30                            # one full interval after the last round
    res = collections.OrderedDict(start=t0, duration_s=round(t1 - t0), rounds=len({k[0] for k in kills}),
                                  kills=len(kills), systems=collections.OrderedDict())
    for key, (label, _) in SYSTEMS.items():
        mine = [k for k in kills if system_of(k[1]) == key]
        s = [(t, c) for t, c in probes[key] if t0 <= t < t1]
        ok = sum(1 for _, c in s if c == 200)
        outs = outages(s)
        codes = collections.Counter(c for _, c in s)
        res["systems"][key] = {
            "label": label, "pods_killed": len(mine), "leader_kills": sum(1 for k in mine if is_leader(k[1])),
            "requests": len(s), "ok": ok, "availability_pct": round(100.0 * ok / len(s), 2),
            "outages": sum(1 for a, b in outs if b - a >= 1.0),            # shorter ones are single failed probes
            "longest_outage_s": round(max((b - a for a, b in outs), default=0), 1),
            "down_at_end": bool(outs) and outs[-1][1] >= t1 - INTERVAL,
            "downtime_s": round(sum(b - a for a, b in outs), 1),
            "first_kill_s": round(min((k[0] for k in mine), default=t1) - t0, 1),
            "codes": {str(k): v for k, v in sorted(codes.items())},
            "_kills": [round(k[0] - t0, 1) for k in mine], "_outages": [(round(a - t0, 1), round(b - t0, 1)) for a, b in outs],
        }
    return res


def system_of(pod):
    best = max((k for k, (_, p) in SYSTEMS.items() if pod.startswith(p)), key=lambda k: len(SYSTEMS[k][1]))
    return best


def is_leader(pod):
    return "leader" in pod or re.fullmatch(r"lws-(one|sim)-\d+", pod) is not None


# ------------------------------------------------------------------ charts
def style(plt):
    plt.rcParams.update({"font.family": "serif", "font.serif": ["Times New Roman"],
                         "font.size": 9.5, "axes.edgecolor": AXIS, "axes.linewidth": 0.8, "text.color": INK,
                         "axes.labelcolor": INK2, "xtick.color": MUTED, "ytick.color": MUTED,
                         "xtick.labelcolor": INK2, "ytick.labelcolor": INK})


def chart_recovery(rec, path):
    import matplotlib; matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.patches import FancyBboxPatch
    style(plt)
    names = {"lws": "LeaderWorkerSet", "sts-lp": "StatefulSets + liveness probes", "sts": "StatefulSets"}
    fig, ax = plt.subplots(figsize=(7.2, 2.45))
    y, ticks = 0.0, []
    xmax = max(v["recovery_s"]["max"] for v in rec.values() if v["recovery_s"])
    for fault, title in (("worker", "Worker pod deleted"), ("leader", "Leader pod deleted")):
        ax.text(0, y - 0.62, title, fontsize=10, weight="bold", color=INK, va="center")
        for system in ("lws", "sts-lp", "sts"):
            r = rec.get(f"{system}/{fault}")
            if r is None:
                continue
            ticks.append((y, names[system]))
            if r["recovery_s"]:
                s = r["recovery_s"]
                ax.add_patch(FancyBboxPatch((0, y - 0.19), s["mean"], 0.38, boxstyle="round,pad=0,rounding_size=0.12",
                                            fc=COLOR[system], ec="none", mutation_aspect=0.4))
                ax.add_patch(plt.Rectangle((0, y - 0.19), min(1.0, s["mean"]), 0.38, fc=COLOR[system], ec="none"))  # square baseline end
                ax.plot([s["min"], s["max"]], [y, y], color=INK, lw=1.0, solid_capstyle="butt")
                for v in (s["min"], s["max"]):
                    ax.plot([v, v], [y - 0.1, y + 0.1], color=INK, lw=1.0)
                ax.text(s["max"] + 0.6, y, f'{s["mean"]:.1f}s   (min {s["min"]:.1f}, max {s["max"]:.1f}, n = {s["n"]})',
                        va="center", fontsize=9.5, color=INK)
            else:
                ax.plot([0, 0], [y - 0.19, y + 0.19], color=COLOR[system], lw=3, solid_capstyle="butt")
                ax.text(0.6, y, f'no recovery in any of {r["runs"]} runs (observed for 60s each)', va="center", fontsize=9.5, color=INK)
            y += 0.62
        y += 0.75
    ax.set_ylim(y - 0.9, -1.0)
    ax.set_xlim(0, xmax * 1.75)
    ax.set_yticks([t for t, _ in ticks]); ax.set_yticklabels([n for _, n in ticks], fontsize=9.5)
    ax.set_xlabel("Time until the whole group is Ready again [s]")
    ax.xaxis.grid(True, color=GRID, lw=0.8); ax.set_axisbelow(True)
    for s in ("top", "right", "left"):
        ax.spines[s].set_visible(False)
    ax.tick_params(axis="y", length=0)
    fig.tight_layout(pad=0.4)
    fig.savefig(path, dpi=300, facecolor="white"); plt.close(fig)


def chart_chaos(ch, path):
    import matplotlib; matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.lines import Line2D
    from matplotlib.patches import Patch
    style(plt)
    fig, ax = plt.subplots(figsize=(7.2, 2.55))
    dur = ch["duration_s"]
    for i, (key, s) in enumerate(ch["systems"].items()):
        ax.broken_barh([(0, dur)], (i - 0.2, 0.4), facecolors=OK, edgecolor="none")
        ax.broken_barh([(a, max(b - a, 0.8)) for a, b in s["_outages"]], (i - 0.2, 0.4), facecolors=FAIL, edgecolor="none")
        ax.plot(s["_kills"], [i - 0.36] * len(s["_kills"]), linestyle="none", marker="v", ms=4.2, mfc=INK, mec="white", mew=0.5, clip_on=False)
        ax.text(dur + 12, i, f'{s["availability_pct"]:.1f}%', va="center", fontsize=10.5, weight="bold", color=INK)
    ax.text(dur + 12, -0.78, "Availability", va="center", fontsize=9.5, color=INK2)
    ax.set_yticks(range(len(ch["systems"]))); ax.set_yticklabels([s["label"] for s in ch["systems"].values()], fontsize=10.5)
    ax.set_ylim(len(ch["systems"]) - 0.45, -1.0)
    ax.set_xlim(0, dur); ax.set_xticks(range(0, dur + 1, 60))
    ax.set_xlabel("Time since the first kubethanos round [s]")
    for sp in ("top", "right", "left"):
        ax.spines[sp].set_visible(False)
    ax.tick_params(axis="y", length=0)
    ax.legend(handles=[Patch(fc=OK, label="requests succeeded (HTTP 200)"), Patch(fc=FAIL, label="requests failed"),
                       Line2D([], [], linestyle="none", marker="v", ms=4.5, mfc=INK, mec="white", label="pod of this system deleted")],
              loc="upper center", bbox_to_anchor=(0.5, -0.24), ncol=3, frameon=False, fontsize=9.5, handlelength=1.4)
    fig.tight_layout(pad=0.4)
    fig.savefig(path, dpi=300, facecolor="white"); plt.close(fig)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--figdir", default=os.path.join(RES, "figures"))
    a = ap.parse_args()
    os.makedirs(a.figdir, exist_ok=True)
    offset = float(open(os.path.join(RES, "clock_offset_s")).read().strip() or 0)
    probes = load_probes()
    summary = {"clock_offset_s": offset, "recovery": recovery(probes, offset)}
    chart_recovery(summary["recovery"], os.path.join(a.figdir, "fig4_recovery.png"))
    if os.path.exists(os.path.join(RES, "kubethanos.log")):
        summary["chaos"] = chaos(probes)
        chart_chaos(summary["chaos"], os.path.join(a.figdir, "fig5_chaos.png"))
    json.dump(summary, open(os.path.join(RES, "summary.json"), "w"), indent=1)
    slim = json.loads(json.dumps(summary))
    for s in slim.get("chaos", {}).get("systems", {}).values():
        s.pop("_kills"); s.pop("_outages")
    print(json.dumps(slim, indent=1))


if __name__ == "__main__":
    main()
