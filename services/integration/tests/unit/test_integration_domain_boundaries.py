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
    import ast

    offenders: list[str] = []
    for path in DOMAIN_ROOT.rglob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    root = alias.name.split(".")[0]
                    if root in FORBIDDEN_IMPORTS:
                        offenders.append(f"{path.relative_to(DOMAIN_ROOT)} imports {root}")
            elif isinstance(node, ast.ImportFrom) and node.module:
                root = node.module.split(".")[0]
                if root in FORBIDDEN_IMPORTS:
                    offenders.append(f"{path.relative_to(DOMAIN_ROOT)} imports {root}")

    assert offenders == []
