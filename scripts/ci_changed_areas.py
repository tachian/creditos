from __future__ import annotations

import sys
from collections.abc import Iterable
from dataclasses import dataclass


@dataclass(frozen=True)
class ChangedFile:
    status: str
    paths: tuple[str, ...]


AREA_RULES: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("services", ("services/",)),
    ("packages", ("packages/",)),
    (
        "tooling",
        (
            ".python-version",
            "pyproject.toml",
            "uv.lock",
            "ruff.toml",
            "pyrightconfig.json",
        ),
    ),
    ("infra", ("infra/",)),
    (
        "contracts",
        (
            "packages/contracts/",
            "docs/contracts.md",
        ),
    ),
    ("scripts", ("scripts/",)),
    (
        "docs",
        (
            "docs/",
            "README.md",
            "_bmad-output/",
        ),
    ),
    (
        "ci",
        (
            ".github/workflows/",
            ".github/copilot-instructions.md",
        ),
    ),
)

QUALITY_GATES: tuple[str, ...] = (
    "uv lock --check",
    "uv sync --locked",
    "uv run ruff check .",
    "uv run ruff format --check .",
    "uv run pyright",
    "uv run python scripts/check_contracts.py",
    "uv run python scripts/local_harness.py check",
    "uv run pytest",
    "gitleaks git /repo --log-opts=<base..head> --redact=100 --exit-code 1",
)


def _decode_git_path(raw_path: bytes) -> str:
    return raw_path.decode("utf-8", errors="surrogateescape")


def parse_changed_entries(raw_input: bytes) -> list[ChangedFile]:
    if not raw_input:
        return []

    if b"\0" in raw_input:
        return _parse_nul_separated_name_status(raw_input)

    return _parse_line_separated_input(raw_input)


def _parse_nul_separated_name_status(raw_input: bytes) -> list[ChangedFile]:
    tokens = [token for token in raw_input.split(b"\0") if token != b""]
    entries: list[ChangedFile] = []
    index = 0

    while index < len(tokens):
        status = _decode_git_path(tokens[index])
        index += 1

        if status.startswith(("R", "C")) and index + 1 < len(tokens):
            paths = (_decode_git_path(tokens[index]), _decode_git_path(tokens[index + 1]))
            index += 2
        elif index < len(tokens):
            paths = (_decode_git_path(tokens[index]),)
            index += 1
        else:
            break

        entries.append(ChangedFile(status=status, paths=paths))

    return entries


def _parse_line_separated_input(raw_input: bytes) -> list[ChangedFile]:
    entries: list[ChangedFile] = []

    for raw_line in raw_input.splitlines():
        if raw_line == b"":
            continue

        parts = [_decode_git_path(part) for part in raw_line.split(b"\t")]

        if len(parts) >= 3 and parts[0].startswith(("R", "C")):
            entries.append(ChangedFile(status=parts[0], paths=(parts[1], parts[2])))
        elif len(parts) >= 2 and len(parts[0]) <= 4:
            entries.append(ChangedFile(status=parts[0], paths=(parts[1],)))
        else:
            entries.append(ChangedFile(status="M", paths=(parts[0],)))

    return entries


def normalize_paths(entries: Iterable[ChangedFile]) -> list[str]:
    return sorted({path for entry in entries for path in entry.paths if path != ""})


def classify_changed_areas(entries: Iterable[ChangedFile]) -> list[str]:
    normalized_paths = normalize_paths(entries)
    detected_areas = {
        area
        for path in normalized_paths
        for area, prefixes in AREA_RULES
        if any(path == prefix.rstrip("/") or path.startswith(prefix) for prefix in prefixes)
    }

    if not detected_areas and normalized_paths:
        detected_areas.add("other")

    return sorted(detected_areas)


def render_markdown_summary(entries: Iterable[ChangedFile]) -> str:
    normalized_entries = list(entries)
    normalized_paths = normalize_paths(normalized_entries)
    changed_areas = classify_changed_areas(normalized_entries)
    change_types = sorted({entry.status for entry in normalized_entries})
    changed_areas_text = (
        ", ".join(changed_areas) if changed_areas else "nenhuma alteração detectada"
    )
    change_types_text = ", ".join(change_types) if change_types else "nenhuma alteração detectada"

    lines = [
        "## Impacto da mudança",
        "",
        f"- Arquivos alterados: {len(normalized_paths)}",
        f"- Tipos de mudança: {change_types_text}",
        f"- Áreas detectadas: {changed_areas_text}",
        "- Estratégia atual: execução completa dos gates enquanto o repositório ainda é pequeno.",
        "- Evolução prevista: separar jobs por área quando o tempo de CI justificar.",
        "",
        "## Gates planejados",
        "",
    ]

    lines.extend(f"- `{gate}`" for gate in QUALITY_GATES)
    lines.append("")

    return "\n".join(lines)


def main() -> int:
    if len(sys.argv) > 1:
        raw_input = "\n".join(sys.argv[1:]).encode("utf-8", errors="surrogateescape")
    else:
        raw_input = sys.stdin.buffer.read()

    sys.stdout.write(render_markdown_summary(parse_changed_entries(raw_input)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
