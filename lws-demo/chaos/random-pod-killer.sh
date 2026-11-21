#!/usr/bin/env bash
# Fallback chaos tool (same idea as kubethanos, no image needed).
# Every INTERVAL seconds deletes COUNT random pods labelled chaos-target=true.
#
#   ./chaos/random-pod-killer.sh                 # 1 pod every 30s, both deployments
#   ./chaos/random-pod-killer.sh 20 2            # 2 pods every 20s
#   SELECTOR='app=lws-sim' ./chaos/random-pod-killer.sh   # only hit the LWS pods
set -euo pipefail
INTERVAL=${1:-30}
COUNT=${2:-1}
NS=${NS:-lws-demo}
SELECTOR=${SELECTOR:-chaos-target=true}

echo "killing $COUNT random pod(s) matching '$SELECTOR' in $NS every ${INTERVAL}s (Ctrl-C to stop)"
while true; do
  victims=$(kubectl -n "$NS" get pods -l "$SELECTOR" \
              --field-selector=status.phase=Running -o name \
            | awk 'BEGIN{srand()} {print rand()"\t"$0}' | sort -n | cut -f2- | head -n "$COUNT")
  for v in $victims; do
    echo "$(date +%H:%M:%S) deleting $v"
    kubectl -n "$NS" delete "$v" --wait=false >/dev/null
  done
  sleep "$INTERVAL"
done
