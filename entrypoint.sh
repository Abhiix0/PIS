#!/bin/sh
set -e

echo Applying migrations
if [ "${SEED_DEMO_DATA:-false}" = "true" ]; then
    python -m ingest.migrate --seed
else
    python -m ingest.migrate
fi

echo Computing features
python -m features.compute

echo Training ML models
python -m ml.train

echo Running initial predictions
python -m ml.predict

echo Starting FastAPI server
exec uvicorn app.main:app --host 0.0.0.0 --port 8000
