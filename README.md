# Fault tolerance of LeaderWorkerSet

This repository holds the code and data behind the Project Laboratory 2 report
*Fault Tolerance Evaluation of LeaderWorkerSet for Multi-Host LLM Inference in Kubernetes*:
the test environment, the live demo, the measurement tooling, the raw data and the
figures. This file explains how to reproduce each of them from scratch.

No GPU is needed. Everything runs on one machine in a local `kind` cluster, and the model
server is the llm-d inference simulator.

## What is in this repository

| Path | Content |
|---|---|
| `lws-demo/` | The testbed: cluster config, manifests, chaos tool, scripts. Its own [README](lws-demo/README.md) is the walkthrough of the live demo. |
| `lws-demo/measure/` | Measurement tooling (recovery test, random-failure run, rolling-update check, evaluation). |
| `lws-demo/results/` | Raw data of the campaign of 16 Nov 2026. **The numbers and charts of the report come from here.** |
| `essay/make_diagrams.py` | Draws Figures 1, 2 and 3 of the report. |
| `essay/figures/` | The five figures used in the report. |

## Requirements

- macOS or Linux with Docker (the original run gave Docker 4 CPUs and 8 GB of memory)
- `kubectl`, `kind`, `python3`
- Internet access, to pull the LeaderWorkerSet manifests and the container images
- For the charts: `matplotlib`, and the Times New Roman font (without it matplotlib falls
  back to another serif font)


Versions used in the original run:

| Component | Version |
|---|---|
| Docker | 29.2.1 |
| kind | v0.33.0 |
| Kubernetes (kind node image) | v1.37.0 |
| LeaderWorkerSet controller | v1.0.0 |
| llm-d inference simulator | v1.2.0 (`ghcr.io/llm-d/llm-d-inference-sim`) |
| kubethanos | commit `e3f8f07`, built locally with one patch (see `lws-demo/chaos/kubethanos/Dockerfile`) |
| Python / matplotlib | 3.x / 3.11 |

All commands below are run from the root of the repository. The scripts change into their own directory,
so they can be started from anywhere.

## Step 1: create the environment (about 5 minutes)

```bash
./lws-demo/scripts/setup.sh
```

The script creates the `kind` cluster `lws-demo` (1 control-plane and 3 worker nodes),
installs the LeaderWorkerSet controller, builds the kubethanos image and loads it into the
cluster, and deploys the demo workloads. It ends with a status table in which all 9 pods
are Ready: 6 pods of the LeaderWorkerSet `lws-sim` (2 groups of 3) and 3 pods of the
StatefulSet baseline.


## Step 2 (optional): the live demo and the scaling check

The demo is described step by step in [lws-demo/README.md](lws-demo/README.md).

## Step 3: run the measurements (about 35 minutes)

```bash
RESULTS_DIR=results-rerun ./lws-demo/measure/run-all.sh
```

`RESULTS_DIR` is relative to `lws-demo/`. **Without it the script writes to
`lws-demo/results/` and overwrites the original data of the report.**

What the script does:

1. Deploys four systems side by side (15 pods) and a prober that sends 5 requests per
   second to each of them.

   | Name in the report | Kubernetes objects | Pods |
   |---|---|---|
   | STS | StatefulSets `baseline-leader`, `baseline-worker` | 3 |
   | STS+LP | StatefulSets `baseline-lp-leader`, `baseline-lp-worker`, with liveness probes | 3 |
   | LWS×1 | LeaderWorkerSet `lws-one`, 1 replica | 3 |
   | LWS×2 | LeaderWorkerSet `lws-sim`, 2 replicas | 6 |

2. Single-failure recovery tests: deletes a worker pod, then the leader pod, 10 times each
   for LWS×1 and STS+LP and 3 times each for STS, and measures the time until the group is
   Ready again.
3. Random-failure run: kubethanos deletes 2 random pods every 30 s for 15 minutes.
4. Rolling-update check: changes the leader template of `lws-sim` twice and counts the
   requests that fail during each update.


Files written to the results folder:

| File | Content |
|---|---|
| `recovery.csv` | One line per recovery test: system, fault, kill time, recovery time, container restarts, manual reset time |
| `prober.csv` | Every probe request: time, target, HTTP code (0 = no answer), latency |
| `kubethanos.log` | Which pods kubethanos deleted, and when |
| `pods_after_chaos.txt`, `status_after_chaos.txt` | Pod states and restart counts 90 s after the random-failure run |
| `rolling_update.json` | Duration and failed requests of the two rolling updates |
| `clock_offset_s`, `chaos_start`, `chaos_end` | Timing helpers |

## Step 4: evaluate the data and draw the figures

Create a Python environment once:

```bash
python3 -m venv .venv
```

```bash
.venv/bin/pip install matplotlib
```

Evaluate a new run. This writes `summary.json` into the results folder and draws
`fig4_recovery.png` and `fig5_chaos.png` into the given folder:

```bash
RESULTS_DIR=results-rerun .venv/bin/python lws-demo/measure/analyze.py --figdir essay/figures-rerun
```

To check the report without a cluster, evaluate the original data instead. This
reproduces Figure 4, Figure 5 and `lws-demo/results/summary.json` exactly:

```bash
.venv/bin/python lws-demo/measure/analyze.py --figdir essay/figures
```

Figures 1, 2 and 3 are diagrams and do not depend on any data:

```bash
.venv/bin/python essay/make_diagrams.py
```

## Clean up

Remove the measurement objects and return to the plain demo state:

```bash
./lws-demo/measure/teardown.sh
```

Delete the whole cluster:

```bash
./lws-demo/scripts/teardown.sh
```
