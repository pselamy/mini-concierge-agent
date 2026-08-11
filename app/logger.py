# app/logger.py
import logging
import json
import sys
import re
from datetime import datetime, timezone

# Simple email regex
EMAIL_REGEX = re.compile(r"[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+")

# Generic phone number regex
PHONE_REGEX = re.compile(
    r"\b(?:\+?(\d{1,3}))?[-. (]*(\d{3})[-. )]*(\d{3})[-. ]*(\d{4})\b"
)


def redact_text(text: str) -> str:
    text = EMAIL_REGEX.sub("[REDACTED_EMAIL]", text)
    text = PHONE_REGEX.sub("[REDACTED_PHONE]", text)
    return text


# Custom LogRecord factory to redact PII at record creation time
_old_factory = logging.getLogRecordFactory()


def pii_redacting_log_record_factory(*args, **kwargs):
    record = _old_factory(*args, **kwargs)
    if isinstance(record.msg, str):
        record.msg = redact_text(record.msg)
    if hasattr(record, "intent") and isinstance(record.intent, str):
        record.intent = redact_text(record.intent)
    if hasattr(record, "outcome") and isinstance(record.outcome, str):
        record.outcome = redact_text(record.outcome)
    return record


class JsonFormatter(logging.Formatter):
    def format(self, record):
        log_data = {
            "timestamp": datetime.fromtimestamp(record.created, tz=timezone.utc)
            .isoformat()
            .replace("+00:00", "Z"),
            "level": record.levelname,
            "message": record.getMessage(),
            "name": record.name,
        }
        # Capture extra fields for intent/outcome and redact them
        if hasattr(record, "intent") and isinstance(record.intent, str):
            log_data["intent"] = redact_text(record.intent)
        if hasattr(record, "outcome") and isinstance(record.outcome, str):
            log_data["outcome"] = redact_text(record.outcome)
        return json.dumps(log_data)


def setup_logging():
    # Register the redacting LogRecord factory
    logging.setLogRecordFactory(pii_redacting_log_record_factory)

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JsonFormatter())

    logging.basicConfig(level=logging.INFO, handlers=[handler], force=True)
