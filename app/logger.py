import json
import logging
import sys

import config


class JsonFormatter(logging.Formatter):
    """One JSON object per line for CloudWatch; extra fields (request_id, ...) are passed via logger(..., extra=...)."""

    _FIELDS = (
        "request_id",
        "method",
        "path",
        "status",
        "duration_ms",
        "run_id",
        "sync_status",
        "error_code",
    )

    def format(self, record):
        out = {
            "ts": self.formatTime(record, "%Y-%m-%dT%H:%M:%S"),
            "level": record.levelname,
            "msg": record.getMessage(),
        }
        out.update({k: getattr(record, k) for k in self._FIELDS if hasattr(record, k)})
        return json.dumps(out)


def setup_logger(name: str = "pis") -> logging.Logger:
    logger = logging.getLogger(name)
    if logger.handlers:
        return logger  # already configured — don't add duplicate handlers

    logger.setLevel(logging.INFO)
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(
        JsonFormatter()
        if config.is_deployed()
        else logging.Formatter(
            # ISO timestamp | level | module | message
            fmt="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
            datefmt="%Y-%m-%dT%H:%M:%S",
        )
    )
    logger.addHandler(handler)
    return logger


logger = setup_logger()
