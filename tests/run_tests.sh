#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

# (Opcional) Si quieres permitir BASE_URL desde entorno sin .env:
export BASE_URL="${BASE_URL:-https://localhost}"
export HTTP_TIMEOUT="${HTTP_TIMEOUT:-5}"

python3 -m venv .venv-tests
source .venv-tests/bin/activate

pip install -U pip
pip install -r tests/requirements-dev.txt

pytest -q