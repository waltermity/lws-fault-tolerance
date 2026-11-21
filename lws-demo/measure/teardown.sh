#!/usr/bin/env bash
# Removes the measurement-only objects and returns the cluster to the plain demo state
# (LWS "lws-sim" with 2 replicas + the plain StatefulSet baseline + loadgen).
set -euo pipefail
cd "$(dirname "$0")/.."
NS=lws-demo
kubectl delete -f chaos/kubethanos/kubethanos.yaml --ignore-not-found >/dev/null
kubectl delete -f measure/manifests/prober.yaml --ignore-not-found
kubectl delete -f measure/manifests/baseline-liveness.yaml --ignore-not-found
kubectl -n $NS delete lws lws-one --ignore-not-found
kubectl -n $NS delete svc lws-one-api --ignore-not-found
kubectl apply -f manifests/ >/dev/null
kubectl -n $NS delete pod -l app=baseline --wait=false >/dev/null     # fresh baseline group
echo ">> waiting for the 9 demo pods"
until [ "$(kubectl -n $NS get pods -l chaos-target=true --no-headers 2>/dev/null | wc -l)" -eq 9 ] &&
      [ "$(kubectl -n $NS get pods -l chaos-target=true --no-headers 2>/dev/null | grep -c -E '(1/1|2/2) +Running')" -eq 9 ]; do sleep 2; done
./scripts/status.sh
