#!/usr/bin/env bash
# Install ssbot's Python dependencies.
#
#   ./install.sh            create ./.venv and install into it (recommended)
#   ./install.sh --no-venv  install into whatever python3 is currently active
#
set -euo pipefail

cd "$(dirname "$0")"

USE_VENV=1
for arg in "$@"; do
  case "$arg" in
    --no-venv) USE_VENV=0 ;;
    -h|--help) sed -n '2,5p' "$0" | cut -c3-; exit 0 ;;
    *) echo "Unknown option: $arg (try --help)" >&2; exit 1 ;;
  esac
done

if ! command -v python3 >/dev/null 2>&1; then
  echo "python3 not found on PATH." >&2
  exit 1
fi

python3 - <<'EOF'
import sys
if sys.version_info < (3, 8):
    sys.exit(f"Python 3.8+ required, found {sys.version.split()[0]}")
print(f"Using Python {sys.version.split()[0]}")
EOF

if [ "$USE_VENV" -eq 1 ]; then
  if [ ! -d .venv ]; then
    echo "Creating virtualenv in ./.venv ..."
    python3 -m venv .venv
  else
    echo "Reusing existing ./.venv"
  fi
  PY=".venv/bin/python"
else
  PY="python3"
  echo "Installing into the active environment (no virtualenv)."
fi

echo "Installing dependencies ..."
"$PY" -m pip install --quiet --upgrade pip
"$PY" -m pip install --quiet -r requirements.txt

# The PyPI package named `telegram` is an unrelated stub that shadows the name
# and breaks `from telegram import Bot`. parser.py no longer imports it, so this
# is informational only — nothing is uninstalled for you.
if "$PY" -m pip show telegram >/dev/null 2>&1; then
  echo
  echo "Note: the stub package 'telegram' is installed in this environment."
  echo "      ssbot does not use it, but it shadows python-telegram-bot."
  echo "      Remove it with:  $PY -m pip uninstall telegram"
fi

echo "Verifying ..."
"$PY" - <<'EOF'
import requests, bs4
print(f"  requests        {requests.__version__}")
print(f"  beautifulsoup4  {bs4.__version__}")
EOF

echo
echo "Done."
if [ "$USE_VENV" -eq 1 ]; then
  echo "Run it with:      .venv/bin/python parser.py --dry-run"
  echo "Or activate:      source .venv/bin/activate && python parser.py --dry-run"
else
  echo "Run it with:      python3 parser.py --dry-run"
fi
