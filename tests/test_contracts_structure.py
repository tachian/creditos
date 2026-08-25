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
INTEGRATION_ASYNCAPI = CONTRACTS / "asyncapi" / "events" / "integration" / "v1" / "asyncapi.json"
INTEGRATION_RESULT_SCHEMA = (
    CONTRACTS / "schemas" / "integration" / "v1" / "integration-result.schema.json"
)
INTEGRATION_COST_SCHEMA = (
    CONTRACTS / "schemas" / "integration" / "v1" / "integration-cost.schema.json"
)
INTEGRATION_DLQ_SCHEMA = (
    CONTRACTS / "schemas" / "integration" / "v1" / "integration-dlq.schema.json"
)
INTEGRATION_RETRY_SCHEMA = (
    CONTRACTS / "schemas" / "integration" / "v1" / "integration-retry.schema.json"
)
INTEGRATION_CONSUMER_EXPECTATIONS = (
    CONTRACTS / "consumer-expectations" / "integration-events" / "v1" / "README.md"
)
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
    "custom",
    "metadata",
    "attributes",
}
INTEGRATION_EVENT_TYPES = {
    "creditos.integration.execution.requested.v1",
    "creditos.integration.execution.completed.v1",
    "creditos.integration.execution.partial.v1",
    "creditos.integration.execution.failed.v1",
    "creditos.integration.job.retry_scheduled.v1",
    "creditos.integration.job.dlq_recorded.v1",
    "creditos.integration.job.reprocess_requested.v1",
    "creditos.integration.execution.cost_recorded.v1",
}
INTEGRATION_FORBIDDEN_FIELDS = {
    "address",
    "attributes",
    "authorization",
    "cnpj",
    "cpf",
    "custom",
    "document",
    "email",
    "exception",
    "headers",
    "legal_name",
    "metadata",
    "name",
    "payload",
    "phone",
    "provider_payload",
    "provider_response",
    "raw_payload",
    "request_body",
    "response_body",
    "secret",
    "stack_trace",
    "street",
    "token",
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


def test_proposal_submitted_asyncapi_defines_minimized_event_data() -> None:
    asyncapi = load_json(CONTRACTS / "asyncapi" / "events" / "proposal" / "v1" / "asyncapi.json")
    payload = asyncapi["components"]["messages"]["ProposalSubmitted"]["payload"]
    data = payload["properties"]["data"]

    assert payload["properties"]["type"]["const"] == "creditos.proposal.v1.submitted"
    assert payload["properties"]["source"]["const"] == "creditos://proposal-intake"
    assert payload["properties"]["dataschema"]["const"] == (
        "creditos://contracts/asyncapi/events/proposal/v1"
    )
    assert set(data["required"]) >= {
        "proposal_id",
        "external_proposal_id",
        "product_type",
        "schema_version",
        "channel",
        "intake_status",
        "provided_data_discarded",
        "consents_discarded",
        "callback_configured",
    }
    assert "borrower" not in data["properties"]
    assert "participants" not in data["properties"]
    assert "provided_data" not in data["properties"]
    assert "consents" not in data["properties"]


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


def test_contract_governance_check_rejects_openapi_request_body_ref_drift(
    tmp_path: Path,
) -> None:
    contracts_root = copy_contracts_fixture(tmp_path)
    openapi_path = contracts_root / "openapi" / "public" / "proposal-intake" / "v1" / "openapi.json"
    openapi = load_json(openapi_path)
    operation = openapi["paths"]["/v1/proposals"]["post"]
    operation["requestBody"]["content"]["application/json"]["schema"] = {
        "$ref": "#/components/schemas/Proposal"
    }
    openapi_path.write_text(dumped(openapi), encoding="utf-8")

    result = run_contract_check(contracts_root)

    assert result.returncode == 1
    assert "deve referenciar o schema canônico de proposta" in result.stderr


def test_contract_governance_check_rejects_optional_mandatory_openapi_header(
    tmp_path: Path,
) -> None:
    contracts_root = copy_contracts_fixture(tmp_path)
    openapi_path = contracts_root / "openapi" / "public" / "proposal-intake" / "v1" / "openapi.json"
    openapi = load_json(openapi_path)
    operation = openapi["paths"]["/v1/proposals"]["post"]
    for parameter in operation["parameters"]:
        if parameter["name"] == "X-Correlation-Id":
            parameter["required"] = False
            break
    openapi_path.write_text(dumped(openapi), encoding="utf-8")

    result = run_contract_check(contracts_root)

    assert result.returncode == 1
    assert "headers obrigatórios devem ser required=true" in result.stderr


def test_contract_governance_check_rejects_extra_openapi_request_body_media_type(
    tmp_path: Path,
) -> None:
    contracts_root = copy_contracts_fixture(tmp_path)
    openapi_path = contracts_root / "openapi" / "public" / "proposal-intake" / "v1" / "openapi.json"
    openapi = load_json(openapi_path)
    operation = openapi["paths"]["/v1/proposals"]["post"]
    operation["requestBody"]["content"]["text/plain"] = {"schema": {"type": "string"}}
    openapi_path.write_text(dumped(openapi), encoding="utf-8")

    result = run_contract_check(contracts_root)

    assert result.returncode == 1
    assert "deve aceitar somente application/json" in result.stderr


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


def test_contract_governance_check_rejects_missing_runtime_forbidden_aliases(
    tmp_path: Path,
) -> None:
    contracts_root = copy_contracts_fixture(tmp_path)
    schema_path = contracts_root / "schemas" / "proposal" / "v1" / "proposal.schema.json"
    schema = load_json(schema_path)
    schema["x-creditos"]["forbiddenFields"].remove("custom")
    schema["x-creditos"]["invalidExamples"] = [
        example
        for example in schema["x-creditos"]["invalidExamples"]
        if "custom" not in set(iter_payload_keys(example))
    ]
    schema_path.write_text(dumped(schema), encoding="utf-8")

    result = run_contract_check(contracts_root)

    assert result.returncode == 1
    assert "x-creditos.forbiddenFields incompletos" in result.stderr


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


def test_contract_governance_check_rejects_open_proposal_submitted_event_data(
    tmp_path: Path,
) -> None:
    contracts_root = copy_contracts_fixture(tmp_path)
    asyncapi_path = contracts_root / "asyncapi" / "events" / "proposal" / "v1" / "asyncapi.json"
    asyncapi = load_json(asyncapi_path)
    message = asyncapi["components"]["messages"]["ProposalSubmitted"]
    message["payload"]["properties"]["data"]["additionalProperties"] = True
    asyncapi_path.write_text(dumped(asyncapi), encoding="utf-8")

    result = run_contract_check(contracts_root)

    assert result.returncode == 1
    assert "ProposalSubmitted data deve ser fechado" in result.stderr


def test_contract_governance_check_rejects_open_proposal_submitted_envelope(
    tmp_path: Path,
) -> None:
    contracts_root = copy_contracts_fixture(tmp_path)
    asyncapi_path = contracts_root / "asyncapi" / "events" / "proposal" / "v1" / "asyncapi.json"
    asyncapi = load_json(asyncapi_path)
    message = asyncapi["components"]["messages"]["ProposalSubmitted"]
    message["payload"]["additionalProperties"] = True
    asyncapi_path.write_text(dumped(asyncapi), encoding="utf-8")

    result = run_contract_check(contracts_root)

    assert result.returncode == 1
    assert "ProposalSubmitted payload deve ser fechado" in result.stderr


def test_contract_governance_check_rejects_extra_proposal_submitted_data_field(
    tmp_path: Path,
) -> None:
    contracts_root = copy_contracts_fixture(tmp_path)
    asyncapi_path = contracts_root / "asyncapi" / "events" / "proposal" / "v1" / "asyncapi.json"
    asyncapi = load_json(asyncapi_path)
    data_properties = asyncapi["components"]["messages"]["ProposalSubmitted"]["payload"][
        "properties"
    ]["data"]["properties"]
    data_properties["requested_amount"] = {"type": "integer"}
    asyncapi_path.write_text(dumped(asyncapi), encoding="utf-8")

    result = run_contract_check(contracts_root)

    assert result.returncode == 1
    assert "data deve declarar payload minimizado" in result.stderr


def test_contract_governance_check_rejects_extra_cloudevent_extension(
    tmp_path: Path,
) -> None:
    contracts_root = copy_contracts_fixture(tmp_path)
    asyncapi_path = contracts_root / "asyncapi" / "events" / "proposal" / "v1" / "asyncapi.json"
    asyncapi = load_json(asyncapi_path)
    payload = asyncapi["components"]["messages"]["ProposalSubmitted"]["payload"]
    payload["required"].append("authorization")
    payload["properties"]["authorization"] = {"type": "string"}
    asyncapi_path.write_text(dumped(asyncapi), encoding="utf-8")

    result = run_contract_check(contracts_root)

    assert result.returncode == 1
    assert "CloudEvent deve exigir extensões CreditOS" in result.stderr


def test_contract_governance_check_rejects_unstable_cloudevent_specversion(
    tmp_path: Path,
) -> None:
    contracts_root = copy_contracts_fixture(tmp_path)
    asyncapi_path = contracts_root / "asyncapi" / "events" / "proposal" / "v1" / "asyncapi.json"
    asyncapi = load_json(asyncapi_path)
    payload = asyncapi["components"]["messages"]["ProposalSubmitted"]["payload"]
    payload["properties"]["specversion"]["const"] = "1.1"
    asyncapi_path.write_text(dumped(asyncapi), encoding="utf-8")

    result = run_contract_check(contracts_root)

    assert result.returncode == 1
    assert "specversion deve ser 1.0" in result.stderr


def test_contract_governance_check_rejects_non_object_proposal_submitted_payload(
    tmp_path: Path,
) -> None:
    contracts_root = copy_contracts_fixture(tmp_path)
    asyncapi_path = contracts_root / "asyncapi" / "events" / "proposal" / "v1" / "asyncapi.json"
    asyncapi = load_json(asyncapi_path)
    message = asyncapi["components"]["messages"]["ProposalSubmitted"]
    message["payload"]["type"] = "string"
    asyncapi_path.write_text(dumped(asyncapi), encoding="utf-8")

    result = run_contract_check(contracts_root)

    assert result.returncode == 1
    assert "ProposalSubmitted payload deve ser object" in result.stderr


def test_integration_contracts_are_registered_and_versioned() -> None:
    catalog = tomllib.loads((CONTRACTS / "catalog" / "contracts.toml").read_text(encoding="utf-8"))
    contract_entries = {
        (entry["id"], entry["version"], entry["path"]) for entry in catalog["contracts"]
    }

    assert (
        "integration-events",
        "v1",
        "asyncapi/events/integration/v1/asyncapi.json",
    ) in contract_entries
    assert (
        "integration-result-schema",
        "v1",
        "schemas/integration/v1/integration-result.schema.json",
    ) in contract_entries
    assert (
        "integration-cost-schema",
        "v1",
        "schemas/integration/v1/integration-cost.schema.json",
    ) in contract_entries
    assert (
        "integration-dlq-schema",
        "v1",
        "schemas/integration/v1/integration-dlq.schema.json",
    ) in contract_entries
    assert (
        "integration-retry-schema",
        "v1",
        "schemas/integration/v1/integration-retry.schema.json",
    ) in contract_entries


def test_integration_asyncapi_defines_minimized_cloudevents() -> None:
    asyncapi = load_json(INTEGRATION_ASYNCAPI)
    messages = asyncapi["components"]["messages"]
    event_types = {
        message["payload"]["properties"]["type"]["const"] for message in messages.values()
    }

    assert asyncapi["asyncapi"] == "3.1.0"
    assert asyncapi["info"]["version"] == "v1"
    assert event_types == INTEGRATION_EVENT_TYPES

    for message_name, message in messages.items():
        payload = message["payload"]
        data = resolve_contract_ref(payload["properties"]["data"])
        data_keys = set(data["properties"])

        assert payload["type"] == "object", message_name
        assert payload["additionalProperties"] is False, message_name
        assert payload["properties"]["specversion"]["const"] == "1.0", message_name
        assert payload["properties"]["source"]["const"] == "creditos://integration", message_name
        assert payload["properties"]["dataschema"]["const"].startswith("creditos://contracts/"), (
            message_name
        )
        assert data["type"] == "object", message_name
        assert data["additionalProperties"] is False, message_name
        assert "execution_id" in data_keys, message_name
        assert data_keys.isdisjoint(INTEGRATION_FORBIDDEN_FIELDS), message_name


def test_integration_json_schemas_are_closed_and_minimized() -> None:
    for schema_path in (
        INTEGRATION_RESULT_SCHEMA,
        INTEGRATION_COST_SCHEMA,
        INTEGRATION_DLQ_SCHEMA,
        INTEGRATION_RETRY_SCHEMA,
    ):
        schema = load_json(schema_path)
        metadata = schema["x-creditos"]
        property_names = set(iter_property_names(schema))

        assert schema["$schema"] == "https://json-schema.org/draft/2020-12/schema"
        assert metadata["owner"] == "Integration"
        assert metadata["version"] == "v1"
        assert set(metadata["forbiddenFields"]) >= INTEGRATION_FORBIDDEN_FIELDS
        assert property_names.isdisjoint(INTEGRATION_FORBIDDEN_FIELDS)

        for path, object_schema in iter_object_schemas(schema):
            assert (
                object_schema.get("additionalProperties") is False
                or object_schema.get("unevaluatedProperties") is False
            ), f"Objeto governado sem fechamento: {path}"


def test_integration_schema_examples_are_governed_and_minimized() -> None:
    for schema_path in (
        INTEGRATION_RESULT_SCHEMA,
        INTEGRATION_COST_SCHEMA,
        INTEGRATION_DLQ_SCHEMA,
        INTEGRATION_RETRY_SCHEMA,
    ):
        schema = load_json(schema_path)
        examples = schema["examples"]
        invalid_examples = schema["x-creditos"]["invalidExamples"]

        assert examples, schema_path
        assert invalid_examples, schema_path
        assert all(
            not (set(iter_payload_keys(example)) & INTEGRATION_FORBIDDEN_FIELDS)
            for example in examples
        )
        assert any(
            set(iter_payload_keys(example)) & INTEGRATION_FORBIDDEN_FIELDS
            for example in invalid_examples
        )


def test_integration_consumer_expectations_cover_downstream_services() -> None:
    content = INTEGRATION_CONSUMER_EXPECTATIONS.read_text(encoding="utf-8")

    assert "Decision" in content
    assert "Audit & Evidence" in content
    assert "Reporting & Insights" in content
    assert "payload bruto" in content
    assert "fornecedor real" in content


def test_contract_governance_check_rejects_open_integration_event_data(
    tmp_path: Path,
) -> None:
    contracts_root = copy_contracts_fixture(tmp_path)
    asyncapi_path = contracts_root / "asyncapi" / "events" / "integration" / "v1" / "asyncapi.json"
    asyncapi = load_json(asyncapi_path)
    message = asyncapi["components"]["messages"]["IntegrationExecutionRequested"]
    message["payload"]["properties"]["data"]["additionalProperties"] = True
    asyncapi_path.write_text(dumped(asyncapi), encoding="utf-8")

    result = run_contract_check(contracts_root)

    assert result.returncode == 1
    assert "Integration data deve ser fechado" in result.stderr


def test_contract_governance_check_rejects_sensitive_integration_schema_field(
    tmp_path: Path,
) -> None:
    contracts_root = copy_contracts_fixture(tmp_path)
    schema_path = (
        contracts_root / "schemas" / "integration" / "v1" / "integration-result.schema.json"
    )
    schema = load_json(schema_path)
    schema["properties"]["provider_response"] = {"type": "object"}
    schema_path.write_text(dumped(schema), encoding="utf-8")

    result = run_contract_check(contracts_root)

    assert result.returncode == 1
    assert (
        "Campo proibido no schema de integração" in result.stderr
        or "Integration data não pode expor campos sensíveis" in result.stderr
    )


def test_contract_governance_check_rejects_integration_schema_without_invalid_examples(
    tmp_path: Path,
) -> None:
    contracts_root = copy_contracts_fixture(tmp_path)
    schema_path = contracts_root / "schemas" / "integration" / "v1" / "integration-cost.schema.json"
    schema = load_json(schema_path)
    schema["x-creditos"]["invalidExamples"] = []
    schema_path.write_text(dumped(schema), encoding="utf-8")

    result = run_contract_check(contracts_root)

    assert result.returncode == 1
    assert "exemplos inválidos governados" in result.stderr


def test_contract_governance_check_rejects_integration_result_schema_drift(
    tmp_path: Path,
) -> None:
    contracts_root = copy_contracts_fixture(tmp_path)
    schema_path = (
        contracts_root / "schemas" / "integration" / "v1" / "integration-result.schema.json"
    )
    schema = load_json(schema_path)
    schema["properties"]["status"]["enum"].append("unknown_status")
    schema_path.write_text(dumped(schema), encoding="utf-8")

    result = run_contract_check(contracts_root)

    assert result.returncode == 1
    assert "status divergente no schema de integração" in result.stderr


def test_contract_governance_check_rejects_integration_schema_pattern_drift(
    tmp_path: Path,
) -> None:
    contracts_root = copy_contracts_fixture(tmp_path)
    schema_path = (
        contracts_root / "schemas" / "integration" / "v1" / "integration-result.schema.json"
    )
    schema = load_json(schema_path)
    schema["$defs"]["result"]["properties"]["adapter_id"]["pattern"] = "^[a-z0-9_]{2,80}$"
    schema_path.write_text(dumped(schema), encoding="utf-8")

    result = run_contract_check(contracts_root)

    assert result.returncode == 1
    assert "pattern divergente para adapter_id" in result.stderr


def test_contract_governance_check_rejects_integration_provider_id_pattern_drift(
    tmp_path: Path,
) -> None:
    contracts_root = copy_contracts_fixture(tmp_path)
    schema_path = (
        contracts_root / "schemas" / "integration" / "v1" / "integration-result.schema.json"
    )
    schema = load_json(schema_path)
    schema["$defs"]["result"]["properties"]["provider_id"]["pattern"] = "^iprv_[a-z0-9_]{3,80}$"
    schema_path.write_text(dumped(schema), encoding="utf-8")

    result = run_contract_check(contracts_root)

    assert result.returncode == 1
    assert "pattern divergente para provider_id" in result.stderr


def test_contract_governance_check_rejects_integration_nested_required_drift(
    tmp_path: Path,
) -> None:
    contracts_root = copy_contracts_fixture(tmp_path)
    schema_path = (
        contracts_root / "schemas" / "integration" / "v1" / "integration-result.schema.json"
    )
    schema = load_json(schema_path)
    schema["$defs"]["result"]["required"].remove("result_id")
    schema_path.write_text(dumped(schema), encoding="utf-8")

    result = run_contract_check(contracts_root)

    assert result.returncode == 1
    assert "required de $defs.result divergente" in result.stderr


def test_contract_governance_check_rejects_integration_asyncapi_schema_traversal(
    tmp_path: Path,
) -> None:
    contracts_root = copy_contracts_fixture(tmp_path)
    outside_schema = tmp_path / "integration-result.schema.json"
    outside_schema.write_text(
        dumped({"type": "object", "properties": {}, "additionalProperties": False}),
        encoding="utf-8",
    )
    asyncapi_path = contracts_root / "asyncapi" / "events" / "integration" / "v1" / "asyncapi.json"
    asyncapi = load_json(asyncapi_path)
    message = asyncapi["components"]["messages"]["IntegrationExecutionCompleted"]
    message["payload"]["properties"]["data"] = {"$ref": str(outside_schema)}
    asyncapi_path.write_text(dumped(asyncapi), encoding="utf-8")

    result = run_contract_check(contracts_root)

    assert result.returncode == 1
    assert "fora de packages/contracts" in result.stderr


def test_contract_governance_check_rejects_integration_cost_cardinality_drift(
    tmp_path: Path,
) -> None:
    contracts_root = copy_contracts_fixture(tmp_path)
    schema_path = contracts_root / "schemas" / "integration" / "v1" / "integration-cost.schema.json"
    schema = load_json(schema_path)
    schema["properties"]["cost_records"].pop("minItems")
    schema_path.write_text(dumped(schema), encoding="utf-8")

    result = run_contract_check(contracts_root)

    assert result.returncode == 1
    assert "cost_records deve exigir minItems 1" in result.stderr


def load_json(path: Path) -> dict[str, Any]:
    import json

    return json.loads(path.read_text(encoding="utf-8"))


def resolve_contract_ref(schema: Mapping[str, Any]) -> Mapping[str, Any]:
    ref = schema.get("$ref")
    if not isinstance(ref, str):
        return schema

    ref_path = (INTEGRATION_ASYNCAPI.parent / ref).resolve()
    return load_json(ref_path)


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
