from __future__ import annotations

import subprocess
import sys
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
from types import ModuleType

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github" / "workflows" / "ci.yml"
CHANGED_AREAS_SCRIPT = ROOT / "scripts" / "ci_changed_areas.py"


def read_workflow() -> str:
    assert WORKFLOW.is_file(), "Workflow inicial de CI deve existir em .github/workflows/ci.yml"
    return WORKFLOW.read_text(encoding="utf-8")


def workflow_step_block(step_name: str) -> str:
    workflow = read_workflow()
    marker = f"      - name: {step_name}"
    start = workflow.index(marker)
    next_step = workflow.find("\n      - name:", start + len(marker))
    return workflow[start:] if next_step == -1 else workflow[start:next_step]


def load_changed_areas_module() -> ModuleType:
    spec = spec_from_file_location("ci_changed_areas", CHANGED_AREAS_SCRIPT)
    assert spec is not None
    assert spec.loader is not None

    module = module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)

    return module


def test_ci_workflow_runs_on_pull_requests_against_main_without_pull_request_target() -> None:
    workflow = read_workflow()

    assert "pull_request:" in workflow
    assert "branches: [main]" in workflow
    assert "workflow_dispatch:" in workflow
    assert "pull_request_target" not in workflow


def test_ci_workflow_uses_minimal_permissions_and_concurrency() -> None:
    workflow = read_workflow()
    checkout_step = workflow_step_block("Checkout repository")

    assert "permissions:" in workflow
    assert "contents: read" in workflow
    assert "contents: write" not in workflow
    assert "pull-requests: write" not in workflow
    assert "id-token: write" not in workflow
    assert "concurrency:" in workflow
    assert "cancel-in-progress: true" in workflow
    assert "continue-on-error" not in workflow
    assert "persist-credentials: false" in checkout_step


def test_ci_workflow_sets_up_python_uv_and_locked_dependencies() -> None:
    setup_python_step = workflow_step_block("Set up Python")
    setup_uv_step = workflow_step_block("Install uv")

    assert "actions/setup-python@v6" in setup_python_step
    assert "python-version-file: .python-version" in setup_python_step
    assert "astral-sh/setup-uv@08807647e7069bb48b6ef5acd8ec9567f424441b" in setup_uv_step
    assert "version: ${{ env.UV_VERSION }}" in setup_uv_step
    assert 'UV_VERSION: "0.11.16"' in read_workflow()
    assert "uv lock --check" in workflow_step_block("Check uv lockfile")
    assert "uv sync --locked" in workflow_step_block("Sync locked dependencies")


def test_ci_workflow_executes_quality_contract_and_test_gates() -> None:
    workflow = read_workflow()

    expected_commands = [
        "uv run ruff check .",
        "uv run ruff format --check .",
        "uv run pyright",
        "uv run python scripts/check_contracts.py",
        "uv run python scripts/local_harness.py check",
        "uv run pytest",
    ]

    for command in expected_commands:
        assert command in workflow


def test_ci_workflow_runs_secret_scan_with_redaction_without_external_license() -> None:
    secret_scan_step = workflow_step_block("Scan repository for secrets")

    assert "ghcr.io/gitleaks/gitleaks:v8.30.1" in secret_scan_step
    assert "gitleaks/gitleaks-action" not in read_workflow()
    assert "git /repo" in secret_scan_step
    assert '--log-opts="$log_opts"' in secret_scan_step
    assert "--redact=100" in secret_scan_step
    assert "--exit-code 1" in secret_scan_step
    assert "GITLEAKS_LICENSE" not in read_workflow()


def test_ci_workflow_computes_changed_areas_from_pr_or_manual_run() -> None:
    changed_areas_step = workflow_step_block("Summarize changed areas")

    assert '${{ github.event_name }}" = "pull_request"' in changed_areas_step
    assert "github.event.pull_request.base.sha" in changed_areas_step
    assert "github.event.pull_request.head.sha" in changed_areas_step
    assert 'git fetch --no-tags --depth=1 origin "$base_sha"' in changed_areas_step
    assert 'git diff --name-status -M -z "$base_sha...$head_sha"' in changed_areas_step
    assert 'git diff --name-status -M -z "$base_sha...HEAD"' in changed_areas_step
    assert "git fetch --no-tags --depth=1 origin main" in changed_areas_step
    assert "git diff --name-status -M -z origin/main...HEAD" in changed_areas_step


def test_ci_workflow_publishes_traceable_changed_area_summary() -> None:
    changed_areas_step = workflow_step_block("Summarize changed areas")

    assert "scripts/ci_changed_areas.py" in changed_areas_step
    assert "GITHUB_STEP_SUMMARY" in changed_areas_step
    assert "changed-files.txt" in changed_areas_step


def test_changed_areas_script_classifies_relevant_paths() -> None:
    assert CHANGED_AREAS_SCRIPT.is_file(), "Script de impacto do CI deve existir"

    completed = subprocess.run(
        [sys.executable, str(CHANGED_AREAS_SCRIPT)],
        input="\n".join(
            [
                "services/service-template/src/creditos_service_template/__init__.py",
                "packages/contracts/schemas/proposal/v1/proposal.schema.json",
                ".github/workflows/ci.yml",
                "docs/development.md",
            ]
        ),
        text=True,
        capture_output=True,
        check=True,
    )

    output = completed.stdout

    assert "## Impacto da mudança" in output
    assert "services" in output
    assert "packages" in output
    assert "contracts" in output
    assert "ci" in output
    assert "docs" in output
    assert "execução completa dos gates" in output
    assert "Gates planejados" in output


def test_changed_areas_script_classifies_root_tooling_and_infra_files() -> None:
    changed_areas = load_changed_areas_module()

    entries = changed_areas.parse_changed_entries(
        b"M\x00pyproject.toml\x00M\x00uv.lock\x00M\x00.python-version\x00M\x00infra/local/README.md\x00"
    )

    assert changed_areas.classify_changed_areas(entries) == ["infra", "tooling"]


def test_changed_areas_script_preserves_rename_and_delete_semantics() -> None:
    changed_areas = load_changed_areas_module()

    entries = changed_areas.parse_changed_entries(
        b"R100\x00docs/old.md\x00docs/new.md\x00D\x00packages/contracts/old.schema.json\x00"
    )
    output = changed_areas.render_markdown_summary(entries)

    assert "Tipos de mudança: D, R100" in output
    assert "docs" in output
    assert "contracts" in output
    assert "packages" in output
