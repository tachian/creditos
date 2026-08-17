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
PROPOSAL_SCHEMA_PATH = "schemas/proposal/v1/proposal.schema.json"
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
    proposal_path = paths.get("/v1/proposals")
    if not isinstance(proposal_path, dict) or "post" not in proposal_path:
        return

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

    for message_name, message in messages.items():
        if message_name != "ProposalSubmitted":
            continue
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
            f"AsyncAPI ProposalSubmitted payload deve ser object: {path}",
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
            payload.get("additionalProperties") is False,
            f"AsyncAPI ProposalSubmitted payload deve ser fechado: {path}",
        )
        require(
            data.get("additionalProperties") is False,
            f"AsyncAPI ProposalSubmitted data deve ser fechado: {path}",
        )
        return

    require(False, f"AsyncAPI deve declarar mensagem ProposalSubmitted: {path}")


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
