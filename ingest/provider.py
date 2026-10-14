"""Shared types for provider adapters: a typed observation and a safe, coded failure."""
from dataclasses import dataclass
from datetime import datetime
from typing import Optional

# Safe codes only: they are stored and returned to clients, so never put payloads or tokens in them.
CODES = ("not_found", "rate_limited", "forbidden", "unavailable", "malformed", "disabled")


class ProviderError(RuntimeError):
    """The provider could not give a trustworthy answer. This is never the same as 'zero activity'."""

    def __init__(self, code: str, message: str = "", retry_after: Optional[int] = None):
        assert code in CODES, code
        super().__init__(message or code)
        self.code = code
        self.retry_after = retry_after


@dataclass(frozen=True)
class Observation:
    provider: str
    observation_type: str
    value_num: float
    granularity: str = "aggregate"            # 'event' | 'aggregate'
    source_object_id: Optional[str] = None
    event_at: Optional[datetime] = None
    event_at_precision: str = "unknown"       # 'exact' | 'day' | 'repo_push' | 'unknown'
    provenance: str = "observed"
    payload_version: str = ""

    @property
    def value_state(self) -> str:
        return "measured_zero" if self.value_num == 0 else "present"
