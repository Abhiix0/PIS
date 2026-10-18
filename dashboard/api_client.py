"""All API calls go through this module. Never build URLs in page files."""

import os

import requests

API_BASE = os.getenv("API_URL", "http://localhost:8000")
# Legacy demo endpoints are operator-only: supply an operator access token from the IdP (never baked into the image).
HEADERS = (
    {"Authorization": f"Bearer {os.environ['PIS_API_TOKEN']}"} if os.getenv("PIS_API_TOKEN") else {}
)
TIMEOUT = 60  # seconds — pipeline with real API calls can take a while


def _get(path: str, params: dict = None) -> dict | list:
    resp = requests.get(f"{API_BASE}{path}", params=params, headers=HEADERS, timeout=TIMEOUT)
    resp.raise_for_status()
    return resp.json()


def _post(path: str, json: dict = None, params: dict = None) -> dict | list:
    resp = requests.post(
        f"{API_BASE}{path}", json=json, params=params, headers=HEADERS, timeout=TIMEOUT
    )
    resp.raise_for_status()
    return resp.json()


def health_check() -> dict:
    return _get("/health")


def get_students() -> list:
    return _get("/students")


def get_student(student_id: int) -> dict:
    return _get(f"/students/{student_id}")


def get_student_status(student_id: int) -> dict:
    return _get(f"/students/{student_id}/status")


def get_student_history(student_id: int) -> list:
    return _get(f"/students/{student_id}/history")


def create_student(payload: dict) -> dict:
    return _post("/students", json=payload)


def update_student(student_id: int, payload: dict) -> dict:
    """PATCH a student's mutable fields (usernames, cgpa)."""
    resp = requests.patch(
        f"{API_BASE}/students/{student_id}",
        json=payload,
        timeout=TIMEOUT,
    )
    resp.raise_for_status()
    return resp.json()


def run_pipeline(student_id: int, force_refresh: bool = False) -> dict:
    params = {"force_refresh": "true"} if force_refresh else None
    return _post(f"/pipeline/{student_id}", params=params)


def get_features(student_id: int) -> dict:
    return _get(f"/features/{student_id}")


def get_prediction(student_id: int) -> dict:
    return _get(f"/prediction/{student_id}")


def get_insights(student_id: int) -> dict:
    return _get(f"/insights/{student_id}")


def get_ranking(branch: str | None = None, limit: int = 20) -> list:
    params = {"limit": limit}
    if branch:
        params["branch"] = branch
    return _get("/ranking", params=params)
