#!/usr/bin/env bash
# Activate virtualenv if present, then run uvicorn for the API app
set -euo pipefail
if [ -f .venv/bin/activate ]; then
	# shellcheck disable=SC1091
	. .venv/bin/activate
fi

echo "Starting FastAPI (uvicorn) on 0.0.0.0:8000"
exec uvicorn api.app:app --host 0.0.0.0 --port 8000 --reload
