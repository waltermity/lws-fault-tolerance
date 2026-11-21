#!/usr/bin/env bash
# The manual "fix" an operator has to do for the baseline: restart every pod of the
# group at once (this is exactly what LWS does automatically).
set -euo pipefail
kubectl -n "${NS:-lws-demo}" delete pod -l app=baseline --wait=false
