from __future__ import annotations

from collections.abc import Mapping
from datetime import UTC, datetime


def health_response(*, service_name: str, service_version: str) -> dict[str, str]:
    return {
        "status": "ok",
        "service.name": service_name,
        "service.version": service_version,
        "timestamp": datetime.now(UTC).isoformat(),
    }


def readiness_response(
    *,
    service_name: str,
    service_version: str,
    checks: Mapping[str, object],
) -> dict[str, object]:
    readiness_checks = [
        {
            "name": _safe_check_name(name, index),
            "status": "ready" if _is_ready(ready) else "not_ready",
        }
        for index, (name, ready) in enumerate(checks.items(), start=1)
    ]
    overall_status = "ready" if all(_is_ready(ready) for ready in checks.values()) else "not_ready"

    return {
        "status": overall_status,
        "service.name": service_name,
        "service.version": service_version,
        "timestamp": datetime.now(UTC).isoformat(),
        "checks": readiness_checks,
    }


def _safe_check_name(name: str, index: int) -> str:
    safe_names = {"database", "cache", "queue", "broker", "storage"}
    normalized_name = name.strip().lower()
    if normalized_name in safe_names:
        return normalized_name

    return f"dependency_{index}"


def _is_ready(value: object) -> bool:
    return value is True
