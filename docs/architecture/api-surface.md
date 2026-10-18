# API surface

Source of truth is `app.routes`; `tests/test_route_coverage.py::test_api_surface_doc_matches_routes` fails if this table drifts.
Auth: **public** = no token; **user** = valid IdP JWT (`current_principal`); **operator** = user + role `pis_operator` (`require_operator`).
Data owner: "caller" = rows scoped by the token's `user_id` inside the SQL; "system" = no per-user data.
Every error, on every route, is `{"error": {"code", "message", "request_id"}}` (`app/main.py`). `/health*` returns its own probe JSON.

| Route | Auth | Data owner |
|---|---|---|
| `GET /health` | public | system |
| `GET /health/ready` | public | system |
| `GET /health/detailed` | public | system |
| `GET /api/v1/me` | user | caller |
| `PUT /api/v1/me/profile` | user | caller |
| `GET /api/v1/me/data-quality` | user | caller |
| `GET /api/v1/me/export` | user | caller |
| `POST /api/v1/me/data-requests/deletion` | user | caller |
| `GET /api/v1/me/data-requests` | user | caller |
| `GET /api/v1/me/privacy` | user | caller |
| `PUT /api/v1/me/privacy` | user | caller |
| `GET /api/v1/integrations` | user | caller |
| `PUT /api/v1/integrations/{provider}` | user | caller |
| `DELETE /api/v1/integrations/{provider}` | user | caller |
| `POST /api/v1/integrations/{provider}/sync` | user | caller |
| `GET /api/v1/sync-runs` | user | caller |
| `GET /api/v1/sync-runs/{run_id}` | user | caller |
| `POST /api/v1/assessments` | user | caller |
| `GET /api/v1/assessments` | user | caller |
| `GET /api/v1/assessments/{assessment_id}` | user | caller |
| `GET /api/v1/assessments/{assessment_id}/evidence` | user | caller |
| `POST /auth/logout` | user | caller |
| `POST /admin/retrain` | operator | system |
| `GET /admin/retrain/status` | operator | system |
| `GET /admin/models` | operator | system |
| `POST /admin/models/{version}/approve` | operator | system |
| `POST /admin/models/{version}/activate` | operator | system |
| `POST /admin/models/rollback` | operator | system |
| `GET /admin/audit-events` | operator | system (actor ids only) |
| `GET /admin/sync-failures` | operator | system (no user fields) |

Removed (decision B): `/students*`, `/ingest/*`, `/predict`, `/prediction`, `/insights`, `/ranking`, `/features`, `/pipeline/*`,
unversioned `/me`, `/profiles*`, `/integrations*`, and the Streamlit dashboard.
