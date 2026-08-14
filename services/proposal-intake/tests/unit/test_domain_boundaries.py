from __future__ import annotations

import ast
from pathlib import Path


def test_domain_layer_does_not_import_infrastructure_dependencies() -> None:
    domain_root = Path(__file__).parents[2] / "src" / "creditos_proposal_intake" / "domain"
    forbidden_import_roots = {
        "creditos_observability",
        "creditos_security",
        "fastapi",
        "grpc",
        "nats",
        "opentelemetry",
        "pydantic",
        "sqlalchemy",
    }

    for source_file in domain_root.rglob("*.py"):
        tree = ast.parse(source_file.read_text(encoding="utf-8"))
        imported_roots: set[str] = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported_roots.update(alias.name.split(".", maxsplit=1)[0] for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                imported_roots.add(node.module.split(".", maxsplit=1)[0])

        assert imported_roots.isdisjoint(forbidden_import_roots), source_file
