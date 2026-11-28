#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
cd "$PROJECT_ROOT"

while true; do
  TOKEN=$(python - <<'PY'
import time
from dotenv import dotenv_values
import jwt

values = dotenv_values('.env')
now = int(time.time())
print(jwt.encode({
    'sub': values.get('BOTBINANCE_USER_ID', '1'),
    'email': values.get('BOTBINANCE_EMAIL', 'hbarbetti.ing@gmail.com'),
    'type': 'access',
    'iat': now,
    'exp': now + 3300,
}, values['JWT_SECRET'], algorithm='HS256'))
PY
  )
  BOTBINANCE_TOKEN="$TOKEN" python paper_forward_report.py --intervalo 60 --iteraciones 55
done
