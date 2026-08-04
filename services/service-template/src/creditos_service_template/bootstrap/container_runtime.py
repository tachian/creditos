"""Runtime mínimo para imagem de exemplo do template de microsserviço."""

from __future__ import annotations

import argparse
import json
import os
import signal
import sys
import time
from pathlib import Path

READY_FILE_ENV = "CREDITOS_READINESS_FILE"
SHUTDOWN_DRAIN_SECONDS_ENV = "CREDITOS_SHUTDOWN_DRAIN_SECONDS"
DEFAULT_READY_FILE = "/tmp/creditos-service-template.ready"
DEFAULT_SHUTDOWN_DRAIN_SECONDS = 1.0


def readiness_file() -> Path:
    return Path(os.environ.get(READY_FILE_ENV, DEFAULT_READY_FILE))


def mark_ready(path: Path) -> bool:
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("ready\n", encoding="utf-8")
    except OSError:
        return False

    return True


def mark_not_ready(path: Path) -> bool:
    try:
        path.unlink(missing_ok=True)
    except OSError:
        return False

    return True


def shutdown_drain_seconds() -> float:
    raw_value = os.environ.get(SHUTDOWN_DRAIN_SECONDS_ENV, str(DEFAULT_SHUTDOWN_DRAIN_SECONDS))

    try:
        value = float(raw_value)
    except ValueError:
        return DEFAULT_SHUTDOWN_DRAIN_SECONDS

    return max(value, 0.0)


def health_payload(status: str, *, probe: str, reason: str | None = None) -> dict[str, str]:
    payload = {
        "status": status,
        "probe": probe,
        "service": os.environ.get("SERVICE_NAME", "creditos-service-template"),
        "version": os.environ.get("SERVICE_VERSION", "0.1.0"),
        "commit_sha": os.environ.get("CREDITOS_COMMIT_SHA", "unknown"),
    }

    if reason is not None:
        payload["reason"] = reason

    return payload


def healthcheck() -> int:
    print(json.dumps(health_payload("ok", probe="liveness"), ensure_ascii=False))
    return 0


def readiness() -> int:
    status = "ready" if readiness_file().is_file() else "not_ready"
    print(json.dumps(health_payload(status, probe="readiness"), ensure_ascii=False))
    return 0 if status == "ready" else 1


def serve() -> int:
    ready_file = readiness_file()
    shutdown_requested = False

    def request_shutdown(_signum: int, _frame: object | None) -> None:
        nonlocal shutdown_requested
        shutdown_requested = True
        mark_not_ready(ready_file)

    signal.signal(signal.SIGTERM, request_shutdown)
    signal.signal(signal.SIGINT, request_shutdown)

    if not mark_ready(ready_file):
        print(
            json.dumps(
                health_payload(
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

    time.sleep(shutdown_drain_seconds())
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Runtime de exemplo do CreditOS")
    parser.add_argument("command", choices=["serve", "healthcheck", "readiness"])
    args = parser.parse_args(argv)

    if args.command == "healthcheck":
        return healthcheck()

    if args.command == "readiness":
        return readiness()

    return serve()


if __name__ == "__main__":
    sys.exit(main())
