#!/usr/bin/env python3
"""Draws the three explanatory diagrams of the report (Figures 1, 2 and 3)."""
import os
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch, FancyArrowPatch

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "figures")
INK, INK2, MUTED, LINE = "#0b0b0b", "#52514e", "#898781", "#c3c2b7"
LEADER_FC, LEADER_EC = "#cde2fb", "#2a78d6"      # leader pods (blue)
WORKER_FC, WORKER_EC = "#f0efec", "#898781"      # worker pods (neutral)
GROUP_FC = "#fcfcfb"
plt.rcParams.update({"font.family": "serif", "font.serif": ["Times New Roman"], "font.size": 9})
FS = 1.15                                           # Times New Roman runs small: scale every label


def box(ax, x, y, w, h, text="", fc="white", ec=LINE, lw=0.8, fs=8, color=INK, weight="normal",
        va="center", ha="center", pad=0.0, r=0.06, ls="-"):
    ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle=f"round,pad=0,rounding_size={r}", fc=fc, ec=ec, lw=lw, ls=ls))
    if text:
        tx = x + w / 2 if ha == "center" else x + 0.1
        ty = y + h / 2 if va == "center" else y + h - 0.1 - pad
        ax.text(tx, ty, text, ha=ha, va="center" if va == "center" else "top", fontsize=fs, color=color, weight=weight)


def arrow(ax, p, q, color=INK2, lw=0.8, style="-|>"):
    ax.add_patch(FancyArrowPatch(p, q, arrowstyle=style, mutation_scale=7, lw=lw, color=color, shrinkA=0, shrinkB=0))


def canvas(w, h):
    fig, ax = plt.subplots(figsize=(w, h))
    ax.set_xlim(0, w); ax.set_ylim(0, h); ax.axis("off")
    fig.subplots_adjust(0, 0, 1, 1)
    plain_text = ax.text
    ax.text = lambda *a, **k: plain_text(*a, **{**k, "fontsize": k.get("fontsize", 8) * FS})
    return fig, ax


def figure1():
    fig, ax = canvas(7.2, 3.0)
    # ---- left: classic deployment
    ax.text(1.55, 2.82, "Classic deployment: two StatefulSets", ha="center", fontsize=9, weight="bold", color=INK)
    box(ax, 0.15, 1.75, 2.8, 0.82, "StatefulSet  leader", fc=GROUP_FC, va="top", ha="left", color=INK2, fs=7.5)
    box(ax, 1.05, 1.85, 1.0, 0.42, "leader-0", fc=LEADER_FC, ec=LEADER_EC)
    box(ax, 0.15, 0.75, 2.8, 0.82, "StatefulSet  worker", fc=GROUP_FC, va="top", ha="left", color=INK2, fs=7.5)
    box(ax, 0.45, 0.85, 1.0, 0.42, "worker-0", fc=WORKER_FC, ec=WORKER_EC)
    box(ax, 1.65, 0.85, 1.0, 0.42, "worker-1", fc=WORKER_FC, ec=WORKER_EC)
    ax.text(1.55, 0.38, "Kubernetes sees three independent pods.\nA failed pod is replaced alone.",
            ha="center", va="center", fontsize=7.5, color=INK2)
    ax.plot([3.25, 3.25], [0.3, 2.9], color=LINE, lw=0.8)
    # ---- right: LeaderWorkerSet
    ax.text(5.25, 2.82, "LeaderWorkerSet  (replicas: 2, size: 3)", ha="center", fontsize=9, weight="bold", color=INK)
    for g, x0 in enumerate((3.55, 5.4)):
        box(ax, x0, 0.75, 1.7, 1.82, f"Group {g}", fc=GROUP_FC, va="top", ha="left", color=INK2, fs=7.5)
        box(ax, x0 + 0.35, 1.78, 1.0, 0.42, f"lws-{g}", fc=LEADER_FC, ec=LEADER_EC)
        box(ax, x0 + 0.08, 0.88, 0.74, 0.42, f"lws-{g}-1", fc=WORKER_FC, ec=WORKER_EC)
        box(ax, x0 + 0.88, 0.88, 0.74, 0.42, f"lws-{g}-2", fc=WORKER_FC, ec=WORKER_EC)
        arrow(ax, (x0 + 0.45, 1.3), (x0 + 0.7, 1.78), color=MUTED, style="-")
        arrow(ax, (x0 + 1.25, 1.3), (x0 + 1.0, 1.78), color=MUTED, style="-")
    ax.text(5.25, 0.38, "Each group is created, restarted, updated\nand placed as one unit.",
            ha="center", va="center", fontsize=7.5, color=INK2)
    # legend
    box(ax, 0.15, 0.02, 0.22, 0.13, fc=LEADER_FC, ec=LEADER_EC, r=0.03)
    ax.text(0.43, 0.085, "leader pod (serves the API)", va="center", fontsize=7, color=INK2)
    box(ax, 1.75, 0.02, 0.22, 0.13, fc=WORKER_FC, ec=WORKER_EC, r=0.03)
    ax.text(2.03, 0.085, "worker pod (model shard)", va="center", fontsize=7, color=INK2)
    fig.savefig(os.path.join(OUT, "fig2_lws_concept.png"), dpi=300, facecolor="white")


def group(ax, x, y, names):
    """One leader-worker group: leader pod (simulator + agent) and two worker pods (agent)."""
    box(ax, x, y + 0.62, 1.2, 0.62, names[0], fc=LEADER_FC, ec=LEADER_EC, va="top", fs=6.5, color=INK2)
    box(ax, x + 0.06, y + 0.68, 0.6, 0.26, "simulator", fc="white", ec=LEADER_EC, fs=6.5, r=0.03)
    box(ax, x + 0.72, y + 0.68, 0.42, 0.26, "agent", fc="white", ec=LEADER_EC, fs=6.5, r=0.03)
    for i, n in enumerate(names[1:]):
        bx = x + i * 0.62
        box(ax, bx, y, 0.58, 0.5, n, fc=WORKER_FC, ec=WORKER_EC, va="top", fs=6.5, color=INK2)
        box(ax, bx + 0.08, y + 0.05, 0.42, 0.22, "agent", fc="white", ec=WORKER_EC, fs=6.5, r=0.03)


def figure2():
    fig, ax = canvas(7.2, 3.75)
    box(ax, 0.05, 0.05, 7.1, 3.65, fc="white", ec=LINE, r=0.08)
    ax.text(0.25, 3.5, "kind cluster: 1 control-plane + 3 worker nodes, Kubernetes v1.37.0, LeaderWorkerSet controller v1.0.0",
            fontsize=7.5, color=INK2, va="center")
    box(ax, 0.25, 2.95, 6.7, 0.36, "Prober: one chat-completion request to every Service each 200ms (open loop)", fc="#f0efec", ec=MUTED)
    cols = [(0.25, "STS", "baseline-api", [["baseline-leader-0", "worker-0", "worker-1"]]),
            (1.65, "STS+LP", "baseline-lp-api", [["baseline-lp-leader-0", "worker-0", "worker-1"]]),
            (3.05, "LWS×1", "lws-one-api", [["lws-one-0", "0-1", "0-2"]]),
            (4.45, "LWS×2", "lws-sim-api", [["lws-sim-0", "0-1", "0-2"], ["lws-sim-1", "1-1", "1-2"]])]
    for x, label, svc, groups in cols:
        w = 1.2 if len(groups) == 1 else 2.5
        box(ax, x, 2.3, w, 0.34, f"Service  {svc}", fc="white", ec=INK2, fs=7)
        arrow(ax, (x + w / 2, 2.95), (x + w / 2, 2.64))
        ax.text(x + w / 2, 2.13, label, ha="center", va="center", fontsize=8.5, weight="bold", color=INK)
        for g, names in enumerate(groups):
            group(ax, x + g * 1.3, 0.72, names)
            arrow(ax, (x + g * 1.3 + 0.6, 0.56), (x + g * 1.3 + 0.6, 0.72))
    box(ax, 0.25, 0.2, 6.7, 0.36, "kubethanos: deletes 2 randomly chosen pods out of the 15 group pods every 30s", fc="#f0efec", ec=MUTED)
    fig.savefig(os.path.join(OUT, "fig3_testbed.png"), dpi=300, facecolor="white")


def figure_parallel():
    """Pipeline-parallel example: one model split over three pods, and what one lost pod does."""
    fig, ax = canvas(7.2, 2.55)
    RED = "#d03b3b"
    for panel, (x0, title) in enumerate(((0.1, "Healthy group"),
                                         (3.75, "One worker pod lost"))):
        ax.text(x0 + 1.67, 2.32, title, ha="center", fontsize=9, weight="bold", color=INK)
        pods = [("leader pod", "API, layers 1–27"), ("worker pod 1", "layers 28–54"), ("worker pod 2", "layers 55–80")]
        for i, (name, layers) in enumerate(pods):
            x = x0 + i * 1.15
            lost = panel == 1 and i == 1
            fc, ec = (LEADER_FC, LEADER_EC) if i == 0 else (WORKER_FC, WORKER_EC)
            if panel == 1 and not lost:
                fc = "#f7f7f5"
            box(ax, x, 1.05, 1.0, 0.95, "", fc=fc, ec=RED if lost else ec, ls="--" if lost else "-")
            ax.text(x + 0.5, 1.78, name, ha="center", fontsize=7.5, color=INK2)
            ax.text(x + 0.5, 1.47, layers, ha="center", fontsize=7, color=MUTED if lost else INK)
            ax.text(x + 0.5, 1.2, "GPU", ha="center", fontsize=7, color=MUTED)
            if lost:
                ax.plot([x + 0.12, x + 0.88], [1.12, 1.93], color=RED, lw=1.6)
                ax.plot([x + 0.12, x + 0.88], [1.93, 1.12], color=RED, lw=1.6)
        for i in range(2):
            a, b = x0 + i * 1.15 + 1.0, x0 + (i + 1) * 1.15
            arrow(ax, (a, 1.52), (b, 1.52), color=RED if panel == 1 else INK2)
        if panel == 0:
            arrow(ax, (x0 + 3.2, 1.05), (x0 + 3.2, 0.82), color=INK2, style="-")
            ax.plot([x0 + 3.2, x0 + 0.5], [0.82, 0.82], color=INK2, lw=0.8)
            arrow(ax, (x0 + 0.5, 0.82), (x0 + 0.5, 1.05), color=INK2)
            ax.text(x0 + 1.85, 0.6, "every new token travels through all three shards",
                    ha="center", fontsize=7.5, color=INK2)
        else:
            ax.text(x0 + 1.67, 0.75, "no token can be generated; the two surviving pods",
                    ha="center", fontsize=7.5, color=INK2)
            ax.text(x0 + 1.67, 0.55, "still hold their GPUs and wait for a peer that is gone",
                    ha="center", fontsize=7.5, color=INK2)
    ax.plot([3.55, 3.55], [0.45, 2.45], color=LINE, lw=0.8)
    ax.text(3.6, 0.12, "a replacement pod started later is not part of the running group, so all three pods must restart together",
            ha="center", fontsize=7.5, color=INK)
    fig.savefig(os.path.join(OUT, "fig1_parallelism.png"), dpi=300, facecolor="white")


if __name__ == "__main__":
    os.makedirs(OUT, exist_ok=True)
    figure_parallel(); figure1(); figure2()
