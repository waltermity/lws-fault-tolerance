#!/usr/bin/env bash
# Creates the kind cluster, installs LeaderWorkerSet, builds/loads images and
# deploys both the LWS and the baseline StatefulSet version + load generator.
set -euo pipefail
cd "$(dirname "$0")/.."

LWS_VERSION=${LWS_VERSION:-v1.0.0}
SIM_IMAGE=ghcr.io/llm-d/llm-d-inference-sim:v1.2.0
CLUSTER=lws-demo

if ! kind get clusters | grep -qx "$CLUSTER"; then
  kind create cluster --config cluster/kind-config.yaml
fi
kubectl config use-context "kind-$CLUSTER"

echo ">> installing LeaderWorkerSet $LWS_VERSION"
kubectl apply --server-side -f "https://github.com/kubernetes-sigs/lws/releases/download/$LWS_VERSION/manifests.yaml"
kubectl -n lws-system wait deploy --all --for=condition=Available --timeout=180s

echo ">> pre-loading images into the kind nodes (faster restarts during the demo)"
# best effort: if `kind load` fails (multi-arch images + Docker's containerd store),
# the nodes simply pull the images from the registry themselves.
for img in "$SIM_IMAGE" busybox:1.36 curlimages/curl:8.11.1; do
  docker pull -q "$img" >/dev/null
  kind load docker-image "$img" --name "$CLUSTER" || echo "   (preload of $img failed, nodes will pull it)"
done

echo ">> building kubethanos"
docker build -q -t kubethanos:local chaos/kubethanos >/dev/null
kind load docker-image kubethanos:local --name "$CLUSTER"

echo ">> deploying the demo"
kubectl apply -f manifests/00-namespace.yaml
# retry: the LWS admission webhook can need a few seconds after the controller is up
until kubectl apply -f manifests/; do echo "   retrying in 5s..."; sleep 5; done
echo ">> waiting for all 9 group pods (2 LWS groups x 3 + 1 baseline group x 3)"
until [ "$(kubectl -n lws-demo get pods -l chaos-target=true --no-headers 2>/dev/null | wc -l)" -ge 9 ]; do sleep 2; done
kubectl -n lws-demo wait pods -l chaos-target=true --for=condition=Ready --timeout=300s
./scripts/status.sh
echo
echo "Ready. Next:  kubectl -n lws-demo logs -f deploy/loadgen"
