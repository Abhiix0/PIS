#!/bin/sh
set -e

# Staging/production: image is immutable. Migrations run as a separate release task
# (python -m ingest.migrate); models ship in the image; nothing is trained or seeded at boot.
case "${APP_ENV:-local}" in staging|production)
    exec uvicorn app.main:app --host 0.0.0.0 --port 8000 --proxy-headers ;;
esac

echo Applying migrations
if [ "${SEED_DEMO_DATA:-false}" = "true" ]; then
    python -m ingest.migrate --seed
else
    python -m ingest.migrate
fi

# The legacy ML pipeline (synthetic-label RandomForest) is opt-in: real-user assessments do not use it,
# and an empty database is a valid local state. Run with LOCAL_ML_BOOTSTRAP=true to train and activate a local model.
if [ "${LOCAL_ML_BOOTSTRAP:-false}" = "true" ]; then
    echo Computing features
    python -m features.compute

    echo Training ML models
    python -m ml.train

    echo "Activating first model if none is active (operator: local-bootstrap; refused in staging/production)"
    python -m ml.bundle bootstrap

    echo Running initial predictions
    python -m ml.predict
fi

echo Starting FastAPI server
exec uvicorn app.main:app --host 0.0.0.0 --port 8000
