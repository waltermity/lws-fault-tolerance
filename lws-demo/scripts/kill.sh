#!/usr/bin/env bash
# Deterministic failure injection for the live demo.
#   ./scripts/kill.sh lws leader        # kill the leader of LWS group 0
#   ./scripts/kill.sh lws worker        # kill worker 1 of LWS group 0
#   ./scripts/kill.sh baseline leader
#   ./scripts/kill.sh baseline worker
set -euo pipefail
NS=${NS:-lws-demo}
case "${1:-}/${2:-}" in
  lws/leader)      pod=lws-sim-0 ;;
  lws/worker)      pod=lws-sim-0-1 ;;
  baseline/leader) pod=baseline-leader-0 ;;
  baseline/worker) pod=baseline-worker-0 ;;
  *) echo "usage: $0 <lws|baseline> <leader|worker>"; exit 1 ;;
esac
echo "$(date +%H:%M:%S) deleting pod/$pod"
kubectl -n "$NS" delete pod "$pod" --wait=false
