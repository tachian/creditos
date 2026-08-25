#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
import sys
import tomllib
from collections.abc import Iterator
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CONTRACTS = ROOT / "packages" / "contracts"

REQUIRED_METADATA = {
    "id",
    "kind",
    "version",
    "owner",
    "path",
    "compatibility",
    "breaking_change_policy",
}
ALLOWED_KINDS = {"openapi", "protobuf", "asyncapi", "json-schema"}
ALLOWED_COMPATIBILITY = {"backward-compatible", "breaking", "experimental"}
ALLOWED_BREAKING_POLICIES = {"new-major-version-required"}
VERSION_PATTERN = re.compile(r"^v([1-9][0-9]*)$")
PLACEHOLDER_VALUES = {"", "todo", "tbd", "to-be-defined", "to-be-defined-before-production"}
CLOUDEVENT_REQUIRED_FIELDS = {
    "specversion",
    "id",
    "source",
    "type",
    "subject",
    "time",
    "datacontenttype",
    "dataschema",
    "tenantid",
    "tenanttier",
    "subjectid",
    "clientid",
    "principaltype",
    "scopes",
    "correlationid",
    "requestid",
    "idempotencykey",
    "schemaversion",
    "traceparent",
    "data",
}
CLOUDEVENT_OPTIONAL_FIELDS = {"roles"}
PROPOSAL_SUBMITTED_DATA_FIELDS = {
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
PROPOSAL_SUBMITTED_FORBIDDEN_DATA_FIELDS = {
    "authorization",
    "borrower",
    "consents",
    "customer",
    "declared_monthly_debt",
    "declared_monthly_income",
    "document",
    "email",
    "name",
    "participants",
    "password",
    "provided_data",
    "secret",
    "token",
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
INTEGRATION_EXECUTION_STATUSES = {"completed", "partial", "failed"}
INTEGRATION_RESULT_STATUSES = {"completed", "partial", "not_found", "failed"}
INTEGRATION_CLASSES = {"kyc_kyb", "credit_bureau", "anti_fraud", "receivables"}
INTEGRATION_SYNTHETIC_SCENARIOS = {
    "synthetic_success",
    "synthetic_partial",
    "synthetic_not_found",
    "synthetic_failure",
}
INTEGRATION_FAILURE_CLASSES = {"recoverable", "non_recoverable", "timeout", "invalid_result"}
INTEGRATION_FALLBACK_STRATEGIES = {"fail_closed", "allow_partial", "skip_optional"}
INTEGRATION_ID_PATTERNS = {
    "execution_id": r"^iexec_[a-f0-9]{32}$",
    "job_id": r"^ijob_[a-f0-9]{32}$",
    "result_id": r"^ires_[a-f0-9]{32}$",
    "dlq_id": r"^idlq_[a-f0-9]{32}$",
    "adapter_id": r"^[a-z0-9][a-z0-9_.-]{2,80}$",
    "trace_id": r"^[0-9a-f]{32}$",
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
PROPOSAL_SCHEMA_PATH = "schemas/proposal/v1/proposal.schema.json"
INTEGRATION_SCHEMA_PREFIX = "schemas/integration/v1/"
PROPOSAL_REQUIRED_FIELDS = {
    "schema_version",
    "external_proposal_id",
    "person_type",
    "product_type",
    "channel",
    "operation",
    "borrower",
    "product_data",
}
PROPOSAL_MVP_PRODUCTS = {"personal_credit", "bnpl", "business_credit", "receivables"}
PROPOSAL_PERSON_TYPES = {"PF", "PJ"}
PROPOSAL_FORBIDDEN_FIELDS = {
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
PROPOSAL_CHANNELS = {"api", "batch", "portal", "partner", "checkout", "backoffice"}
PROPOSAL_CRITICAL_PARTICIPANT_ROLES = {
    "beneficial_owner",
    "co_borrower",
    "guarantor",
    "legal_representative",
    "payer",
    "shareholder",
}
PROPOSAL_MONEY_MAX = 1_000_000_000_000
PROPOSAL_SENSITIVE_DIGITS = re.compile(r"^\d{10,15}$")
OPENAPI_REQUIRED_HEADER_PARAMETERS = {"X-Correlation-Id", "X-Request-Id", "Idempotency-Key"}
OPENAPI_MANDATORY_HEADER_PARAMETERS = OPENAPI_REQUIRED_HEADER_PARAMETERS
PROPOSAL_OPENAPI_REQUEST_REF = "../../../../schemas/proposal/v1/proposal.schema.json"
OPENAPI_REQUIRED_RESPONSES = {"202", "400", "401", "409", "500"}
KIND_PATH_RULES = {
    "openapi": (("openapi", "public"), ".json"),
    "protobuf": (("protobuf", "internal"), ".proto"),
    "asyncapi": (("asyncapi", "events"), ".json"),
    "json-schema": (("schemas",), ".schema.json"),
}


class ContractCheckError(Exception):
    pass


def display_path(path: Path) -> str:
    try:
        return str(path.relative_to(ROOT))
    except ValueError:
        return str(path)


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ContractCheckError(message)


def require_dict(value: Any, message: str) -> dict[str, Any]:
    require(isinstance(value, dict), message)
    return value


def non_placeholder(value: object) -> bool:
    return str(value).strip().lower() not in PLACEHOLDER_VALUES


def version_number(version: str) -> int:
    match = VERSION_PATTERN.match(version)
    if match is None:
        raise ContractCheckError(f"Versão inválida: {version}")
    return int(match.group(1))


def load_entries(catalog_path: Path) -> list[dict[str, Any]]:
    if not catalog_path.is_file():
        raise ContractCheckError(f"Catálogo ausente: {display_path(catalog_path)}")

    catalog = tomllib.loads(catalog_path.read_text(encoding="utf-8"))
    entries = catalog.get("contracts")

    if not isinstance(entries, list) or not entries:
        raise ContractCheckError("Catálogo deve declarar ao menos uma entrada [[contracts]]")

    for entry in entries:
        require(isinstance(entry, dict), "Cada item de [[contracts]] deve ser uma tabela TOML")

    return entries


def validate_unique_entries(entries: list[dict[str, Any]]) -> None:
    seen_paths: set[str] = set()
    seen_contract_keys: set[tuple[str, str]] = set()

    for entry in entries:
        contract_id = str(entry.get("id", ""))
        version = str(entry.get("version", ""))
        path = str(entry.get("path", ""))
        contract_key = (contract_id, version)

        require(
            contract_key not in seen_contract_keys,
            f"Contrato duplicado por id/version: {contract_id} {version}",
        )
        require(path not in seen_paths, f"Contrato duplicado por path: {path}")

        seen_paths.add(path)
        seen_contract_keys.add(contract_key)


def validate_contract_path(contracts_root: Path, kind: str, version: str, raw_path: str) -> Path:
    contract_path = (contracts_root / raw_path).resolve()
    relative_parts = Path(raw_path).parts
    expected_prefix, expected_suffix = KIND_PATH_RULES[kind]

    require(
        contract_path.is_relative_to(contracts_root.resolve()),
        f"Path fora do diretório de contratos {contracts_root}: {raw_path}",
    )
    require(contract_path.is_file(), f"Arquivo de contrato ausente: {display_path(contract_path)}")
    require(
        relative_parts[: len(expected_prefix)] == expected_prefix,
        f"Path de {kind} deve iniciar com {'/'.join(expected_prefix)}: {raw_path}",
    )
    require(
        version in relative_parts, f"Path deve incluir segmento de versão {version}: {raw_path}"
    )
    require(
        raw_path.endswith(expected_suffix),
        f"Path de {kind} deve terminar com {expected_suffix}: {raw_path}",
    )

    return contract_path


def load_json_object(path: Path) -> dict[str, Any]:
    return require_dict(
        json.loads(path.read_text(encoding="utf-8")), f"JSON raiz deve ser objeto: {path}"
    )


def validate_openapi_contract(path: Path, version: str) -> None:
    contract = load_json_object(path)
    info = require_dict(contract.get("info"), f"OpenAPI info deve ser objeto: {path}")
    paths = require_dict(contract.get("paths"), f"OpenAPI paths deve ser objeto: {path}")
    components = require_dict(
        contract.get("components"), f"OpenAPI components deve ser objeto: {path}"
    )
    schemas = require_dict(
        components.get("schemas"), f"OpenAPI components.schemas deve existir: {path}"
    )

    require(str(contract.get("openapi", "")).startswith("3."), f"OpenAPI inválido: {path}")
    require(info.get("version") == version, f"Versão OpenAPI divergente: {path}")
    require("ErrorResponse" in schemas, f"OpenAPI deve definir ErrorResponse: {path}")

    operations = [
        operation
        for item in paths.values()
        if isinstance(item, dict)
        for operation in item.values()
        if isinstance(operation, dict)
    ]
    require(bool(operations), f"OpenAPI deve declarar ao menos uma operação: {path}")

    for operation in operations:
        responses = require_dict(
            operation.get("responses"), f"OpenAPI operação sem responses: {path}"
        )
        parameters = operation.get("parameters", [])
        require(isinstance(parameters, list), f"OpenAPI parameters deve ser lista: {path}")
        header_parameters = {
            parameter.get("name")
            for parameter in parameters
            if isinstance(parameter, dict) and parameter.get("in") == "header"
        }
        headers_by_name = {
            str(parameter.get("name")): parameter
            for parameter in parameters
            if isinstance(parameter, dict) and parameter.get("in") == "header"
        }
        require(
            header_parameters >= OPENAPI_REQUIRED_HEADER_PARAMETERS,
            f"OpenAPI operação deve declarar headers de rastreabilidade/idempotência: {path}",
        )
        optional_mandatory_headers = {
            header_name
            for header_name in OPENAPI_MANDATORY_HEADER_PARAMETERS
            if headers_by_name.get(header_name, {}).get("required") is not True
        }
        require(
            not optional_mandatory_headers,
            "OpenAPI headers obrigatórios devem ser required=true: "
            f"{sorted(optional_mandatory_headers)} em {path}",
        )
        idempotency_header = require_dict(
            headers_by_name.get("Idempotency-Key"),
            f"OpenAPI operação deve declarar Idempotency-Key como header: {path}",
        )
        idempotency_schema = require_dict(
            idempotency_header.get("schema"),
            f"OpenAPI Idempotency-Key deve declarar schema: {path}",
        )
        min_length = idempotency_schema.get("minLength")
        require(
            isinstance(min_length, int) and min_length >= 8,
            f"OpenAPI Idempotency-Key deve exigir minLength >= 8: {path}",
        )
        require(
            set(responses) >= OPENAPI_REQUIRED_RESPONSES,
            "OpenAPI operação deve declarar respostas padrão "
            f"{sorted(OPENAPI_REQUIRED_RESPONSES)}: {path}",
        )
    validate_proposal_openapi_contract(paths, path)


def validate_proposal_openapi_contract(paths: dict[str, Any], path: Path) -> None:
    if "proposal-intake" not in path.parts:
        return
    proposal_path = paths.get("/v1/proposals")

    proposal_path = require_dict(
        proposal_path,
        f"OpenAPI Proposal Intake deve declarar /v1/proposals: {path}",
    )
    submit_operation = require_dict(
        proposal_path.get("post"),
        f"OpenAPI Proposal Intake deve declarar POST /v1/proposals: {path}",
    )
    request_body = require_dict(
        submit_operation.get("requestBody"),
        f"OpenAPI Proposal Intake deve declarar requestBody: {path}",
    )
    content = require_dict(
        request_body.get("content"),
        f"OpenAPI Proposal Intake requestBody deve declarar content: {path}",
    )
    require(
        set(content) == {"application/json"},
        f"OpenAPI Proposal Intake requestBody deve aceitar somente application/json: {path}",
    )
    json_content = require_dict(
        content.get("application/json"),
        f"OpenAPI Proposal Intake requestBody deve aceitar application/json: {path}",
    )
    schema = require_dict(
        json_content.get("schema"),
        f"OpenAPI Proposal Intake requestBody deve declarar schema: {path}",
    )
    require(
        request_body.get("required") is True,
        f"OpenAPI Proposal Intake requestBody deve ser required=true: {path}",
    )
    require(
        schema.get("$ref") == PROPOSAL_OPENAPI_REQUEST_REF,
        f"OpenAPI Proposal Intake deve referenciar o schema canônico de proposta: {path}",
    )


def validate_asyncapi_contract(path: Path, version: str) -> None:
    contract = load_json_object(path)
    info = require_dict(contract.get("info"), f"AsyncAPI info deve ser objeto: {path}")
    servers = require_dict(contract.get("servers"), f"AsyncAPI servers deve ser objeto: {path}")
    channels = require_dict(contract.get("channels"), f"AsyncAPI channels deve ser objeto: {path}")
    operations = require_dict(
        contract.get("operations"), f"AsyncAPI operations deve ser objeto: {path}"
    )
    components = require_dict(
        contract.get("components"), f"AsyncAPI components deve ser objeto: {path}"
    )
    messages = require_dict(
        components.get("messages"), f"AsyncAPI components.messages deve existir: {path}"
    )

    require(contract.get("asyncapi") == "3.1.0", f"AsyncAPI deve usar 3.1.0: {path}")
    require(info.get("version") == version, f"Versão AsyncAPI divergente: {path}")
    require(bool(servers), f"AsyncAPI deve declarar servidor NATS JetStream estrutural: {path}")
    require(bool(channels), f"AsyncAPI deve declarar channels: {path}")
    require(bool(operations), f"AsyncAPI deve declarar operations: {path}")
    require(bool(messages), f"AsyncAPI deve declarar mensagens: {path}")

    if "proposal" in path.parts:
        validate_proposal_asyncapi_contract(path, messages)
        return

    if "integration" in path.parts:
        validate_integration_asyncapi_contract(path, messages)
        return

    raise ContractCheckError(f"AsyncAPI sem validação específica governada: {path}")


def validate_proposal_asyncapi_contract(path: Path, messages: dict[str, Any]) -> None:
    for message_name, message in messages.items():
        if message_name != "ProposalSubmitted":
            continue
        _, properties = validate_cloudevent_payload(
            message,
            path,
            message_name="ProposalSubmitted",
        )
        data = require_dict(
            properties.get("data"),
            f"AsyncAPI CloudEvent deve declarar data: {path}",
        )
        require(
            data.get("type") == "object",
            f"AsyncAPI ProposalSubmitted data deve ser object: {path}",
        )
        data_required = data.get("required", [])
        data_properties = require_dict(
            data.get("properties"), f"AsyncAPI CloudEvent data.properties deve existir: {path}"
        )
        require(
            isinstance(data_required, list)
            and set(data_required) >= PROPOSAL_SUBMITTED_DATA_FIELDS,
            f"AsyncAPI ProposalSubmitted data deve exigir payload minimizado: {path}",
        )
        require(
            set(data_properties) == PROPOSAL_SUBMITTED_DATA_FIELDS,
            f"AsyncAPI ProposalSubmitted data deve declarar payload minimizado: {path}",
        )
        require(
            data_properties.keys().isdisjoint(PROPOSAL_SUBMITTED_FORBIDDEN_DATA_FIELDS),
            f"AsyncAPI ProposalSubmitted data não pode expor dados sensíveis: {path}",
        )
        require(
            data.get("additionalProperties") is False,
            f"AsyncAPI ProposalSubmitted data deve ser fechado: {path}",
        )
        return

    require(False, f"AsyncAPI deve declarar mensagem ProposalSubmitted: {path}")


def validate_integration_asyncapi_contract(path: Path, messages: dict[str, Any]) -> None:
    observed_event_types: set[str] = set()
    for message_name, message in messages.items():
        payload, properties = validate_cloudevent_payload(
            message,
            path,
            message_name=message_name,
        )
        require(
            properties.get("source", {}).get("const") == "creditos://integration",
            f"AsyncAPI Integration source deve ser creditos://integration: {path}",
        )
        event_type = str(properties.get("type", {}).get("const", ""))
        observed_event_types.add(event_type)
        require(
            str(properties.get("dataschema", {}).get("const", "")).startswith(
                "creditos://contracts/"
            ),
            f"AsyncAPI Integration dataschema deve referenciar contratos CreditOS: {path}",
        )
        validate_integration_event_schema_binding(
            event_type=event_type,
            dataschema=str(properties.get("dataschema", {}).get("const", "")),
            data_schema=properties.get("data"),
            path=path,
            message_name=message_name,
        )
        data = resolve_schema_ref(path, properties.get("data"))
        data_properties = require_dict(
            data.get("properties"),
            f"AsyncAPI Integration data.properties deve existir em {message_name}: {path}",
        )
        require(
            data.get("type") == "object",
            f"AsyncAPI Integration data deve ser object em {message_name}: {path}",
        )
        require(
            data.get("additionalProperties") is False,
            f"AsyncAPI Integration data deve ser fechado em {message_name}: {path}",
        )
        require(
            "execution_id" in data_properties,
            f"AsyncAPI Integration data deve expor execution_id em {message_name}: {path}",
        )
        forbidden_fields = set(iter_property_names(data)) & INTEGRATION_FORBIDDEN_FIELDS
        require(
            not forbidden_fields,
            "AsyncAPI Integration data não pode expor campos sensíveis: "
            f"{sorted(forbidden_fields)} em {path}",
        )
        require(
            payload.get("additionalProperties") is False,
            f"AsyncAPI Integration payload deve ser fechado em {message_name}: {path}",
        )

    require(
        observed_event_types == INTEGRATION_EVENT_TYPES,
        "AsyncAPI Integration deve cobrir eventos esperados: "
        f"{sorted(INTEGRATION_EVENT_TYPES - observed_event_types)}",
    )


def validate_integration_event_schema_binding(
    *,
    event_type: str,
    dataschema: str,
    data_schema: Any,
    path: Path,
    message_name: str,
) -> None:
    if event_type in {
        "creditos.integration.execution.completed.v1",
        "creditos.integration.execution.partial.v1",
        "creditos.integration.execution.failed.v1",
    }:
        expected = "integration-result.schema.json"
    elif event_type == "creditos.integration.execution.cost_recorded.v1":
        expected = "integration-cost.schema.json"
    elif event_type == "creditos.integration.job.retry_scheduled.v1":
        expected = "integration-retry.schema.json"
    elif event_type in {
        "creditos.integration.job.dlq_recorded.v1",
        "creditos.integration.job.reprocess_requested.v1",
    }:
        expected = "integration-dlq.schema.json"
    else:
        return

    ref = require_dict(data_schema, f"AsyncAPI Integration data deve ser objeto: {path}").get(
        "$ref"
    )
    require(
        dataschema.endswith(expected) and isinstance(ref, str) and ref.endswith(expected),
        "AsyncAPI Integration evento referencia schema incompatível: "
        f"{message_name} -> {dataschema} / {ref}",
    )


def validate_cloudevent_payload(
    message: Any,
    path: Path,
    *,
    message_name: str,
) -> tuple[dict[str, Any], dict[str, Any]]:
    message_object = require_dict(message, f"AsyncAPI message deve ser objeto: {path}")
    payload = require_dict(
        message_object.get("payload"), f"AsyncAPI message.payload deve existir: {path}"
    )
    required = payload.get("required", [])
    properties = require_dict(
        payload.get("properties"), f"AsyncAPI payload.properties deve existir: {path}"
    )
    require(isinstance(required, list), f"AsyncAPI payload.required deve ser lista: {path}")
    require(
        payload.get("type") == "object",
        f"AsyncAPI {message_name} payload deve ser object: {path}",
    )
    require(
        set(required) == CLOUDEVENT_REQUIRED_FIELDS,
        f"AsyncAPI CloudEvent deve exigir extensões CreditOS: {path}",
    )
    require(
        set(properties) == CLOUDEVENT_REQUIRED_FIELDS | CLOUDEVENT_OPTIONAL_FIELDS,
        f"AsyncAPI CloudEvent deve declarar propriedades CreditOS: {path}",
    )
    require(
        properties.get("specversion", {}).get("const") == "1.0",
        f"AsyncAPI CloudEvent specversion deve ser 1.0: {path}",
    )
    if "integration" in path.parts:
        for field_name in CLOUDEVENT_REQUIRED_FIELDS - {"specversion", "data"}:
            field_schema = require_dict(
                properties.get(field_name),
                f"AsyncAPI CloudEvent {field_name} deve declarar schema: {path}",
            )
            if field_schema.get("type") == "string":
                require(
                    field_schema.get("minLength", 0) > 0
                    or "pattern" in field_schema
                    or "enum" in field_schema
                    or "const" in field_schema,
                    f"AsyncAPI CloudEvent {field_name} deve impedir string vazia: {path}",
                )
    require(
        payload.get("additionalProperties") is False,
        f"AsyncAPI {message_name} payload deve ser fechado: {path}",
    )
    return payload, properties


def resolve_schema_ref(base_path: Path, schema: Any) -> dict[str, Any]:
    schema_object = require_dict(schema, f"Schema referenciado deve ser objeto: {base_path}")
    ref = schema_object.get("$ref")
    if not isinstance(ref, str):
        return schema_object

    ref_path = (base_path.parent / ref).resolve()
    contracts_root = find_contracts_root(base_path)
    require(
        ref_path.is_relative_to(contracts_root.resolve()),
        f"Referência de schema fora de packages/contracts: {display_path(ref_path)}",
    )
    require(
        ref_path.is_file(),
        f"Referência de schema ausente em AsyncAPI: {display_path(ref_path)}",
    )
    return load_json_object(ref_path)


def find_contracts_root(path: Path) -> Path:
    for candidate in (path.parent, *path.parents):
        if (candidate / "catalog" / "contracts.toml").is_file():
            return candidate
    return DEFAULT_CONTRACTS


def validate_json_schema_contract(path: Path, version: str, raw_path: str) -> None:
    contract = load_json_object(path)
    creditos_metadata = require_dict(
        contract.get("x-creditos"), f"JSON Schema x-creditos deve ser objeto: {path}"
    )

    require(
        contract.get("$schema") == "https://json-schema.org/draft/2020-12/schema",
        f"JSON Schema deve declarar draft 2020-12: {path}",
    )
    require(creditos_metadata.get("version") == version, f"Versão JSON Schema divergente: {path}")
    if raw_path == PROPOSAL_SCHEMA_PATH:
        validate_proposal_schema_contract(contract, path)
    if raw_path.startswith(INTEGRATION_SCHEMA_PREFIX):
        validate_integration_schema_contract(contract, path)


def validate_integration_schema_contract(contract: dict[str, Any], path: Path) -> None:
    metadata = require_dict(
        contract.get("x-creditos"), f"Schema de integração sem x-creditos: {path}"
    )
    properties = require_dict(
        contract.get("properties"), f"Schema de integração sem properties: {path}"
    )

    require(contract.get("type") == "object", f"Schema de integração deve ter raiz object: {path}")
    require(
        contract.get("additionalProperties") is False,
        f"Schema de integração deve fechar a raiz: {path}",
    )
    require(metadata.get("owner") == "Integration", f"Owner Integration obrigatório: {path}")
    require(
        set(metadata.get("forbiddenFields", [])) >= INTEGRATION_FORBIDDEN_FIELDS,
        f"x-creditos.forbiddenFields incompletos no schema de integração: {path}",
    )
    require("execution_id" in properties, f"Schema de integração deve expor execution_id: {path}")
    forbidden_schema_fields = set(iter_property_names(contract)) & INTEGRATION_FORBIDDEN_FIELDS
    require(
        not forbidden_schema_fields,
        "Campo proibido no schema de integração: "
        f"{sorted(forbidden_schema_fields)} em {display_path(path)}",
    )
    validate_integration_canonical_field_definitions(contract, path)
    validate_governed_objects_are_closed(contract, path)
    validate_integration_examples(contract, path)


def validate_integration_canonical_field_definitions(
    contract: dict[str, Any],
    path: Path,
) -> None:
    properties = require_dict(
        contract.get("properties"), f"Schema de integração sem properties: {path}"
    )
    defs = contract.get("$defs", {})

    require_schema_pattern(
        properties, "execution_id", INTEGRATION_ID_PATTERNS["execution_id"], path
    )
    if path.name in {"integration-result.schema.json", "integration-cost.schema.json"}:
        require_enum(
            properties,
            "product_type",
            PROPOSAL_MVP_PRODUCTS,
            f"product_type divergente no schema de integração: {path}",
        )
    if "status" in properties:
        require_enum(
            properties,
            "status",
            INTEGRATION_EXECUTION_STATUSES,
            f"status divergente no schema de integração: {path}",
        )

    if path.name == "integration-result.schema.json":
        result_schema = require_dict(
            require_dict(defs, f"Schema de resultado deve declarar $defs: {path}").get("result"),
            f"Schema de resultado deve declarar $defs.result: {path}",
        )
        result_properties = require_dict(
            result_schema.get("properties"),
            f"Schema de resultado deve declarar properties do result: {path}",
        )
        require_schema_pattern(
            result_properties, "result_id", INTEGRATION_ID_PATTERNS["result_id"], path
        )
        require_schema_pattern(result_properties, "job_id", INTEGRATION_ID_PATTERNS["job_id"], path)
        require_schema_pattern(
            result_properties, "adapter_id", INTEGRATION_ID_PATTERNS["adapter_id"], path
        )
        require_enum(
            result_properties,
            "integration_class",
            INTEGRATION_CLASSES,
            f"integration_class divergente no schema de resultado: {path}",
        )
        require_enum(
            result_properties,
            "result_status",
            INTEGRATION_RESULT_STATUSES,
            f"result_status divergente no schema de resultado: {path}",
        )
        require_enum(
            result_properties,
            "synthetic_scenario",
            INTEGRATION_SYNTHETIC_SCENARIOS,
            f"synthetic_scenario divergente no schema de resultado: {path}",
        )

    if path.name == "integration-cost.schema.json":
        cost_records = require_dict(
            properties.get("cost_records"),
            f"Schema de custo deve declarar cost_records: {path}",
        )
        require(cost_records.get("minItems") == 1, f"cost_records deve exigir minItems 1: {path}")
        cost_record_schema = require_dict(
            require_dict(defs, f"Schema de custo deve declarar $defs: {path}").get("cost_record"),
            f"Schema de custo deve declarar $defs.cost_record: {path}",
        )
        cost_properties = require_dict(
            cost_record_schema.get("properties"),
            f"Schema de custo deve declarar properties do cost_record: {path}",
        )
        require_schema_pattern(cost_properties, "job_id", INTEGRATION_ID_PATTERNS["job_id"], path)
        require_schema_pattern(
            cost_properties, "adapter_id", INTEGRATION_ID_PATTERNS["adapter_id"], path
        )
        require_schema_pattern(
            cost_properties, "trace_id", INTEGRATION_ID_PATTERNS["trace_id"], path
        )
        require_enum(
            cost_properties,
            "integration_class",
            INTEGRATION_CLASSES,
            f"integration_class divergente no schema de custo: {path}",
        )
        require_enum(
            cost_properties,
            "result_status",
            INTEGRATION_RESULT_STATUSES,
            f"result_status divergente no schema de custo: {path}",
        )
        require_enum(
            cost_properties,
            "fallback_strategy",
            INTEGRATION_FALLBACK_STRATEGIES,
            f"fallback_strategy divergente no schema de custo: {path}",
        )

    if path.name in {"integration-dlq.schema.json", "integration-retry.schema.json"}:
        require_schema_pattern(properties, "job_id", INTEGRATION_ID_PATTERNS["job_id"], path)
        require_schema_pattern(
            properties, "adapter_id", INTEGRATION_ID_PATTERNS["adapter_id"], path
        )
        require_enum(
            properties,
            "integration_class",
            INTEGRATION_CLASSES,
            f"integration_class divergente no schema de DLQ: {path}",
        )
        require_enum(
            properties,
            "failure_class",
            INTEGRATION_FAILURE_CLASSES,
            f"failure_class divergente no schema de DLQ: {path}",
        )
    if path.name == "integration-dlq.schema.json":
        require_schema_pattern(properties, "dlq_id", INTEGRATION_ID_PATTERNS["dlq_id"], path)


def require_enum(
    properties: dict[str, Any],
    field_name: str,
    expected_values: set[str],
    message: str,
) -> None:
    field_schema = require_dict(
        properties.get(field_name),
        f"Campo {field_name} deve declarar schema",
    )
    require(set(field_schema.get("enum", [])) == expected_values, message)


def require_schema_pattern(
    properties: dict[str, Any],
    field_name: str,
    expected_pattern: str,
    path: Path,
) -> None:
    field_schema = require_dict(
        properties.get(field_name),
        f"Campo {field_name} deve declarar schema: {path}",
    )
    require(
        field_schema.get("pattern") == expected_pattern,
        f"pattern divergente para {field_name} no schema de integração: {path}",
    )


def validate_integration_examples(contract: dict[str, Any], path: Path) -> None:
    metadata = require_dict(
        contract.get("x-creditos"), f"Schema de integração sem x-creditos: {path}"
    )
    examples = contract.get("examples", [])
    invalid_examples = metadata.get("invalidExamples", [])

    require(
        isinstance(examples, list) and len(examples) > 0,
        f"Schema de integração deve ter exemplos: {path}",
    )
    require(
        isinstance(invalid_examples, list) and len(invalid_examples) > 0,
        f"Schema de integração deve ter exemplos inválidos governados: {path}",
    )

    for index, example in enumerate(examples):
        example_errors = validate_integration_example_shape(contract, example)
        require(
            not example_errors,
            f"Exemplo válido de integração #{index} falhou governança: {example_errors}",
        )

    invalid_outcomes = [
        validate_integration_example_shape(contract, example) for example in invalid_examples
    ]
    require(
        all(invalid_outcomes),
        f"Exemplos inválidos de integração devem ser rejeitados: {path}",
    )


def validate_integration_example_shape(
    contract: dict[str, Any],
    value: object,
) -> list[str]:
    errors = validate_schema_value(contract, value)
    if not isinstance(value, dict):
        return errors or ["exemplo deve ser objeto"]

    required = set(contract.get("required", []))
    properties = set(
        require_dict(contract.get("properties"), "Schema de integração sem properties")
    )
    missing = required - set(value)
    extra = set(value) - properties
    forbidden_fields = set(iter_payload_keys(value)) & INTEGRATION_FORBIDDEN_FIELDS

    if missing:
        errors.append(f"campos obrigatórios ausentes: {sorted(missing)}")
    if extra:
        errors.append(f"campos não governados presentes: {sorted(extra)}")
    if forbidden_fields:
        errors.append(f"campos sensíveis presentes: {sorted(forbidden_fields)}")
    if value.get("schema_version") != "1.0":
        errors.append("schema_version deve ser 1.0")

    product_type = value.get("product_type")
    if product_type is not None and product_type not in PROPOSAL_MVP_PRODUCTS:
        errors.append(f"product_type fora do MVP: {product_type}")
    errors.extend(validate_integration_example_semantics(value))

    return errors


def validate_integration_example_semantics(value: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    results = value.get("results")
    if isinstance(results, list) and value.get("result_count") != len(results):
        errors.append("result_count deve ser igual ao tamanho de results")

    cost_records = value.get("cost_records")
    if isinstance(cost_records, list):
        if value.get("job_count") != len(cost_records):
            errors.append("job_count deve ser igual ao tamanho de cost_records")
        execution_id = value.get("execution_id")
        record_execution_ids = {
            record.get("execution_id") for record in cost_records if isinstance(record, dict)
        }
        if record_execution_ids and record_execution_ids != {execution_id}:
            errors.append("cost_records não podem referenciar outra execução")
        estimated_total = sum(
            record.get("estimated_cost_units", 0)
            for record in cost_records
            if isinstance(record, dict) and type(record.get("estimated_cost_units")) is int
        )
        actual_total = sum(
            record.get("actual_cost_units", 0)
            for record in cost_records
            if isinstance(record, dict) and type(record.get("actual_cost_units")) is int
        )
        if value.get("total_estimated_cost_units") != estimated_total:
            errors.append("total_estimated_cost_units deve somar cost_records")
        if value.get("total_actual_cost_units") != actual_total:
            errors.append("total_actual_cost_units deve somar cost_records")
    return errors


def validate_schema_value(
    schema: dict[str, Any],
    value: object,
    *,
    root_schema: dict[str, Any] | None = None,
    path: str = "$",
) -> list[str]:
    root_schema = schema if root_schema is None else root_schema
    ref = schema.get("$ref")
    if isinstance(ref, str):
        return validate_schema_value(
            resolve_internal_schema_ref(root_schema, ref),
            value,
            root_schema=root_schema,
            path=path,
        )

    errors: list[str] = []
    expected_type = schema.get("type")
    allowed_types = tuple(expected_type) if isinstance(expected_type, list) else (expected_type,)
    if expected_type is not None and not schema_type_matches(allowed_types, value):
        errors.append(f"{path} deve ser {expected_type}")
        return errors

    if "const" in schema and value != schema["const"]:
        errors.append(f"{path} deve ser constante {schema['const']}")
    enum_values = schema.get("enum")
    if isinstance(enum_values, list) and value not in enum_values:
        errors.append(f"{path} deve estar em enum {enum_values}")

    if isinstance(value, str):
        min_length = schema.get("minLength")
        if isinstance(min_length, int) and len(value) < min_length:
            errors.append(f"{path} deve ter minLength >= {min_length}")
        pattern = schema.get("pattern")
        if isinstance(pattern, str) and re.fullmatch(pattern, value) is None:
            errors.append(f"{path} não atende pattern {pattern}")

    if type(value) is int:
        minimum = schema.get("minimum")
        maximum = schema.get("maximum")
        if isinstance(minimum, (int, float)) and value < minimum:
            errors.append(f"{path} deve ser >= {minimum}")
        if isinstance(maximum, (int, float)) and value > maximum:
            errors.append(f"{path} deve ser <= {maximum}")

    if isinstance(value, list):
        min_items = schema.get("minItems")
        max_items = schema.get("maxItems")
        if isinstance(min_items, int) and len(value) < min_items:
            errors.append(f"{path} deve ter minItems >= {min_items}")
        if isinstance(max_items, int) and len(value) > max_items:
            errors.append(f"{path} deve ter maxItems <= {max_items}")
        items_schema = schema.get("items")
        if isinstance(items_schema, dict):
            for index, item in enumerate(value):
                errors.extend(
                    validate_schema_value(
                        items_schema,
                        item,
                        root_schema=root_schema,
                        path=f"{path}[{index}]",
                    )
                )

    if isinstance(value, dict):
        required = schema.get("required", [])
        properties = schema.get("properties", {})
        if isinstance(required, list):
            missing = set(required) - set(value)
            if missing:
                errors.append(f"{path} campos obrigatórios ausentes: {sorted(missing)}")
        if isinstance(properties, dict):
            extra = set(value) - set(properties)
            if extra and schema.get("additionalProperties") is False:
                errors.append(f"{path} campos não governados presentes: {sorted(extra)}")
            for property_name, property_value in value.items():
                property_schema = properties.get(property_name)
                if isinstance(property_schema, dict):
                    errors.extend(
                        validate_schema_value(
                            property_schema,
                            property_value,
                            root_schema=root_schema,
                            path=f"{path}.{property_name}",
                        )
                    )
    return errors


def resolve_internal_schema_ref(root_schema: dict[str, Any], ref: str) -> dict[str, Any]:
    if not ref.startswith("#/"):
        raise ContractCheckError(f"$ref interno não suportado em exemplo de integração: {ref}")
    current: Any = root_schema
    for part in ref.removeprefix("#/").split("/"):
        current = require_dict(current, f"$ref inválido em schema de integração: {ref}").get(part)
    return require_dict(current, f"$ref inválido em schema de integração: {ref}")


def schema_type_matches(allowed_types: tuple[object, ...], value: object) -> bool:
    for expected_type in allowed_types:
        if expected_type == "object" and isinstance(value, dict):
            return True
        if expected_type == "array" and isinstance(value, list):
            return True
        if expected_type == "string" and isinstance(value, str):
            return True
        if expected_type == "integer" and type(value) is int:
            return True
        if expected_type == "number" and type(value) in {int, float}:
            return True
        if expected_type == "boolean" and isinstance(value, bool):
            return True
        if expected_type == "null" and value is None:
            return True
    return False


def validate_proposal_schema_contract(contract: dict[str, Any], path: Path) -> None:
    properties = require_dict(
        contract.get("properties"), f"Schema de proposta sem properties: {path}"
    )
    required = contract.get("required", [])
    metadata = require_dict(
        contract.get("x-creditos"), f"Schema de proposta sem x-creditos: {path}"
    )

    require(contract.get("type") == "object", f"Schema de proposta deve ter raiz object: {path}")
    require(
        contract.get("additionalProperties") is False,
        f"Schema de proposta deve fechar a raiz com additionalProperties false: {path}",
    )
    require(isinstance(required, list), f"Schema de proposta required deve ser lista: {path}")
    require(
        set(required) >= PROPOSAL_REQUIRED_FIELDS,
        f"Campos obrigatórios divergentes no schema de proposta: {path}",
    )
    require(
        properties.get("schema_version", {}).get("const") == "1.0",
        f"Schema de proposta deve exigir schema_version 1.0: {path}",
    )
    require(
        set(properties.get("person_type", {}).get("enum", [])) == PROPOSAL_PERSON_TYPES,
        f"Person types divergentes no schema de proposta: {path}",
    )
    require(
        set(properties.get("product_type", {}).get("enum", [])) == PROPOSAL_MVP_PRODUCTS,
        f"Produtos MVP divergentes no schema de proposta: {path}",
    )
    require(
        set(properties.get("channel", {}).get("enum", [])) == PROPOSAL_CHANNELS,
        f"Canais divergentes no schema de proposta: {path}",
    )
    require(
        set(metadata.get("productTypes", [])) == PROPOSAL_MVP_PRODUCTS,
        f"Metadados x-creditos.productTypes divergentes no schema de proposta: {path}",
    )
    require(
        set(metadata.get("forbiddenFields", [])) >= PROPOSAL_FORBIDDEN_FIELDS,
        f"Metadados x-creditos.forbiddenFields incompletos no schema de proposta: {path}",
    )

    forbidden_schema_fields = set(iter_property_names(contract)) & PROPOSAL_FORBIDDEN_FIELDS
    require(
        not forbidden_schema_fields,
        "Campo proibido no schema de proposta: "
        f"{sorted(forbidden_schema_fields)} em {display_path(path)}",
    )
    validate_governed_objects_are_closed(contract, path)
    validate_proposal_shape_sections(contract, path)
    validate_proposal_examples(contract, path)


def validate_governed_objects_are_closed(contract: dict[str, Any], path: Path) -> None:
    open_object_paths = [
        schema_path
        for schema_path, schema in iter_object_schemas(contract)
        if schema.get("additionalProperties") is not False
        and schema.get("unevaluatedProperties") is not False
    ]
    require(
        not open_object_paths,
        f"Objetos governados sem fechamento no schema de proposta: {open_object_paths} em {path}",
    )


def validate_proposal_shape_sections(contract: dict[str, Any], path: Path) -> None:
    defs = require_dict(contract.get("$defs"), f"Schema de proposta deve declarar $defs: {path}")
    operation = require_dict(defs.get("operation"), f"Schema de proposta sem operation: {path}")
    requested_terms = require_dict(
        defs.get("requested_terms"), f"Schema de proposta sem requested_terms: {path}"
    )
    borrower = require_dict(defs.get("borrower"), f"Schema de proposta sem borrower: {path}")
    participant = require_dict(
        defs.get("participant"), f"Schema de proposta sem participant: {path}"
    )
    product_data = require_dict(
        defs.get("product_data"), f"Schema de proposta sem product_data: {path}"
    )
    decision_options = require_dict(
        defs.get("decision_options"), f"Schema de proposta sem decision_options: {path}"
    )
    callback = require_dict(defs.get("callback"), f"Schema de proposta sem callback: {path}")

    require(
        set(operation.get("required", [])) >= {"requested_terms"},
        f"operation deve exigir requested_terms: {path}",
    )
    require(
        set(requested_terms.get("required", [])) >= {"amount", "currency"},
        f"requested_terms deve exigir amount e currency: {path}",
    )
    require(
        requested_terms.get("properties", {}).get("currency", {}).get("const") == "BRL",
        f"requested_terms.currency deve ser BRL no MVP: {path}",
    )
    require(
        requested_terms.get("properties", {}).get("amount", {}).get("maximum")
        == PROPOSAL_MONEY_MAX,
        f"requested_terms.amount deve declarar teto operacional: {path}",
    )
    require(
        set(borrower.get("properties", {}).get("document_type", {}).get("enum", []))
        == {"CPF", "CNPJ"},
        f"borrower.document_type deve limitar CPF/CNPJ: {path}",
    )
    require(
        bool(participant.get("allOf")),
        f"participant deve declarar regras condicionais por papel/documento: {path}",
    )
    require(
        set(product_data.get("properties", {})) == PROPOSAL_MVP_PRODUCTS,
        f"product_data deve conter exatamente os produtos MVP: {path}",
    )
    require(product_data.get("minProperties") == 1, f"product_data deve exigir um bloco: {path}")
    require(
        product_data.get("maxProperties") == 1,
        f"product_data deve permitir exatamente um bloco: {path}",
    )
    require(
        "manual_review"
        not in decision_options.get("properties", {}).get("review_strategy", {}).get("enum", []),
        f"decision_options não pode permitir manual_review no MVP: {path}",
    )
    callback_properties = callback.get("properties", {})
    require(
        "url" not in callback_properties,
        f"callback não pode aceitar URL livre no payload público: {path}",
    )
    require(
        set(callback.get("required", [])) >= {"callback_profile_ref"},
        f"callback deve exigir callback_profile_ref quando informado: {path}",
    )


def validate_proposal_examples(contract: dict[str, Any], path: Path) -> None:
    examples = contract.get("examples", [])
    metadata = require_dict(
        contract.get("x-creditos"), f"Schema de proposta sem x-creditos: {path}"
    )
    invalid_examples = metadata.get("invalidExamples", [])

    require(
        isinstance(examples, list) and len(examples) > 0,
        f"Schema de proposta deve ter exemplos: {path}",
    )
    require(
        isinstance(invalid_examples, list) and len(invalid_examples) > 0,
        f"Schema de proposta deve ter exemplos inválidos governados: {path}",
    )
    require(
        {example.get("product_type") for example in examples if isinstance(example, dict)}
        == PROPOSAL_MVP_PRODUCTS,
        f"Exemplos válidos devem cobrir todos os produtos MVP: {path}",
    )
    require(
        {example.get("person_type") for example in examples if isinstance(example, dict)}
        >= PROPOSAL_PERSON_TYPES,
        f"Exemplos válidos devem cobrir PF e PJ: {path}",
    )
    covered_forbidden_fields = {
        key
        for example in invalid_examples
        if isinstance(example, dict)
        for key in iter_payload_keys(example)
        if key in PROPOSAL_FORBIDDEN_FIELDS
    }
    missing_forbidden_fields = PROPOSAL_FORBIDDEN_FIELDS - covered_forbidden_fields
    require(
        not missing_forbidden_fields,
        "Exemplos inválidos devem cobrir todos os campos proibidos de proposta: "
        f"{sorted(missing_forbidden_fields)}",
    )

    for index, example in enumerate(examples):
        proposal_errors = validate_proposal_example_shape(example)
        require(
            not proposal_errors,
            f"Exemplo válido de proposta #{index} falhou governança: {proposal_errors}",
        )

    invalid_outcomes = [validate_proposal_example_shape(example) for example in invalid_examples]
    require(
        all(invalid_outcomes),
        f"Exemplos inválidos de proposta devem ser rejeitados: {path}",
    )


def validate_proposal_example_shape(value: object) -> list[str]:
    errors: list[str] = []
    if not isinstance(value, dict):
        return ["exemplo deve ser objeto"]

    missing = PROPOSAL_REQUIRED_FIELDS - set(value)
    if missing:
        errors.append(f"campos obrigatórios ausentes: {sorted(missing)}")

    forbidden_fields = set(iter_payload_keys(value)) & PROPOSAL_FORBIDDEN_FIELDS
    if forbidden_fields:
        errors.append(f"campos proibidos presentes: {sorted(forbidden_fields)}")

    external_proposal_id = value.get("external_proposal_id")
    if isinstance(external_proposal_id, str) and PROPOSAL_SENSITIVE_DIGITS.fullmatch(
        external_proposal_id
    ):
        errors.append("external_proposal_id não pode parecer CPF, CNPJ ou telefone")

    product_type = value.get("product_type")
    if product_type not in PROPOSAL_MVP_PRODUCTS:
        errors.append(f"produto fora do MVP: {product_type}")

    person_type = value.get("person_type")
    if person_type not in PROPOSAL_PERSON_TYPES:
        errors.append(f"person_type inválido: {person_type}")

    channel = value.get("channel")
    if channel not in PROPOSAL_CHANNELS:
        errors.append(f"channel inválido: {channel}")

    operation = value.get("operation", {})
    requested_terms = operation.get("requested_terms", {}) if isinstance(operation, dict) else {}
    if not isinstance(requested_terms, dict):
        errors.append("operation.requested_terms deve ser objeto")
    else:
        if requested_terms.get("currency") != "BRL":
            errors.append("currency deve ser BRL")
        amount = requested_terms.get("amount")
        if not isinstance(amount, int) or amount <= 0:
            errors.append("amount deve ser inteiro positivo")
        elif amount > PROPOSAL_MONEY_MAX:
            errors.append("amount acima do teto operacional")

    borrower = value.get("borrower", {})
    if not isinstance(borrower, dict):
        errors.append("borrower deve ser objeto")
    elif person_type == "PF":
        if borrower.get("document_type") != "CPF":
            errors.append("borrower.document_type deve ser CPF para PF")
        if not document_matches(borrower.get("document"), 11):
            errors.append("borrower.document deve ter 11 dígitos para CPF")
    elif person_type == "PJ":
        if borrower.get("document_type") != "CNPJ":
            errors.append("borrower.document_type deve ser CNPJ para PJ")
        if not document_matches(borrower.get("document"), 14):
            errors.append("borrower.document deve ter 14 dígitos para CNPJ")

    participants = value.get("participants", [])
    if not isinstance(participants, list):
        errors.append("participants deve ser lista")
    elif len(participants) > 20:
        errors.append("participants acima do limite operacional")
    else:
        for index, participant in enumerate(participants):
            validate_participant_example_shape(participant, index, errors)

    product_data = value.get("product_data", {})
    if not isinstance(product_data, dict):
        errors.append("product_data deve ser objeto")
    elif set(product_data) != {product_type}:
        errors.append("product_data deve conter exatamente o bloco do product_type")
    elif product_type == "bnpl":
        bnpl_data = product_data.get("bnpl", {})
        if isinstance(bnpl_data, dict) and "purchase_amount" in bnpl_data:
            errors.append("bnpl.purchase_amount não deve duplicar requested_terms.amount")

    decision_options = value.get("decision_options", {})
    has_manual_review = (
        isinstance(decision_options, dict)
        and decision_options.get("review_strategy") == "manual_review"
    )
    if has_manual_review:
        errors.append("manual_review não faz parte do MVP")

    callback = value.get("callback")
    if callback is not None:
        if not isinstance(callback, dict):
            errors.append("callback deve ser objeto")
        else:
            if "url" in callback:
                errors.append("callback.url não é permitido no payload público")
            if "callback_profile_ref" not in callback:
                errors.append(
                    "callback.callback_profile_ref é obrigatório quando callback é informado"
                )
            callback_events = callback.get("events", [])
            if isinstance(callback_events, list) and len(callback_events) > 20:
                errors.append("callback.events acima do limite operacional")

    return errors


def validate_participant_example_shape(value: object, index: int, errors: list[str]) -> None:
    if not isinstance(value, dict):
        errors.append(f"participants[{index}] deve ser objeto")
        return

    role = value.get("role")
    person_type = value.get("person_type")
    document_type = value.get("document_type")
    document = value.get("document")

    if person_type is not None and person_type not in PROPOSAL_PERSON_TYPES:
        errors.append(f"participants[{index}].person_type inválido: {person_type}")

    if document_type is not None and document_type not in {"CPF", "CNPJ"}:
        errors.append(f"participants[{index}].document_type inválido: {document_type}")
    if role in PROPOSAL_CRITICAL_PARTICIPANT_ROLES:
        missing = {"person_type", "document_type", "document"} - set(value)
        if missing:
            errors.append(
                f"participants[{index}] papel crítico sem identificação completa: {sorted(missing)}"
            )

    if person_type == "PF":
        if document_type != "CPF":
            errors.append(f"participants[{index}].document_type deve ser CPF para PF")
        if not document_matches(document, 11):
            errors.append(f"participants[{index}].document deve ter 11 dígitos para CPF")
        if "name" not in value:
            errors.append(f"participants[{index}].name é obrigatório para PF identificado")
    elif person_type == "PJ":
        if document_type != "CNPJ":
            errors.append(f"participants[{index}].document_type deve ser CNPJ para PJ")
        if not document_matches(document, 14):
            errors.append(f"participants[{index}].document deve ter 14 dígitos para CNPJ")
        if "legal_name" not in value:
            errors.append(f"participants[{index}].legal_name é obrigatório para PJ identificado")


def document_matches(value: object, length: int) -> bool:
    return isinstance(value, str) and value.isdigit() and len(value) == length


def iter_payload_keys(value: object) -> Iterator[str]:
    if isinstance(value, dict):
        for key, nested_value in value.items():
            yield str(key)
            yield from iter_payload_keys(nested_value)
    elif isinstance(value, list):
        for nested_value in value:
            yield from iter_payload_keys(nested_value)


def iter_property_names(value: object) -> Iterator[str]:
    if isinstance(value, dict):
        properties = value.get("properties", {})
        if isinstance(properties, dict):
            yield from (str(property_name) for property_name in properties)
        for nested_value in value.values():
            yield from iter_property_names(nested_value)
    elif isinstance(value, list):
        for nested_value in value:
            yield from iter_property_names(nested_value)


def iter_object_schemas(
    value: object, schema_path: str = "$"
) -> Iterator[tuple[str, dict[str, Any]]]:
    if isinstance(value, dict):
        if value.get("type") == "object":
            yield schema_path, value
        for key, nested_value in value.items():
            yield from iter_object_schemas(nested_value, f"{schema_path}.{key}")
    elif isinstance(value, list):
        for index, nested_value in enumerate(value):
            yield from iter_object_schemas(nested_value, f"{schema_path}[{index}]")


def validate_proto_contract(path: Path, version: str) -> None:
    lines = path.read_text(encoding="utf-8").splitlines()
    effective_lines = [
        line.strip() for line in lines if line.strip() and not line.strip().startswith("//")
    ]
    content = "\n".join(effective_lines)

    require(effective_lines[:1] == ['syntax = "proto3";'], f"Proto deve iniciar com proto3: {path}")
    require(
        f'creditos.contract.version = "{version}"' in "\n".join(lines),
        f"Proto deve declarar versão do contrato: {path}",
    )
    require(
        re.search(r"^service\s+\w+\s*{", content, re.MULTILINE) is not None,
        f"Proto deve declarar service gRPC: {path}",
    )
    require(
        re.search(r"\brpc\s+\w+\s*\(", content) is not None, f"Proto deve declarar rpc gRPC: {path}"
    )


def validate_breaking_controls(entry: dict[str, Any], contract_id: str, version: str) -> None:
    policy = str(entry["breaking_change_policy"])
    require(
        policy in ALLOWED_BREAKING_POLICIES,
        f"Política de breaking change inválida em {contract_id}: {policy}",
    )

    if entry["compatibility"] != "breaking":
        return

    replacement_version = str(entry.get("replacement_version", ""))
    migration_plan = entry.get("migration_plan", "")
    compatibility_window = entry.get("compatibility_window", "")

    require(
        VERSION_PATTERN.match(replacement_version) is not None,
        f"Breaking change em {contract_id} exige replacement_version vN",
    )
    require(
        version_number(replacement_version) > version_number(version),
        f"Breaking change em {contract_id} exige versão sucessora maior",
    )
    require(non_placeholder(migration_plan), f"Plano de migração concreto ausente em {contract_id}")
    require(
        non_placeholder(compatibility_window),
        f"Janela de compatibilidade concreta ausente em {contract_id}",
    )
    require(
        entry.get("contract_tests_required") is True,
        f"Testes de contrato obrigatórios em {contract_id}",
    )


def validate_entry(contracts_root: Path, entry: dict[str, Any]) -> None:
    missing_metadata = REQUIRED_METADATA - set(entry)
    require(
        not missing_metadata, f"Contrato sem metadados obrigatórios: {sorted(missing_metadata)}"
    )

    contract_id = str(entry["id"])
    kind = str(entry["kind"])
    version = str(entry["version"])
    compatibility = str(entry["compatibility"])
    raw_path = str(entry["path"])

    require(kind in ALLOWED_KINDS, f"Tipo de contrato inválido em {contract_id}: {kind}")
    require(
        compatibility in ALLOWED_COMPATIBILITY,
        f"Compatibilidade inválida em {contract_id}: {compatibility}",
    )
    require(
        VERSION_PATTERN.match(version) is not None, f"Versão inválida em {contract_id}: {version}"
    )
    require(str(entry["owner"]).strip() != "", f"Owner obrigatório em {contract_id}")

    validate_breaking_controls(entry, contract_id, version)
    contract_path = validate_contract_path(contracts_root, kind, version, raw_path)

    if kind == "openapi":
        validate_openapi_contract(contract_path, version)
    elif kind == "asyncapi":
        validate_asyncapi_contract(contract_path, version)
    elif kind == "json-schema":
        validate_json_schema_contract(contract_path, version, raw_path)
    else:
        validate_proto_contract(contract_path, version)


def validate_catalog(
    contracts_root: Path = DEFAULT_CONTRACTS, catalog_path: Path | None = None
) -> int:
    resolved_catalog_path = catalog_path or contracts_root / "catalog" / "contracts.toml"
    entries = load_entries(resolved_catalog_path)
    validate_unique_entries(entries)

    for entry in entries:
        validate_entry(contracts_root, entry)

    return len(entries)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Valida governança de contratos versionados")
    parser.add_argument("--contracts-root", type=Path, default=DEFAULT_CONTRACTS)
    parser.add_argument("--catalog", type=Path, default=None)
    return parser.parse_args()


def main() -> int:
    args = parse_args()

    try:
        contract_count = validate_catalog(args.contracts_root, args.catalog)
    except (ContractCheckError, json.JSONDecodeError, tomllib.TOMLDecodeError, TypeError) as error:
        print(f"contracts check failed: {error}", file=sys.stderr)
        return 1

    print(f"contracts check passed: {contract_count} contracts")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
