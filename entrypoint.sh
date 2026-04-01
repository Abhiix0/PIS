#!/bin/sh
set -e

echo Computing features
python -m features.compute

echo Training ML models
python -m ml.train

echo Running initial predictions
python -m ml.predict

echo Starting FastAPI server
exec uvicorn app.main:app --host 0.0.0.0 --port 8000
