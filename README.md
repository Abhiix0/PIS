# Placement Intelligence System (PIS)

A data-driven platform that evaluates student placement readiness using SQL feature engineering, Random Forest ML, and a hybrid rule + ML insight engine.

---

## What makes it different

- **SQL-first feature engineering** — a 5-CTE pipeline computes all readiness features directly in PostgreSQL. No Pandas in the hot path. A separate single-student variant runs O(1) per pipeline call instead of scanning the full table.
- **Hybrid insight engine** — rule-based weakness detection combined with ML feature importance ranking. Recommendations are both interpretable (rules fire on human-readable thresholds) and data-driven (ordered by what the Random Forest actually weighted most).
- **Real data integration** — fetches actual GitHub repos/commits via the REST API and LeetCode solve statistics via the public GraphQL API. Falls back gracefully to synthetic data if usernames are not set or APIs are unavailable, with a 24-hour cache to prevent hammering external APIs.
- **Production-aware design** — atomic model swaps via staging directory, pipeline cooldown with `force_refresh` override, prediction history throttling, and startup validation that fails fast before serving a single request.

---

## Architecture

```
[PostgreSQL]  ←  schema + 5-CTE feature engineering + ranking SQL
      ↓
[FastAPI]     ←  18 endpoints · Pydantic validation · psycopg2 pool
      ↓
[Streamlit]   ←  3-page dashboard — communicates only via HTTP
```

All three services run in Docker. The dashboard has zero direct database access — it is a pure HTTP client against the API. The API uses a single psycopg2 `ThreadedConnectionPool` (min=2, max=20) shared across all modules.

---

## Quick start

```bash
git clone <repo-url>
cd PIS
cp .env.example .env          # set DATABASE_URL; add GITHUB_TOKEN (optional)
make up                        # builds + starts all 3 containers
```

On first boot, `entrypoint.sh` automatically runs:
1. Feature computation (full-table SQL pipeline)
2. Model training (Random Forest regressor + classifier)
3. Initial predictions for all 8 seed students
4. FastAPI server start

Open **http://localhost:8501** for the Streamlit dashboard.  
Open **http://localhost:8000/docs** for interactive API docs (Swagger).

---

## API reference

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/health` | Basic liveness check |
| GET | `/health/detailed` | DB status, model state, uptime, student count |
| GET | `/students` | List all students with prediction status |
| POST | `/students` | Create student profile |
| GET | `/students/{id}` | Get student by ID |
| PATCH | `/students/{id}` | Update CGPA or platform usernames |
| GET | `/students/{id}/status` | Pipeline stage: `no_data` → `features_computed` → `predicted` → `complete` |
| GET | `/students/{id}/history` | Last 30 prediction history records |
| POST | `/ingest/coding/{id}` | Ingest synthetic coding activity |
| POST | `/ingest/coding/real/{id}` | Fetch real data from LeetCode API (falls back to synthetic) |
| POST | `/ingest/github/{id}` | Ingest synthetic GitHub activity |
| POST | `/ingest/github/real/{id}` | Fetch real data from GitHub REST API |
| GET | `/features/{id}` | Get computed features for a student |
| POST | `/predict/{id}` | Run ML prediction and save result |
| GET | `/prediction/{id}` | Get saved prediction |
| GET | `/insights/{id}` | Full insight report: strengths, weaknesses, composite patterns, recommendations |
| POST | `/pipeline/{id}` | Run all 5 steps in sequence with per-step timing |
| POST | `/pipeline/batch` | Batch pipeline — up to 20 students, 3 concurrent |
| GET | `/ranking` | Leaderboard with optional branch filter |
| POST | `/admin/retrain` | Trigger background model retrain (admin key required) |
| GET | `/admin/retrain/status` | Poll retrain state: `idle` → `running` → `completed` / `failed` |

---

## The pipeline (5 steps)

```
POST /pipeline/{id}
    │
    ├─ Step 1: Coding ingestion
    │     └─ LeetCode API (if username set + not cached) → synthetic fallback
    │
    ├─ Step 2: GitHub ingestion
    │     └─ GitHub REST API (if username set + not cached) → synthetic fallback
    │
    ├─ Step 3: Feature computation
    │     └─ Runs parameterised 5-CTE SQL directly in PostgreSQL
    │           CTE 1: total problems solved
    │           CTE 2: avg difficulty (easy=1, medium=2, hard=3)
    │           CTE 3: consistency score (active weeks / 13 in last 90 days)
    │           CTE 4: commit frequency (commits per day over active window)
    │           CTE 5: UPSERT into features table
    │
    ├─ Step 4: ML prediction
    │     └─ Random Forest regressor → readiness score (0–100)
    │        Random Forest classifier → category label
    │        Saves to predictions + appends prediction_history (once/hour)
    │
    └─ Step 5: Insight generation
          └─ 5 threshold rules fire on raw feature values
             Weaknesses ranked by ML feature importance
             Composite pattern detection across rule combinations
             Tiered recommendations: critical → important → suggested
```

A **5-minute cooldown** prevents redundant pipeline runs. Use `?force_refresh=true` to bypass.

---

## Feature importances (from trained regressor)

| Feature | Importance | What it measures |
|---------|-----------|-----------------|
| `total_problems` | 0.259 | Volume of LeetCode problems solved |
| `avg_difficulty` | 0.230 | Weighted difficulty (1=easy, 2=medium, 3=hard) |
| `consistency_score` | 0.207 | Fraction of weeks active in the last 90 days |
| `commit_frequency` | 0.200 | Average GitHub commits per active day |
| `cgpa` | 0.105 | Academic GPA (0–10 scale) |

---

## Sample output

`GET /insights/7` — Amit Roy, MECH, CGPA 5.8:

```json
{
  "student_id": 7,
  "student_name": "Amit Roy",
  "readiness_score": 28.4,
  "category": "Needs Improvement",
  "score_delta_7d": -3.2,
  "score_trend": "↓ slipping",
  "strengths": [],
  "weaknesses": [
    {
      "feature": "total_problems",
      "label": "low_dsa_volume",
      "message": "Only 4 problems solved — most companies filter at 75+",
      "raw_value": 4,
      "importance": 0.259
    },
    {
      "feature": "consistency_score",
      "label": "low_consistency",
      "message": "Active only 12% of weeks in last 90 days — burst activity does not build retention",
      "raw_value": 0.12,
      "importance": 0.207
    }
  ],
  "composite_insights": [
    {
      "pattern": "needs_structure",
      "message": "Both practice volume and consistency are below threshold — sporadic effort is not compounding.",
      "action": "Start a 30-day streak: one problem per day, any difficulty. Habit first, difficulty second."
    }
  ],
  "recommendations": [
    {
      "priority": 1,
      "tier": "critical",
      "area": "low_dsa_volume",
      "action": "Solve 2–3 LeetCode problems daily. Target medium difficulty. Focus on arrays, strings, and trees first.",
      "why_it_matters": "Problem-solving volume carries a high weight in this tool's readiness proxy score; it is not validated as a predictor of placement outcomes."
    }
  ],
  "top_priority": "Solve 2–3 LeetCode problems daily. Target medium difficulty. Focus on arrays, strings, and trees first."
}
```

---

## Project structure

```
PIS/
├── app/
│   ├── main.py              # App factory, lifespan startup validation, health endpoints
│   ├── schemas.py           # All Pydantic request/response models
│   ├── logger.py            # Structured request logger
│   └── routers/
│       ├── students.py      # CRUD, list, status, history, patch
│       ├── ingest.py        # Synthetic + real API ingestion (coding + github)
│       ├── features.py      # Feature read endpoint
│       ├── predictions.py   # Predict + get prediction
│       ├── insights.py      # Full insight report
│       ├── pipeline.py      # Single + batch pipeline orchestration
│       └── admin.py         # Retrain trigger + status poll
├── ingest/
│   ├── coding.py            # Synthetic coding activity generator
│   ├── github.py            # Synthetic GitHub activity generator
│   ├── github_api.py        # Real GitHub REST API client (paginated commits)
│   ├── leetcode_api.py      # Real LeetCode GraphQL API client (submitStats)
│   ├── db_connection.py     # psycopg2 ThreadedConnectionPool — single source of truth
│   └── validators.py        # Record-level validation before DB insert
├── features/
│   └── compute.py           # Runs SQL CTE pipeline, scales features, saves scaler
├── ml/
│   ├── labels.py            # Weighted label generation + Gaussian noise for realistic R²
│   ├── train.py             # Trains regressor + classifier, exports importances, drift detection
│   └── predict.py           # Inference, upsert to predictions, history throttling
├── insights/
│   ├── rules.py             # 5 threshold rules, one per feature (raw values, human-readable)
│   └── engine.py            # Applies rules, ranks by importance, composite pattern detection
├── services/
│   └── pipeline.py          # 5-step orchestration with per-step timing, TTL-aware API calls
├── sql/
│   ├── seed.sql             # 8 students with varied realistic activity profiles
│   ├── feature_engineering.sql         # Full-table 5-CTE pipeline (used by ml.train)
│   ├── feature_engineering_single.sql  # Parameterised single-student variant (used by pipeline)
│   ├── ranking.sql          # Composite score + window function global/branch ranking
│   └── migrations/          # Ordered migrations (000_baseline…), applied by ingest/migrate.py
├── dashboard/
│   ├── api_client.py        # All HTTP calls in one place
│   └── app.py               # 3-page Streamlit app with dark theme
├── tests/
│   ├── test_core.py         # Rule logic + health endpoint + label boundaries (no DB needed)
│   ├── test_api.py          # Endpoint contracts, validation, branch normalisation
│   ├── test_pipeline.py     # Pipeline, batch limits, student status, health/detailed
│   ├── test_insights.py     # Insight engine rules in isolation
│   ├── test_github_api.py   # GitHub API client (fully mocked)
│   └── test_leetcode_api.py # LeetCode API client (fully mocked, 8 cases)
├── models/                  # Saved ML artifacts (git-ignored in production)
│   ├── regressor.pkl
│   ├── classifier.pkl
│   ├── scaler.pkl
│   └── feature_importances.json
├── docs/
│   ├── erd.png              # Entity-relationship diagram
│   └── query_optimization.md
├── docker-compose.yml       # db + api + dashboard services
├── Dockerfile               # API container (Python 3.11-slim)
├── dashboard/Dockerfile     # Dashboard container
├── entrypoint.sh            # Boot sequence: features → train → predict → serve
├── Makefile                 # Dev commands (see below)
├── requirements.txt
├── config.py                # Loads DATABASE_URL from .env
└── .env.example
```

---

## Make commands

```bash
make up              # Build and start all services (foreground)
make up-detached     # Build and start (background)
make down            # Stop containers
make down-clean      # Stop containers and remove volumes (wipes DB)
make restart         # Restart API container only
make test            # Run tests inside Docker
make test-local      # Run tests locally (requires running DB + models)
make health          # curl /health/detailed and pretty-print
make pipeline-all    # Run batch pipeline for all 8 seed students
make logs            # Tail API logs
make clean           # Remove __pycache__ and .pyc files
```

---

## Environment variables

| Variable | Required | Description |
|----------|----------|-------------|
| `DATABASE_URL` | Yes | e.g. `postgresql://pis_user:<password>@db:5432/pis_db` |
| `GITHUB_TOKEN` | No | Personal Access Token — raises rate limit from 60 to 5,000 req/hr |
| `ADMIN_KEY` | Staging/prod | Minimum 16 chars — `/admin/*` returns 503 while unset |
| `APP_ENV` | No | `local` (default), `test`, `staging`, `production`; the last two enforce a real `ADMIN_KEY`, reject placeholder secrets, and refuse demo seed |

---

## Running tests

```bash
# All tests (requires live DB + models)
make test

# Without Docker
pytest tests/ -v --tb=short

# Only unit tests (no DB or model files needed)
pytest tests/test_core.py tests/test_insights.py tests/test_github_api.py tests/test_leetcode_api.py -v
```

All external HTTP calls (GitHub, LeetCode) are mocked — no network access required for the test suite. The core unit tests (`test_core.py`) run entirely without a database or model files.

---

## Tech stack

| Technology | Why |
|------------|-----|
| PostgreSQL | CTEs and window functions handle all feature engineering without loading data into Python |
| psycopg2 | Single `ThreadedConnectionPool` shared across all modules — no dual-pool split |
| FastAPI | Automatic Swagger docs, Pydantic validation, lifespan startup hooks |
| scikit-learn | Random Forest with `feature_importances_` — importance scores feed directly into insight ranking |
| Streamlit | Python-only UI, zero frontend complexity, sufficient for demo and presentation |

---

## Design decisions worth noting

**Why psycopg2 over SQLAlchemy** — The project uses a single psycopg2 `ThreadedConnectionPool` for all database access. SQLAlchemy was removed to eliminate dual-pool complexity (two separate connection managers talking to the same database). The psycopg2 pool handles commit/rollback/return via a context manager, which is sufficient for this workload.

**Why two SQL variants for features** — `feature_engineering.sql` scans all rows (used at training time). `feature_engineering_single.sql` is parameterised to a single `student_id` (used in the live pipeline). This avoids O(n_students) work on every pipeline call.

**Why Gaussian noise on labels** — Labels are a weighted formula of the features, so they are synthetic. Noise (`σ=5`, fixed seed) only stops the model reproducing the formula exactly; it does not model placement-outcome variance. Reported R² measures how well the model re-learns that formula, not how well it predicts placement. See `docs/research/dataset-card.md`.

**Why atomic model swap on retrain** — New models are trained to `models/staging/`, smoke-tested against all current students, then moved to `models/` only on success. Live models are never touched if the retrain fails.
