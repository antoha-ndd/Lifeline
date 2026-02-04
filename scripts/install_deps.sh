#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
APP_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"

if ! command -v python3 >/dev/null 2>&1; then
  echo "python3 not found. Install it with your package manager first." >&2
  exit 1
fi

sudo apt-get update
sudo apt-get install -y \
  python3-venv \
  python3-pip \
  build-essential \
  libffi-dev \
  libssl-dev

cd "${APP_DIR}"
python3 -m venv .venv
source .venv/bin/activate

python -m pip install --upgrade pip
python -m pip install -r requirements.txt

echo "Done. Activate with: source .venv/bin/activate"

