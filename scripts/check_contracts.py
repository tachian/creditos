#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
import sys
import tomllib
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
    "tenantid",
    "correlationid",
    "idempotencykey",
    "schemaversion",
    "traceparent",
}
OPENAPI_REQUIRED_HEADER_PARAMETERS = {"X-Correlation-Id", "X-Request-Id", "Idempotency-Key"}
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
    seen_ids: set[str] = set()
    seen_paths: set[str] = set()
    seen_contract_keys: set[tuple[str, str]] = set()

    for entry in entries:
        contract_id = str(entry.get("id", ""))
        version = str(entry.get("version", ""))
        path = str(entry.get("path", ""))
        contract_key = (contract_id, version)

        require(contract_id not in seen_ids, f"Contrato duplicado por id: {contract_id}")
        require(path not in seen_paths, f"Contrato duplicado por path: {path}")
        require(
            contract_key not in seen_contract_keys,
            f"Contrato duplicado por id/version: {contract_id} {version}",
        )

        seen_ids.add(contract_id)
        seen_paths.add(path)
        seen_contract_keys.add(contract_key)


def validate_contract_path(contracts_root: Path, kind: str, version: str, raw_path: str) -> Path:
    contract_path = (contracts_root / raw_path).resolve()
    relative_parts = Path(raw_path).parts
    expected_prefix, expected_suffix = KIND_PATH_RULES[kind]

    require(contract_path.is_file(), f"Arquivo de contrato ausente: {display_path(contract_path)}")
    require(
        contract_path.is_relative_to(contracts_root.resolve()),
        f"Path fora de packages/contracts: {raw_path}",
    )
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
        require(
            header_parameters >= OPENAPI_REQUIRED_HEADER_PARAMETERS,
            f"OpenAPI operação deve declarar headers de rastreabilidade/idempotência: {path}",
        )
        require(
            set(responses) >= OPENAPI_REQUIRED_RESPONSES,
            "OpenAPI operação deve declarar respostas padrão "
            f"{sorted(OPENAPI_REQUIRED_RESPONSES)}: {path}",
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

    for message in messages.values():
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
            set(required) >= CLOUDEVENT_REQUIRED_FIELDS,
            f"AsyncAPI CloudEvent deve exigir extensões CreditOS: {path}",
        )
        require(
            set(properties) >= CLOUDEVENT_REQUIRED_FIELDS,
            f"AsyncAPI CloudEvent deve declarar propriedades CreditOS: {path}",
        )


def validate_json_schema_contract(path: Path, version: str) -> None:
    contract = load_json_object(path)
    creditos_metadata = require_dict(
        contract.get("x-creditos"), f"JSON Schema x-creditos deve ser objeto: {path}"
    )

    require(
        contract.get("$schema") == "https://json-schema.org/draft/2020-12/schema",
        f"JSON Schema deve declarar draft 2020-12: {path}",
    )
    require(creditos_metadata.get("version") == version, f"Versão JSON Schema divergente: {path}")


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
        validate_json_schema_contract(contract_path, version)
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
