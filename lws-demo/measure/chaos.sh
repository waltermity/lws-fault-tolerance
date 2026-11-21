#!/usr/bin/env bash
# Random-failure run: kubethanos deletes ~15 % of the 15 group pods (2 pods) every 30 s.
#   ./measure/chaos.sh [duration_seconds=900]
set -euo pipefail
cd "$(dirname "$0")/.."
NS=lws-demo; DUR=${1:-900}; R=${RESULTS_DIR:-results}
mkdir -p "$R"

kubectl -n $NS wait pods -l chaos-target=true --for=condition=Ready --timeout=300s >/dev/null
sleep 20
date +%s > "$R/chaos_start"
sed -e 's/--included-pod-names=.*/--included-pod-names=lws-,baseline-/' \
    -e 's/--interval=.*/--interval=30s/' -e 's/--ratio=.*/--ratio=0.15/' \
    chaos/kubethanos/kubethanos.yaml | kubectl apply -f - >/dev/null
sleep "$DUR"
kubectl -n $NS logs deploy/kubethanos > "$R/kubethanos.log"
kubectl delete -f chaos/kubethanos/kubethanos.yaml >/dev/null
date +%s > "$R/chaos_end"
sleep 90                                               # observe the recovery after the last kill
kubectl -n $NS get pods -l chaos-target=true -o wide > "$R/pods_after_chaos.txt"
./scripts/status.sh > "$R/status_after_chaos.txt"
