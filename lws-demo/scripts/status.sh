#!/usr/bin/env bash
# One-shot view of every group member: node, readiness, and the group-agent state.
#   ./scripts/status.sh          # once
#   ./scripts/status.sh -w       # refresh every 2s
NS=${NS:-lws-demo}

show() {
  printf '%-20s %-22s %-6s %s\n' POD NODE READY AGENT-STATUS
  kubectl -n "$NS" get pods -l chaos-target=true --sort-by=.metadata.name \
    -o jsonpath='{range .items[*]}{.metadata.name}{" "}{.spec.nodeName}{" "}{range .status.containerStatuses[*]}{.ready}{","}{end}{"\n"}{end}' |
  while read -r pod node ready; do
    [[ "$ready" == *false* || -z "$ready" ]] && r=no || r=yes
    s=$(kubectl -n "$NS" exec "$pod" -c agent -- cat /www/status 2>/dev/null | sed 's/^role=[a-z]* //')
    printf '%-20s %-22s %-6s %s\n' "$pod" "${node:-<pending>}" "$r" "${s:-<starting>}"
  done
}

if [[ "${1:-}" == "-w" ]]; then
  while true; do out=$(show); clear; date +%H:%M:%S; echo "$out"; sleep 2; done
else
  show
fi
