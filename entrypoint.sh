#!/bin/sh

# 1. Generate features from SQL data
echo "Computing features..."
python -m features.compute

# 2. Train the ML models and export importances
echo "Training ML models..."
python -m ml.train

# 3. Start the FastAPI server
echo "Starting FastAPI server..."
exec uvicorn app.main:app --host 0.0.0.0 --port 8000