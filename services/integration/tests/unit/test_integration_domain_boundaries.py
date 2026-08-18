from __future__ import annotations

from pathlib import Path

DOMAIN_ROOT = Path(__file__).resolve().parents[2] / "src" / "creditos_integration" / "domain"
FORBIDDEN_IMPORTS = (
    "fastapi",
    "pydantic",
    "sqlalchemy",
    "alembic",
    "grpc",
    "nats",
    "opentelemetry",
    "requests",
    "httpx",
)


def test_integration_domain_has_no_infrastructure_imports() -> None:
    offenders: list[str] = []
    for path in DOMAIN_ROOT.rglob("*.py"):
        content = path.read_text(encoding="utf-8")
        for forbidden in FORBIDDEN_IMPORTS:
            if f"import {forbidden}" in content or f"from {forbidden}" in content:
                offenders.append(f"{path.relative_to(DOMAIN_ROOT)} imports {forbidden}")

    assert offenders == []
