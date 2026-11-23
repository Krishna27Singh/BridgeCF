#!/bin/sh
set -eu

if [ ! -f /app/backend/data/bridgecf.db ]; then
    python -m app.scripts.build_knowledge_base \
        --limit "${BOOTSTRAP_LIMIT:-2000}"
fi

exec python -m uvicorn app.main:app \
    --host 0.0.0.0 \
    --port "${PORT:-8000}"
