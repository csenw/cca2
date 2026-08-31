#!/usr/bin/env bash
# PROVIDED helper - not assessed and should not be submitted.
set -euo pipefail

TOKEN="${1:-$(python3 - <<'PY'
import secrets
print(secrets.token_urlsafe(24))
PY
)}"

kubectl create secret generic jupyter-secret \
  --from-literal=JUPYTER_TOKEN="$TOKEN" \
  --dry-run=client -o yaml | kubectl apply -f -

echo
echo "Jupyter token created. Keep this token private while your cluster is running:"
echo "$TOKEN"
echo
echo "After jupyter-service receives an EXTERNAL-IP, browse to:"
echo "  http://EXTERNAL_IP:8080/lab?token=$TOKEN"
