from __future__ import annotations

import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_required_root_directories_exist() -> None:
    required_directories = ["services", "packages", "tests", "infra", "docs", "scripts"]

    for directory in required_directories:
        assert (ROOT / directory).is_dir(), f"Diretório obrigatório ausente: {directory}"


def test_python_baseline_and_workspace_configuration() -> None:
    assert (ROOT / ".python-version").read_text(encoding="utf-8").strip() == "3.13"

    pyproject = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))

    assert pyproject["project"]["requires-python"] == ">=3.13"
    assert pyproject["tool"]["uv"]["workspace"]["members"] == ["services/*", "packages/*"]
    assert pyproject["tool"]["pyright"]["include"] == ["services", "packages", "tests"]
    assert "dev" in pyproject["dependency-groups"]
    assert "ruff" in pyproject["tool"]
    assert "pyright" in pyproject["tool"]
    assert "pytest" in pyproject["tool"]


def test_single_uv_lockfile_policy() -> None:
    assert (ROOT / "uv.lock").is_file(), "uv.lock deve existir e ser versionado"

    forbidden_lockfiles = [
        "requirements.txt",
        "requirements-dev.txt",
        "Pipfile",
        "Pipfile.lock",
        "poetry.lock",
        "pdm.lock",
        "hatch.toml",
        "tox.ini",
        "noxfile.py",
    ]
    ignored_directories = {
        ".git",
        ".venv",
        ".pytest_cache",
        ".ruff_cache",
        ".pyright",
        "__pycache__",
    }

    for filename in forbidden_lockfiles:
        matches = [
            path
            for path in ROOT.rglob(filename)
            if ignored_directories.isdisjoint(path.relative_to(ROOT).parts)
        ]
        assert not matches, "Lockfile/manifesto alternativo proibido: " + ", ".join(
            str(path.relative_to(ROOT)) for path in matches
        )


def test_workspace_member_directories_do_not_contain_unconfigured_projects() -> None:
    for container in ["services", "packages"]:
        for child in (ROOT / container).iterdir():
            if child.name.startswith("."):
                assert child.name == ".gitkeep", (
                    f"Placeholder oculto não permitido em workspace: {child.relative_to(ROOT)}"
                )
                continue

            assert child.is_dir(), f"{container}/ deve conter apenas diretórios de workspace"
            assert (child / "pyproject.toml").is_file(), (
                f"Membro de workspace sem pyproject.toml: {child.relative_to(ROOT)}"
            )


if __name__ == "__main__":
    test_required_root_directories_exist()
    test_python_baseline_and_workspace_configuration()
    test_single_uv_lockfile_policy()
    test_workspace_member_directories_do_not_contain_unconfigured_projects()
