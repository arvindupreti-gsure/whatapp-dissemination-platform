#!/usr/bin/env bash
# WhatsApp Dissemination & Analytics Platform : proof of concept
# Gsure Technologies Private Limited
set -uo pipefail
cd "$(dirname "$0")"

echo
echo "  ================================================================"
echo "    WhatsApp Dissemination & Analytics Platform"
echo "    Proof of concept  |  Gsure Technologies Private Limited"
echo "  ================================================================"
echo

die() { echo; echo "  [X] $*"; echo; exit 1; }

# --------------------------------------------------------------- Python
PY=""
for cand in python3 python py; do
  if command -v "$cand" >/dev/null 2>&1 &&
     "$cand" -c "import sys; raise SystemExit(0 if sys.version_info>=(3,10) else 1)" >/dev/null 2>&1; then
    PY="$cand"; break
  fi
done
[ -n "$PY" ] || die "Python 3.10 or later not found. Tried python3, python, py."
echo "  [1/4] Python $($PY -c 'import sys;print(sys.version.split()[0])') found"
echo

# --------------------------------------------------------- Dependencies
IMPORTS="import fastapi, uvicorn, sqlalchemy, httpx, openpyxl, reportlab, cryptography, multipart"
if $PY -c "$IMPORTS" >/dev/null 2>&1; then
  echo "  [2/4] Dependencies already present"
else
  echo "  [2/4] Installing dependencies, this may take a minute..."
  echo
  $PY -m pip install --disable-pip-version-check -r requirements.txt || true
  echo
  $PY -c "$IMPORTS" >/dev/null 2>&1 || die "Dependencies still missing. Run: $PY -m pip install -r requirements.txt"
  echo "  [2/4] Dependencies installed"
fi
echo

# ----------------------------------------------------------------- Port
# Binds rather than connects: a bound-but-not-accepting socket still answers
# "refused", so a connect test reports a busy port as free.
WANT="${WDAP_PORT:-8000}"
PORT="$($PY tools/freeport.py "$WANT" 8025 2>/dev/null || true)"
[ -n "$PORT" ] || die "No free port between $WANT and 8025. Set one: WDAP_PORT=9100 ./run.sh"
if [ "$PORT" != "$WANT" ]; then
  echo "  [3/4] Port $WANT is busy, using $PORT instead"
else
  echo "  [3/4] Port $PORT is free"
fi
echo

# ------------------------------------------------------------- Settings
export WDAP_CHANNEL="${WDAP_CHANNEL:-simulator}"
export WDAP_TIME_SCALE="${WDAP_TIME_SCALE:-0.01}"
export WDAP_PORT="$PORT"
export WDAP_PUBLIC_URL="http://127.0.0.1:${PORT}"

echo "  [4/4] Starting the platform"
echo
echo "  ----------------------------------------------------------------"
echo "    URL          http://127.0.0.1:${PORT}"
echo "    Sign in      admin@gsuretech.com  /  Gsure@2026"
echo "    Channel      ${WDAP_CHANNEL}   (simulator sends nothing)"
echo "    Time scale   ${WDAP_TIME_SCALE}   (15m snapshot lands in ~9s)"
echo "  ----------------------------------------------------------------"
echo
echo "  First run seeds 5,000 groups. Allow a few seconds."
echo "  Press Ctrl+C to stop the server."
echo

cd backend
exec $PY -m uvicorn app:app --host 127.0.0.1 --port "$PORT"
