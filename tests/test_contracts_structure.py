from __future__ import annotations

import shutil
import subprocess
import sys
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CONTRACTS = ROOT / "packages" / "contracts"
CONTRACT_CHECK = ROOT / "scripts" / "check_contracts.py"

REQUIRED_CONTRACT_DIRECTORIES = [
    "catalog",
    "openapi/public",
    "protobuf/internal",
    "asyncapi/events",
    "schemas",
    "consumer-expectations",
    "src/creditos_contracts",
]


def run_contract_check(contracts_root: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(CONTRACT_CHECK), "--contracts-root", str(contracts_root)],
        check=False,
        cwd=ROOT,
        text=True,
        capture_output=True,
    )


def copy_contracts_fixture(tmp_path: Path) -> Path:
    contracts_root = tmp_path / "contracts"
    ignore = shutil.ignore_patterns("__pycache__", "*.pyc", ".pytest_cache")
    shutil.copytree(CONTRACTS, contracts_root, ignore=ignore)
    return contracts_root


def read_catalog(contracts_root: Path) -> str:
    return (contracts_root / "catalog" / "contracts.toml").read_text(encoding="utf-8")


def write_catalog(contracts_root: Path, content: str) -> None:
    (contracts_root / "catalog" / "contracts.toml").write_text(content, encoding="utf-8")


def test_contracts_package_is_workspace_member() -> None:
    pyproject_path = CONTRACTS / "pyproject.toml"
    assert pyproject_path.is_file(), "`packages/contracts` deve ser membro do workspace uv"

    pyproject = tomllib.loads(pyproject_path.read_text(encoding="utf-8"))

    assert pyproject["project"]["name"] == "creditos-contracts"
    assert pyproject["project"]["requires-python"] == ">=3.13"
    assert pyproject["project"]["dependencies"] == []
    assert pyproject["build-system"]["build-backend"] == "setuptools.build_meta"
    assert pyproject["tool"]["setuptools"]["packages"]["find"]["where"] == ["src"]
    assert (CONTRACTS / "src" / "creditos_contracts" / "__init__.py").is_file()


def test_contracts_have_standard_versioned_directories() -> None:
    for relative_directory in REQUIRED_CONTRACT_DIRECTORIES:
        assert (CONTRACTS / relative_directory).is_dir(), (
            f"Diretório obrigatório de contratos ausente: {relative_directory}"
        )


def test_contract_governance_check_passes_for_repository_contracts() -> None:
    result = run_contract_check(CONTRACTS)

    assert result.returncode == 0, result.stderr

    catalog = tomllib.loads((CONTRACTS / "catalog" / "contracts.toml").read_text(encoding="utf-8"))
    expected_count = len(catalog["contracts"])
    assert f"contracts check passed: {expected_count} contracts" in result.stdout


def test_contract_governance_check_rejects_duplicate_ids(tmp_path: Path) -> None:
    contracts_root = copy_contracts_fixture(tmp_path)
    write_catalog(
        contracts_root,
        read_catalog(contracts_root).replace(
            'id = "identity-tenant-context-grpc"',
            'id = "proposal-intake-public-api"',
            1,
        ),
    )

    result = run_contract_check(contracts_root)

    assert result.returncode == 1
    assert "duplicado por id" in result.stderr


def test_contract_governance_check_rejects_kind_path_mismatch(tmp_path: Path) -> None:
    contracts_root = copy_contracts_fixture(tmp_path)
    write_catalog(
        contracts_root,
        read_catalog(contracts_root).replace(
            'kind = "openapi"',
            'kind = "asyncapi"',
            1,
        ),
    )

    result = run_contract_check(contracts_root)

    assert result.returncode == 1
    assert "Path de asyncapi deve iniciar" in result.stderr


def test_contract_governance_check_rejects_malformed_json_object(tmp_path: Path) -> None:
    contracts_root = copy_contracts_fixture(tmp_path)
    (contracts_root / "openapi" / "public" / "proposal-intake" / "v1" / "openapi.json").write_text(
        '["not-an-object"]',
        encoding="utf-8",
    )

    result = run_contract_check(contracts_root)

    assert result.returncode == 1
    assert "JSON raiz deve ser objeto" in result.stderr


def test_contract_governance_check_rejects_incomplete_openapi_guardrails(tmp_path: Path) -> None:
    contracts_root = copy_contracts_fixture(tmp_path)
    (contracts_root / "openapi" / "public" / "proposal-intake" / "v1" / "openapi.json").write_text(
        '{"openapi":"3.1.0","info":{"version":"v1"},"paths":{},"components":{"schemas":{}}}',
        encoding="utf-8",
    )

    result = run_contract_check(contracts_root)

    assert result.returncode == 1
    assert "ErrorResponse" in result.stderr


def test_contract_governance_check_rejects_incomplete_asyncapi_cloudevent(tmp_path: Path) -> None:
    contracts_root = copy_contracts_fixture(tmp_path)
    asyncapi_path = contracts_root / "asyncapi" / "events" / "proposal" / "v1" / "asyncapi.json"
    content = asyncapi_path.read_text(encoding="utf-8").replace('"tenantid",', "")
    asyncapi_path.write_text(content, encoding="utf-8")

    result = run_contract_check(contracts_root)

    assert result.returncode == 1
    assert "CloudEvent deve exigir extensões CreditOS" in result.stderr


def test_contract_governance_check_rejects_proto_without_grpc_service(tmp_path: Path) -> None:
    contracts_root = copy_contracts_fixture(tmp_path)
    proto_path = (
        contracts_root / "protobuf" / "internal" / "identity-tenant" / "v1" / "tenant_context.proto"
    )
    content = proto_path.read_text(encoding="utf-8")
    service_definition = (
        "service TenantContextService {\n"
        "  rpc ResolveTenantContext(TenantContextRequest) returns (TenantContextResponse);\n"
        "}\n\n"
    )
    content = content.replace(
        service_definition,
        "",
    )
    proto_path.write_text(content, encoding="utf-8")

    result = run_contract_check(contracts_root)

    assert result.returncode == 1
    assert "service gRPC" in result.stderr


def test_contract_governance_check_rejects_weak_breaking_controls(tmp_path: Path) -> None:
    contracts_root = copy_contracts_fixture(tmp_path)
    content = read_catalog(contracts_root).replace(
        'compatibility = "backward-compatible"',
        'compatibility = "breaking"\nreplacement_version = "v1"\nmigration_plan = "to-be-defined"',
        1,
    )
    write_catalog(contracts_root, content)

    result = run_contract_check(contracts_root)

    assert result.returncode == 1
    assert "versão sucessora maior" in result.stderr
