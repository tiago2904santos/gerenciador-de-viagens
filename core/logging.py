from __future__ import annotations

import json
import logging
from datetime import datetime, timezone


class RequestContextFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        from core.middleware import get_current_request

        request = get_current_request()
        record.request_id = getattr(request, "request_id", "") if request else ""
        record.request_path = getattr(request, "path", "") if request else ""
        record.request_method = getattr(request, "method", "") if request else ""
        return True


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "time": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "request_id": getattr(record, "request_id", ""),
            "method": getattr(record, "request_method", ""),
            "path": getattr(record, "request_path", ""),
        }
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)
        return json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
