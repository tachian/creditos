from __future__ import annotations

import argparse
import json
import os
import signal
import sys
import time
from pathlib import Path

READINESS_FILE = Path(
    os.environ.get("CREDITOS_READINESS_FILE", "/tmp/creditos-audit-evidence.ready")
)
DEFAULT_SHUTDOWN_DRAIN_SECONDS = 1.0


def healthcheck() -> int:
    print(json.dumps(_health_payload("ok", probe="liveness"), ensure_ascii=False))
    return 0


def readiness() -> int:
    status = "ready" if READINESS_FILE.is_file() else "not_ready"
    print(json.dumps(_health_payload(status, probe="readiness"), ensure_ascii=False))
    return 0 if status == "ready" else 1


def serve() -> int:
    shutdown_requested = False

    def request_shutdown(_signum: int, _frame: object | None) -> None:
        nonlocal shutdown_requested
        shutdown_requested = True
        READINESS_FILE.unlink(missing_ok=True)

    signal.signal(signal.SIGTERM, request_shutdown)
    signal.signal(signal.SIGINT, request_shutdown)

    try:
        READINESS_FILE.parent.mkdir(parents=True, exist_ok=True)
        READINESS_FILE.write_text("ready\n", encoding="utf-8")
    except OSError:
        print(
            json.dumps(
                _health_payload(
                    "not_ready",
                    probe="readiness",
                    reason="readiness_file_unavailable",
                ),
                ensure_ascii=False,
            ),
            file=sys.stderr,
        )
        return 1

    while not shutdown_requested:
        time.sleep(0.2)

    time.sleep(_shutdown_drain_seconds())
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Runtime mínimo do Audit & Evidence Service")
    parser.add_argument("command", choices=["serve", "healthcheck", "readiness"])
    args = parser.parse_args(argv)

    if args.command == "healthcheck":
        return healthcheck()
    if args.command == "readiness":
        return readiness()
    return serve()


def _health_payload(status: str, *, probe: str, reason: str | None = None) -> dict[str, str]:
    payload = {
        "status": status,
        "probe": probe,
        "service": os.environ.get("SERVICE_NAME", "creditos-audit-evidence"),
        "version": os.environ.get("SERVICE_VERSION", "0.1.0"),
        "commit_sha": os.environ.get("CREDITOS_COMMIT_SHA", "unknown"),
    }
    if reason is not None:
        payload["reason"] = reason
    return payload


def _shutdown_drain_seconds() -> float:
    raw_value = os.environ.get(
        "CREDITOS_SHUTDOWN_DRAIN_SECONDS",
        str(DEFAULT_SHUTDOWN_DRAIN_SECONDS),
    )
    try:
        value = float(raw_value)
    except ValueError:
        return DEFAULT_SHUTDOWN_DRAIN_SECONDS
    return max(value, 0.0)


if __name__ == "__main__":
    raise SystemExit(main())
