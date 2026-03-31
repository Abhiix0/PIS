# Placement Intelligence System (PIS)

A data-driven platform that evaluates student placement readiness using SQL feature engineering, Random Forest ML, and a hybrid rule+ML insight engine.

---

## What makes it different

- **SQL-heavy feature engineering** — a 5-CTE pipeline computes readiness features directly in PostgreSQL: total problems solved, difficulty-weighted score, consistency across weeks, and GitHub commit frequency. No Pandas in the hot path.
- **Hybrid insight engine** — rule-based weakness detection combined with ML feature importance ranking. Recommendations are both interpretable (rules fire on thresholds) and data-driven (ordered by what the Random Forest actually weighted most).
- **Real data integration** — fetches actual GitHub repos/commits via the REST API and LeetCode solve statistics via the public GraphQL API. Falls back gracefully to synthetic data if usernames are not set or APIs are unavailable.

---

## Architecture

```
[PostgreSQL]  ←  SQL schema + 5-CTE feature engineering pipeline
      ↓
[FastAPI]     ←  17 endpoints, Pydantic validation, ML pipeline, insight engine
      ↓
[Streamlit]   ←  3-page dashboard — communicates only through the API
```

All three services run in Docker. The API and dashboard never share a database connection — the dashboard is a pure HTTP client.

---

## Quick start

```bash
git clone <repo>
cp .env.example .env   # add your GITHUB_TOKEN (optional)
make up
```

Open **http://localhost:8501** for the dashboard.
Open **http://localhost:8000/docs** for the interactive API docs.

On first boot, `entrypoint.sh` automatically runs feature computation, model training, and initial predictions for all 8 seed students before starting the server.

---

## API reference

| Method | Endpoint                     | Description                          |
|--------|------------------------------|--------------------------------------|
| GET    | /health                      | Basic health check                   |
| GET    | /health/detailed             | Full component status + uptime       |
| GET    | /students                    | List all students with prediction status |
| POST   | /students                    | Create student profile               |
| GET    | /students/{id}               | Get student by ID                    |
| GET    | /students/{id}/status        | Pipeline stage summary               |
| POST   | /ingest/coding/{id}          | Ingest coding data (synthetic)       |
| POST   | /ingest/coding/real/{id}     | Ingest from LeetCode API             |
| POST   | /ingest/github/{id}          | Ingest GitHub data (synthetic)       |
| POST   | /ingest/github/real/{id}     | Ingest from GitHub API               |
| GET    | /features/{id}               | Get computed features                |
| POST   | /predict/{id}                | Run ML prediction                    |
| GET    | /prediction/{id}             | Get saved prediction                 |
| GET    | /insights/{id}               | Get insight report                   |
| POST   | /pipeline/{id}               | Full pipeline in one call            |
| POST   | /pipeline/batch              | Batch pipeline (max 20 students)     |
| GET    | /ranking                     | Leaderboard with branch filter       |

---

## Sample output

`GET /insights/7` for a weak-overall student (Amit Roy, MECH, CGPA 5.8):

```json
{
  "student_id": 7,
  "student_name": "Amit Roy",
  "readiness_score": 28.4,
  "category": "Needs Improvement",
  "strengths": [],
  "weaknesses": [
    {
      "feature": "total_problems",
      "label": "Low Problem Count",
      "message": "Only 4 problems solved — far below placement threshold",
      "raw_value": 4,
      "importance": 0.38
    },
    {
      "feature": "consistency_score",
      "label": "Inconsistent Practice",
      "message": "Active in only 12% of weeks over last 90 days",
      "raw_value": 0.12,
      "importance": 0.27
    }
  ],
  "recommendations": [
    {
      "priority": 1,
      "tier": "critical",
      "area": "total_problems",
      "action": "Solve at least 3 problems per week on LeetCode, focusing on medium difficulty",
      "why_it_matters": "Feature importance: 0.380"
    },
    {
      "priority": 2,
      "tier": "important",
      "area": "consistency_score",
      "action": "Build a daily coding habit — even 1 problem per day compounds significantly",
      "why_it_matters": "Feature importance: 0.270"
    }
  ],
  "top_priority": "Solve at least 3 problems per week on LeetCode, focusing on medium difficulty"
}
```

---

## Tech stack

| Technology   | Why chosen |
|--------------|------------|
| PostgreSQL   | Relational data with clear FK relationships; CTEs and window functions handle feature engineering directly in SQL without loading data into Python |
| SQLAlchemy   | Session management + dependency injection; sync chosen deliberately over async — simpler at this scale, no connection pool overhead |
| FastAPI      | Automatic Swagger docs, Pydantic validation, fast iteration; `TestClient` makes unit testing straightforward |
| Scikit-learn | Proven Random Forest with `feature_importances_` — the importance scores feed directly into the insight ranking layer |
| Streamlit    | Python-only UI, zero frontend complexity, sufficient for demo and interview purposes |

---

## Project structure

```
PIS/
├── app/                    # FastAPI application
│   ├── main.py             # App factory, startup validation, health endpoints
│   ├── db.py               # SQLAlchemy engine + get_db dependency
│   ├── schemas.py          # All Pydantic request/response models
│   └── routers/            # One file per tag group
│       ├── students.py     # CRUD + list + status
│       ├── ingest.py       # Synthetic + real API ingestion
│       ├── features.py     # Feature read endpoint
│       ├── predictions.py  # Predict + get prediction
│       ├── insights.py     # Insight report
│       └── pipeline.py     # Orchestration endpoints
├── ingest/                 # Data ingestion layer
│   ├── coding.py           # Synthetic coding activity generator
│   ├── github.py           # Synthetic GitHub activity generator
│   ├── github_api.py       # Real GitHub REST API client
│   └── leetcode_api.py     # Real LeetCode GraphQL API client
├── features/
│   └── compute.py          # Runs SQL CTE pipeline, scales features, saves scaler
├── ml/
│   ├── labels.py           # Generates training labels from features
│   ├── train.py            # Trains regressor + classifier, saves importances
│   └── predict.py          # Runs inference, writes to predictions table
├── insights/
│   ├── rules.py            # 5 threshold rules (one per feature)
│   └── engine.py           # Applies rules + ranks by ML importance
├── services/
│   └── pipeline.py         # Orchestrates all 5 steps with per-step timing
├── sql/
│   ├── schema.sql          # Table definitions + indexes
│   ├── seed.sql            # 8 students + realistic activity data
│   ├── feature_engineering.sql  # 5-CTE feature computation query
│   └── ranking.sql         # Composite score + window function ranking
├── dashboard/
│   ├── api_client.py       # All HTTP calls in one place
│   └── app.py              # 3-page Streamlit app
├── tests/
│   ├── test_api.py         # Core endpoint tests
│   ├── test_pipeline.py    # Pipeline + student list/status tests
│   ├── test_github_api.py  # GitHub API client unit tests (mocked)
│   └── test_leetcode_api.py # LeetCode API client unit tests (mocked)
├── models/                 # Saved ML artifacts (git-ignored)
├── docker-compose.yml      # db + api + dashboard services
├── Dockerfile              # API container
├── entrypoint.sh           # Boot sequence: features → train → predict → serve
├── Makefile                # Dev commands
└── .env.example            # Environment variable template
```

---

## Environment variables

| Variable       | Required | Description |
|----------------|----------|-------------|
| `DATABASE_URL` | Yes      | PostgreSQL connection string, e.g. `postgresql://pis_user:pis_password@localhost:5432/pis_db` |
| `GITHUB_TOKEN` | No       | GitHub Personal Access Token — increases rate limit from 60 to 5000 requests/hour |

---

## Running tests

```bash
# Local (requires DB + models to be running)
make test-local

# Inside Docker
make test
```

The test suite covers endpoint contracts, Pydantic validation, ML prediction bounds, insight rule logic, and mocked external API clients. All external HTTP calls in tests are mocked — no real network access required.
