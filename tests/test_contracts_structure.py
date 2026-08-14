from __future__ import annotations

import shutil
import subprocess
import sys
import tomllib
from collections.abc import Iterator, Mapping
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
CONTRACTS = ROOT / "packages" / "contracts"
CONTRACT_CHECK = ROOT / "scripts" / "check_contracts.py"
PROPOSAL_SCHEMA = CONTRACTS / "schemas" / "proposal" / "v1" / "proposal.schema.json"
PROPOSAL_OPENAPI = CONTRACTS / "openapi" / "public" / "proposal-intake" / "v1" / "openapi.json"
CORE_PROPOSAL_FIELDS = {
    "schema_version",
    "external_proposal_id",
    "person_type",
    "product_type",
    "channel",
    "operation",
    "borrower",
    "product_data",
}
MVP_PRODUCT_TYPES = {"personal_credit", "bnpl", "business_credit", "receivables"}
FORBIDDEN_PROPOSAL_FIELDS = {
    "idempotency_key",
    "selected_plan",
    "plan_id",
    "extra_data",
    "tenant_id",
    "raw_payload",
    "payload",
}

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


def test_proposal_schema_defines_canonical_versioned_public_contract() -> None:
    schema = load_json(PROPOSAL_SCHEMA)

    assert schema["$schema"] == "https://json-schema.org/draft/2020-12/schema"
    assert schema["x-creditos"]["version"] == "v1"
    assert schema["x-creditos"]["owner"] == "Proposal Intake"
    assert set(schema["required"]) >= CORE_PROPOSAL_FIELDS
    assert schema["properties"]["schema_version"]["const"] == "1.0"
    assert set(schema["properties"]["person_type"]["enum"]) == {"PF", "PJ"}
    assert set(schema["properties"]["product_type"]["enum"]) == MVP_PRODUCT_TYPES
    assert "idempotency_key" not in schema["properties"]
    assert "selected_plan" not in set(iter_property_names(schema))
    assert "plan_id" not in set(iter_property_names(schema))


def test_proposal_schema_closes_governed_objects_and_product_extensions() -> None:
    schema = load_json(PROPOSAL_SCHEMA)

    for path, object_schema in iter_object_schemas(schema):
        assert (
            object_schema.get("additionalProperties") is False
            or object_schema.get("unevaluatedProperties") is False
        ), f"Objeto governado sem fechamento: {path}"

    product_data = schema["$defs"]["product_data"]
    product_refs = dumped(product_data)
    for product_type in MVP_PRODUCT_TYPES:
        assert product_type in product_refs

    forbidden_properties = set(iter_property_names(schema)) & FORBIDDEN_PROPOSAL_FIELDS
    assert forbidden_properties == set()


def test_proposal_openapi_references_canonical_schema_in_submit_request_body() -> None:
    openapi = load_json(PROPOSAL_OPENAPI)
    operation = openapi["paths"]["/v1/proposals"]["post"]

    assert operation["requestBody"]["required"] is True
    proposal_ref = operation["requestBody"]["content"]["application/json"]["schema"]["$ref"]
    assert proposal_ref == "../../../../schemas/proposal/v1/proposal.schema.json"
    idempotency_header = next(
        parameter for parameter in operation["parameters"] if parameter["name"] == "Idempotency-Key"
    )
    assert idempotency_header["required"] is True
    assert idempotency_header["schema"]["minLength"] >= 8
    assert operation["summary"] == "Submissão pública canônica de proposta v1"


def test_proposal_schema_examples_cover_mvp_products_pf_pj_and_rejections() -> None:
    schema = load_json(PROPOSAL_SCHEMA)
    examples = schema["examples"]
    invalid_examples = schema["x-creditos"]["invalidExamples"]

    assert {example["product_type"] for example in examples} == MVP_PRODUCT_TYPES
    assert {example["person_type"] for example in examples} >= {"PF", "PJ"}
    assert {example["product_type"] for example in invalid_examples} >= {"credit_card"}
    covered_forbidden_fields = {
        key
        for example in invalid_examples
        for key in iter_payload_keys(example)
        if key in FORBIDDEN_PROPOSAL_FIELDS
    }
    assert covered_forbidden_fields >= FORBIDDEN_PROPOSAL_FIELDS
    assert any(
        "callback" in example and "url" in example["callback"] for example in invalid_examples
    )


def test_contract_governance_check_rejects_proposal_schema_forbidden_fields(tmp_path: Path) -> None:
    contracts_root = copy_contracts_fixture(tmp_path)
    schema_path = contracts_root / "schemas" / "proposal" / "v1" / "proposal.schema.json"
    schema = load_json(schema_path)
    schema["properties"]["selected_plan"] = {"type": "object"}
    schema_path.write_text(dumped(schema), encoding="utf-8")

    result = run_contract_check(contracts_root)

    assert result.returncode == 1
    assert "Campo proibido no schema de proposta" in result.stderr


def test_contract_governance_check_rejects_proposal_schema_outside_mvp(tmp_path: Path) -> None:
    contracts_root = copy_contracts_fixture(tmp_path)
    schema_path = contracts_root / "schemas" / "proposal" / "v1" / "proposal.schema.json"
    schema = load_json(schema_path)
    schema["properties"]["product_type"]["enum"].append("credit_card")
    schema_path.write_text(dumped(schema), encoding="utf-8")

    result = run_contract_check(contracts_root)

    assert result.returncode == 1
    assert "Produtos MVP divergentes" in result.stderr


def test_contract_governance_check_rejects_proposal_example_document_mismatch(
    tmp_path: Path,
) -> None:
    contracts_root = copy_contracts_fixture(tmp_path)
    schema_path = contracts_root / "schemas" / "proposal" / "v1" / "proposal.schema.json"
    schema = load_json(schema_path)
    schema["examples"][0]["borrower"]["document"] = "00000000000191"
    schema_path.write_text(dumped(schema), encoding="utf-8")

    result = run_contract_check(contracts_root)

    assert result.returncode == 1
    assert "borrower.document deve ter 11 dígitos para CPF" in result.stderr


def test_contract_governance_check_rejects_sensitive_external_proposal_id(
    tmp_path: Path,
) -> None:
    contracts_root = copy_contracts_fixture(tmp_path)
    schema_path = contracts_root / "schemas" / "proposal" / "v1" / "proposal.schema.json"
    schema = load_json(schema_path)
    schema["examples"][0]["external_proposal_id"] = "12345678901"
    schema_path.write_text(dumped(schema), encoding="utf-8")

    result = run_contract_check(contracts_root)

    assert result.returncode == 1
    assert "external_proposal_id não pode parecer CPF" in result.stderr


def test_contract_governance_check_rejects_product_data_mismatch(
    tmp_path: Path,
) -> None:
    contracts_root = copy_contracts_fixture(tmp_path)
    schema_path = contracts_root / "schemas" / "proposal" / "v1" / "proposal.schema.json"
    schema = load_json(schema_path)
    schema["examples"][1]["product_data"]["personal_credit"] = {}
    schema_path.write_text(dumped(schema), encoding="utf-8")

    result = run_contract_check(contracts_root)

    assert result.returncode == 1
    assert "product_data deve conter exatamente o bloco do product_type" in result.stderr


def test_contract_governance_check_rejects_free_callback_url(
    tmp_path: Path,
) -> None:
    contracts_root = copy_contracts_fixture(tmp_path)
    schema_path = contracts_root / "schemas" / "proposal" / "v1" / "proposal.schema.json"
    schema = load_json(schema_path)
    schema["examples"][2]["callback"] = {"url": "http://127.0.0.1/internal"}
    schema_path.write_text(dumped(schema), encoding="utf-8")

    result = run_contract_check(contracts_root)

    assert result.returncode == 1
    assert "callback.url não é permitido" in result.stderr


def test_contract_governance_check_rejects_underidentified_critical_participant(
    tmp_path: Path,
) -> None:
    contracts_root = copy_contracts_fixture(tmp_path)
    schema_path = contracts_root / "schemas" / "proposal" / "v1" / "proposal.schema.json"
    schema = load_json(schema_path)
    schema["examples"][3]["participants"][0] = {"participant_ref": "payer-001", "role": "payer"}
    schema_path.write_text(dumped(schema), encoding="utf-8")

    result = run_contract_check(contracts_root)

    assert result.returncode == 1
    assert "papel crítico sem identificação completa" in result.stderr


def load_json(path: Path) -> dict[str, Any]:
    import json

    return json.loads(path.read_text(encoding="utf-8"))


def dumped(value: object) -> str:
    import json

    return json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True)


def iter_property_names(value: object) -> Iterator[str]:
    if isinstance(value, Mapping):
        properties = value.get("properties", {})
        if isinstance(properties, Mapping):
            yield from (str(property_name) for property_name in properties)
        for nested_value in value.values():
            yield from iter_property_names(nested_value)
    elif isinstance(value, list):
        for nested_value in value:
            yield from iter_property_names(nested_value)


def iter_payload_keys(value: object) -> Iterator[str]:
    if isinstance(value, Mapping):
        for key, nested_value in value.items():
            yield str(key)
            yield from iter_payload_keys(nested_value)
    elif isinstance(value, list):
        for nested_value in value:
            yield from iter_payload_keys(nested_value)


def iter_object_schemas(value: object, path: str = "$") -> Iterator[tuple[str, Mapping[str, Any]]]:
    if isinstance(value, Mapping):
        is_object_schema = value.get("type") == "object"
        if is_object_schema:
            yield path, value
        for key, nested_value in value.items():
            yield from iter_object_schemas(nested_value, f"{path}.{key}")
    elif isinstance(value, list):
        for index, nested_value in enumerate(value):
            yield from iter_object_schemas(nested_value, f"{path}[{index}]")
