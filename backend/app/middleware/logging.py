"""Request logging middleware registration."""

from __future__ import annotations

import json
import logging
import time
import uuid

from flask import Flask, g, has_request_context, request


class JSONFormatter(logging.Formatter):
    """Simple JSON formatter for structured logs."""

    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "timestamp": self.formatTime(record, "%Y-%m-%dT%H:%M:%S"),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
        }
        if has_request_context():
            payload["request_id"] = getattr(g, "request_id", None)
            payload["path"] = request.path
            payload["method"] = request.method
            payload["remote_addr"] = request.remote_addr
            payload["user_id"] = getattr(g, "user_id", None)
        return json.dumps(payload, default=str)


def _configure_structured_logging(app: Flask) -> None:
    if not app.logger.handlers:
        handler = logging.StreamHandler()
        app.logger.addHandler(handler)

    level_name = str(app.config.get("LOG_LEVEL", "INFO")).upper()
    app.logger.setLevel(getattr(logging, level_name, logging.INFO))

    for handler in app.logger.handlers:
        handler.setFormatter(JSONFormatter())


def register_request_logging(app: Flask) -> None:
    """Register request timing and request-id logging hooks."""

    _configure_structured_logging(app)

    @app.before_request
    def _start_request_timer() -> None:
        g.request_start_time = time.perf_counter()
        g.request_id = request.headers.get("X-Request-Id", str(uuid.uuid4()))

    @app.after_request
    def _log_request(response):
        start = getattr(g, "request_start_time", None)
        duration_ms = 0.0
        if start is not None:
            duration_ms = (time.perf_counter() - start) * 1000
        app.logger.info(
            "request_id=%s method=%s path=%s status=%s duration_ms=%.2f",
            getattr(g, "request_id", "-"),
            request.method,
            request.path,
            response.status_code,
            duration_ms,
        )
        response.headers["X-Request-Id"] = getattr(g, "request_id", "-")
        return response
