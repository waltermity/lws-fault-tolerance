#!/usr/bin/env bash
# Prepares the cluster for the measurements. Four systems run side by side:
#   lws1   LeaderWorkerSet "lws-one", 1 replica  (1 group of 3 pods)
#   lws2   LeaderWorkerSet "lws-sim", 2 replicas (2 groups of 3 pods)
#   sts    two plain StatefulSets "baseline-*"   (1 group of 3 pods)
#   stslp  two StatefulSets + liveness probes "baseline-lp-*" (1 group of 3 pods)
set -euo pipefail
cd "$(dirname "$0")/.."
NS=lws-demo

kubectl delete -f chaos/kubethanos/kubethanos.yaml --ignore-not-found >/dev/null
kubectl apply -f manifests/                                   # demo objects in their original state
sed -e 's/lws-sim/lws-one/g' -e 's/replicas: 2/replicas: 1/' manifests/10-lws.yaml | kubectl apply -f -
kubectl apply -f measure/manifests/baseline-liveness.yaml
kubectl -n $NS delete pod -l app=baseline --wait=false        # fresh baseline group

echo ">> waiting for both LeaderWorkerSets to be fully rolled out"
for l in lws-sim lws-one; do
  until [ "$(kubectl -n $NS get lws $l -o jsonpath='{.spec.replicas}/{.spec.replicas}')" = \
          "$(kubectl -n $NS get lws $l -o jsonpath='{.status.updatedReplicas}/{.status.readyReplicas}')" ]; do sleep 3; done
done

echo ">> waiting for all 15 group pods"
until [ "$(kubectl -n $NS get pods -l chaos-target=true --no-headers 2>/dev/null | grep -c Running)" -ge 15 ]; do sleep 2; done
sleep 5
kubectl -n $NS wait pods -l chaos-target=true --for=condition=Ready --timeout=300s >/dev/null
kubectl apply -f measure/manifests/prober.yaml
kubectl -n $NS rollout restart deploy/prober >/dev/null
kubectl -n $NS rollout status deploy/prober --timeout=180s
./scripts/status.sh
