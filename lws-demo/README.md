# LeaderWorkerSet demo with the llm-d inference simulator

This demo shows why **LeaderWorkerSet (LWS)** exists. Large models are sharded across
several pods (multi-host inference), and those pods only work **as a unit**. If one
member dies, the survivors are useless until the whole group restarts. LWS manages the
group as a unit. Two hand-rolled StatefulSets do not.

## What is deployed

| Name | What | Pods |
|---|---|---|
| `lws-sim` (LeaderWorkerSet) | 2 replicas × group size 3 (1 leader + 2 workers) | `lws-sim-0`, `lws-sim-0-1`, `lws-sim-0-2`, `lws-sim-1`, … |
| `baseline-leader` + `baseline-worker` (2 StatefulSets) | same group by hand: 1 leader + 2 workers | `baseline-leader-0`, `baseline-worker-0/1` |
| `loadgen` | 1 request per second to both APIs, prints running availability | |
| `kubethanos` (started separately) | deletes 25 % of the target pods at random every 60 s | |

Each **leader** pod runs:
* `sim`: the [llm-d inference simulator](https://github.com/llm-d/llm-d-inference-sim)
  (`ghcr.io/llm-d/llm-d-inference-sim:v1.2.0`). This is the OpenAI-compatible API, the
  "rank 0" of the model.
* `agent`: the *group-agent* ([manifests/01-group-agent.yaml](manifests/01-group-agent.yaml)).

Each **worker** pod runs only the `agent`. Workers stand in for the model shards on the
other hosts.

### Why the group-agent?

The simulator is a single process. It cannot really be sharded, so the group-agent
reproduces the one property of multi-host inference that matters here. 

1. Leader and workers **form a group** at start-up. The leader serves traffic only when
   every worker has joined *it*.
2. If **any member dies or restarts**, the group is broken for the survivors, and they
   **cannot repair it in place**. The leader turns NotReady and makes the simulator return
   HTTP 503 (through the simulator's `/admin/config` failure injection). The workers turn
   NotReady.
3. Only **recreating the whole group** brings the service back.

Inspect any member's state with
`kubectl -n lws-demo exec <pod> -c agent -- cat /www/status`, or run `./scripts/status.sh`.

## Requirements

* Docker, `kubectl`, and `kind`
* Internet access, to pull the LWS manifests and the images

## Run it

```bash
./scripts/setup.sh
```

This creates the kind cluster (1 control-plane + 3 worker nodes), installs LWS v1.0.0,
builds kubethanos, and deploys everything. Then open three terminals:

```bash
kubectl -n lws-demo logs -f deploy/loadgen        # T1: live availability
./scripts/status.sh -w                            # T2: group members + agent state
kubectl -n lws-demo get pods -o wide -w           # T3: raw pod events
```

## Demo script

### 0. LWS basics (the "working principle")

```bash
kubectl -n lws-demo get lws lws-sim
kubectl -n lws-demo get sts,svc                    # LWS created: leader STS + one worker STS per group + headless svc
kubectl -n lws-demo get pods -L leaderworkerset.sigs.k8s.io/group-index,leaderworkerset.sigs.k8s.io/worker-index
kubectl -n lws-demo exec lws-sim-0-1 -- env | grep LWS_   # discovery handed to every pod
./scripts/status.sh                                # each group is on its own node (exclusive-topology)
```

Things to point out:

* One object describes "N copies of a model that needs M pods". LWS expands it into a
  leader StatefulSet plus one worker StatefulSet per group.
* Pods get stable names and DNS (`lws-sim-<group>-<index>`) and the env vars
  `LWS_LEADER_ADDRESS`, `LWS_GROUP_SIZE`, and `LWS_WORKER_INDEX`. The agent uses these to
  find its peers, with no hard-coded addresses.
* Placement is group-aware. Because of the `exclusive-topology` annotation, the 3 pods of
  a group always share one node, and two groups never share a node. In a real cluster this
  means one rack or NVLink domain per model instance.

### 1. Kill a worker: the core difference

```bash
./scripts/kill.sh baseline worker
./scripts/kill.sh lws worker
```

* **Baseline.** The StatefulSet replaces just `baseline-worker-0`. The leader notices that
  its shard restarted and goes `broken`. The other worker goes `broken` too. `loadgen`
  shows `FAIL` **forever**. Kubernetes thinks it did its job, because the pod is back,
  but the model is dead.
* **LWS.** `restartPolicy: RecreateGroupOnPodRestart` deletes the **whole group**
  (`lws-sim-0`, `-0-1`, `-0-2`), recreates it, and the group re-forms in a few seconds.
  Meanwhile `lws-sim-1` keeps serving, so `loadgen` barely notices.

### 2. Kill a leader

```bash
./scripts/reset-baseline.sh        # first bring the baseline back (manual, whole group!)
./scripts/kill.sh baseline leader
./scripts/kill.sh lws leader
```

* **Baseline.** A fresh leader comes up, but the old workers are still bound to the dead
  leader. The new leader waits for them forever (`waiting:baseline-worker-0:broken`).
* **LWS.** Same as before: the group is recreated as one unit.

`reset-baseline.sh` is the manual operator fix (delete all pods of the group). This is
exactly what LWS automates.

### 3. Random chaos with kubethanos

```bash
./scripts/reset-baseline.sh
kubectl apply -f chaos/kubethanos/kubethanos.yaml
kubectl -n lws-demo logs -f deploy/kubethanos
```

Every 60 s, kubethanos kills 2 random pods out of the 9 target pods. Let it run for a few
minutes and compare the availability percentages in `loadgen`. Stop it with
`kubectl delete -f chaos/kubethanos/kubethanos.yaml`.

If kubethanos gives you trouble, use the fallback, which does the same thing with plain
`kubectl`:

```bash
./chaos/random-pod-killer.sh 30 1
```

### 4. Optional extras (more LWS benefits)

```bash
# Scale = add whole model instances. A 3rd group goes to the 3rd node.
kubectl -n lws-demo scale lws lws-sim --replicas=3
# A 4th group stays Pending: there is no free node (exclusive placement).
kubectl -n lws-demo scale lws lws-sim --replicas=4
kubectl -n lws-demo scale lws lws-sim --replicas=2

# Rolling update group by group (maxUnavailable: 1). Change the simulated latency:
kubectl -n lws-demo patch lws lws-sim --type=json -p \
  '[{"op":"replace","path":"/spec/leaderWorkerTemplate/leaderTemplate/spec/containers/0/args/3","value":"--time-to-first-token=50ms"}]'
```

## Measurements (used in the report)

The `measure/` folder holds the tooling behind the numbers and charts of the report.
It deploys four systems side by side and measures them with a prober that sends 5
requests per second to every Service.

| Name | System | Objects |
|---|---|---|
| LWS×1 | LeaderWorkerSet, 1 replica | `lws-one` (generated from `manifests/10-lws.yaml`) |
| LWS×2 | LeaderWorkerSet, 2 replicas | `lws-sim` |
| STS | two plain StatefulSets | `baseline-*` |
| STS+LP | two StatefulSets + liveness probes | `baseline-lp-*` (`measure/manifests/baseline-liveness.yaml`) |

The full replication guide, including the evaluation and the figures, is in
[../README.md](../README.md). 

## Clean up

```bash
./scripts/teardown.sh
```

## Files

```
cluster/kind-config.yaml            kind cluster, 1 control-plane + 3 workers
manifests/00-namespace.yaml
manifests/01-group-agent.yaml       group-agent script (ConfigMap)
manifests/10-lws.yaml               LeaderWorkerSet + client Service
manifests/20-baseline-statefulsets.yaml   leader STS + worker STS + Services
manifests/30-loadgen.yaml           availability probe
chaos/kubethanos/Dockerfile         builds kubethanos (no upstream image; upstream Dockerfile is broken)
chaos/kubethanos/kubethanos.yaml    SA + RBAC + Deployment
chaos/random-pod-killer.sh          fallback chaos tool
scripts/setup.sh | status.sh | kill.sh | reset-baseline.sh | teardown.sh
measure/setup.sh | run-all.sh | chaos.sh | teardown.sh   measurement campaign
measure/recovery.py                 single-fault recovery-time test
measure/rolling_update.py           rolling-update check (duration, failed requests)
measure/analyze.py                  evaluation + charts (needs matplotlib)
measure/manifests/                  prober and the StatefulSet + liveness-probe variant
results/                            raw data and summary.json of the last campaign
```

## Notes on kubethanos

* The upstream repo is unmaintained (last commits around 2019) and publishes no image.
  Its Dockerfile runs `go run main.go` during the build, which needs a cluster, and it
  hard-codes `amd64`. `chaos/kubethanos/Dockerfile` builds the pinned commit
  `e3f8f07` for the host architecture instead.
* The Dockerfile also patches one line. Since K8s 1.20 the API server no longer fills
  `metadata.selfLink`, so unpatched kubethanos logs `selfLink was empty` after every kill.
  The pod is still deleted, but the "killed by kubethanos" Event is lost. With the patch the
  events show up:
  `kubectl -n lws-demo get events --field-selector reason=killing`.
* It filters by **pod-name substring** (`--included-pod-names`), not by label.
* It kills `floor(ratio × matching pods)` pods every `--interval`, starting immediately.

## Reading the loadgen output

* `200` means served. `503` means the leader is up but its group is broken (simulator
  failure injection). `000` means the Service has **no Ready leader** at all (connection
  refused or timeout).
* Availability % is counted from each target's first successful answer, so start-up time
  is not counted as downtime.

## Sample run (kind, LWS v1.0.0)

| Test | Baseline (2 StatefulSets) | LWS |
|---|---|---|
| Kill a worker | leader `broken`, stays down (HTTP 503 → 000) | group 0 fully recreated, 0 failed requests |
| Kill the leader | new leader stuck `forming`, workers `broken` | group recreated, 0 failed requests |
| kubethanos, 4 min, 8 random kills | **9 %** availability (broken by the 1st kill, never recovered) | **99 %** availability |
| Scale to 4 groups | n/a | groups 0–2 each on their own node, group 3 `Pending` |
| Rolling update | n/a | group 1 replaced, then group 0; service stayed up |
