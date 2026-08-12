from __future__ import annotations

import re
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass

_CONTEXT_TEXT_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9:._/-]{0,127}$")
_CONTEXT_TOKEN_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9:._/-]{0,127}$")
_BRAZILIAN_DOCUMENT_PATTERN = re.compile(
    r"^(?:\d{11}|\d{14}|\d{3}\.\d{3}\.\d{3}-\d{2}|\d{2}\.\d{3}\.\d{3}/\d{4}-\d{2})$"
)
_TRACEPARENT_PATTERN = re.compile(r"^00-([0-9a-f]{32})-([0-9a-f]{16})-([0-9a-f]{2})$")
_SCHEMA_VERSION_PATTERN = re.compile(r"^v[1-9][0-9]*$")
_TENANT_ISOLATION_TIERS = frozenset({"bridge", "silo"})
_PRINCIPAL_TYPES = frozenset({"m2m", "human", "platform"})
_MAX_CONTEXT_TOKENS = 64
_SENSITIVE_METADATA_KEYS = frozenset({"authorization", "x-authorization", "cookie"})
_SENSITIVE_CLOUDEVENT_KEYS = frozenset(
    {"authorization", "token", "accesstoken", "refreshtoken", "secret", "payload", "data"}
)
_SENSITIVE_KEY_EXACT = frozenset({"authorization", "cookie", "data", "payload"})
_SENSITIVE_KEY_PARTS = (
    "token",
    "secret",
    "password",
    "credential",
    "apikey",
    "authorization",
    "payload",
    "cpf",
    "cnpj",
    "email",
)
_GRPC_METADATA_KEYS = frozenset(
    {
        "x-correlation-id",
        "x-request-id",
        "traceparent",
        "x-creditos-tenant-id",
        "x-creditos-tenant-isolation-tier",
        "x-creditos-subject-id",
        "x-creditos-client-id",
        "x-creditos-principal-type",
        "x-creditos-scopes",
        "x-creditos-roles",
        "x-creditos-schema-version",
    }
)
_CLOUDEVENT_CONTEXT_KEYS = frozenset(
    {
        "tenantid",
        "tenanttier",
        "subjectid",
        "clientid",
        "principaltype",
        "scopes",
        "roles",
        "correlationid",
        "requestid",
        "traceparent",
        "schemaversion",
        "idempotencykey",
    }
)
_CLOUDEVENT_CORE_KEYS = frozenset(
    {
        "specversion",
        "id",
        "source",
        "type",
        "subject",
        "time",
        "datacontenttype",
        "dataschema",
    }
)
_CLOUDEVENT_ALLOWED_DATA_KEYS = frozenset({"datacontenttype", "dataschema"})


class InvalidTrustedContextError(ValueError):
    code = "invalid_trusted_context"
    safe_message = "contexto confiável inválido"
    grpc_status = "PERMISSION_DENIED"

    def __init__(self, message: str | None = None) -> None:
        self.message = message or self.safe_message
        super().__init__(self.message)


@dataclass(frozen=True, slots=True)
class TrustedContext:
    tenant_id: str
    tenant_isolation_tier: str
    subject_id: str
    scopes: Iterable[str]
    roles: Iterable[str] = ()
    client_id: str | None = None
    principal_type: str = "m2m"

    def __post_init__(self) -> None:
        object.__setattr__(self, "tenant_id", _required_text(self.tenant_id, "tenant_id"))
        object.__setattr__(
            self,
            "tenant_isolation_tier",
            _required_tenant_isolation_tier(self.tenant_isolation_tier),
        )
        object.__setattr__(self, "subject_id", _required_text(self.subject_id, "subject_id"))
        object.__setattr__(self, "scopes", _normalize_required_tokens(self.scopes))
        object.__setattr__(self, "roles", _normalize_optional_tokens(self.roles))
        object.__setattr__(self, "client_id", _optional_text(self.client_id, "client_id"))
        object.__setattr__(self, "principal_type", _required_principal_type(self.principal_type))

    def to_public_metadata(self) -> dict[str, object]:
        metadata: dict[str, object] = {
            "tenant_id": self.tenant_id,
            "tenant_isolation_tier": self.tenant_isolation_tier,
            "subject_id": self.subject_id,
            "principal_type": self.principal_type,
            "scopes": sorted(self.scopes),
            "roles": sorted(self.roles),
        }
        if self.client_id is not None:
            metadata["client_id"] = self.client_id
        return metadata


@dataclass(frozen=True, slots=True)
class PropagatedContext:
    trusted: TrustedContext
    correlation_id: str
    request_id: str
    traceparent: str
    schema_version: str = "v1"

    def __post_init__(self) -> None:
        if not isinstance(self.trusted, TrustedContext):
            raise InvalidTrustedContextError("contexto confiável inválido")
        object.__setattr__(
            self,
            "correlation_id",
            _required_text(self.correlation_id, "correlation_id"),
        )
        object.__setattr__(self, "request_id", _required_text(self.request_id, "request_id"))
        object.__setattr__(self, "traceparent", _required_traceparent(self.traceparent))
        object.__setattr__(self, "schema_version", _required_schema_version(self.schema_version))

    @property
    def trace_id(self) -> str:
        match = _TRACEPARENT_PATTERN.fullmatch(self.traceparent)
        if match is None:
            raise InvalidTrustedContextError("traceparent inválido")
        return match.group(1)

    def to_public_metadata(self) -> dict[str, object]:
        return {
            **self.trusted.to_public_metadata(),
            "correlation_id": self.correlation_id,
            "request_id": self.request_id,
            "traceparent": self.traceparent,
            "schema_version": self.schema_version,
        }


@dataclass(frozen=True, slots=True)
class CloudEventTrustedContext:
    context: PropagatedContext
    idempotency_key: str
    event_id: str
    source: str
    event_type: str
    subject: str
    time: str
    datacontenttype: str

    def __post_init__(self) -> None:
        if not isinstance(self.context, PropagatedContext):
            raise InvalidTrustedContextError("contexto de evento inválido")
        object.__setattr__(
            self,
            "idempotency_key",
            _required_text(self.idempotency_key, "idempotencykey"),
        )
        object.__setattr__(self, "event_id", _required_text(self.event_id, "id"))
        object.__setattr__(self, "source", _required_text(self.source, "source"))
        object.__setattr__(self, "event_type", _required_text(self.event_type, "type"))
        object.__setattr__(self, "subject", _required_text(self.subject, "subject"))
        object.__setattr__(self, "time", _required_non_empty_string(self.time, "time"))
        if self.datacontenttype != "application/json":
            raise InvalidTrustedContextError("datacontenttype CloudEvents inválido")


def _required_tenant_isolation_tier(value: str) -> str:
    tier = _required_text(value, "tenant_isolation_tier")
    if tier not in _TENANT_ISOLATION_TIERS:
        raise InvalidTrustedContextError("tier de isolamento inválido")
    return tier


def _required_principal_type(value: str) -> str:
    principal_type = _required_text(value, "principal_type")
    if principal_type not in _PRINCIPAL_TYPES:
        raise InvalidTrustedContextError("tipo de principal inválido")
    return principal_type


def _required_traceparent(value: str) -> str:
    if not isinstance(value, str):
        raise InvalidTrustedContextError("traceparent é obrigatório")
    normalized_value = value.strip()
    match = _TRACEPARENT_PATTERN.fullmatch(normalized_value)
    if match is None or match.group(1) == "0" * 32 or match.group(2) == "0" * 16:
        raise InvalidTrustedContextError("traceparent inválido")
    return normalized_value


def _required_schema_version(value: str) -> str:
    if not isinstance(value, str):
        raise InvalidTrustedContextError("schema_version é obrigatório")
    normalized_value = value.strip()
    if _SCHEMA_VERSION_PATTERN.fullmatch(normalized_value) is None:
        raise InvalidTrustedContextError("schema_version inválido")
    return normalized_value


def _optional_text(value: str | None, field_name: str) -> str | None:
    if value is None:
        return None
    return _required_text(value, field_name)


def _required_text(value: str, field_name: str) -> str:
    if not isinstance(value, str):
        raise InvalidTrustedContextError(f"{field_name} é obrigatório")
    normalized_value = value.strip()
    if not normalized_value:
        raise InvalidTrustedContextError(f"{field_name} é obrigatório")
    if _CONTEXT_TEXT_PATTERN.fullmatch(normalized_value) is None:
        raise InvalidTrustedContextError(f"{field_name} inválido")
    if _contains_brazilian_document(normalized_value):
        raise InvalidTrustedContextError(f"{field_name} não pode conter documento sensível")
    return normalized_value


def _required_non_empty_string(value: str, field_name: str) -> str:
    if not isinstance(value, str):
        raise InvalidTrustedContextError(f"{field_name} é obrigatório")
    normalized_value = value.strip()
    if not normalized_value:
        raise InvalidTrustedContextError(f"{field_name} é obrigatório")
    return normalized_value


def _contains_brazilian_document(value: str) -> bool:
    if _BRAZILIAN_DOCUMENT_PATTERN.fullmatch(value) is not None:
        return True
    digits = re.sub(r"\D", "", value)
    return len(digits) in (11, 14)


def _normalize_required_tokens(values: Iterable[str]) -> frozenset[str]:
    tokens = _normalize_tokens(values)
    if not tokens:
        raise InvalidTrustedContextError("tokens de contexto obrigatórios")
    return tokens


def _normalize_optional_tokens(values: Iterable[str]) -> frozenset[str]:
    return _normalize_tokens(values)


def _normalize_tokens(values: Iterable[str]) -> frozenset[str]:
    if isinstance(values, str | Mapping | bytes | bytearray | memoryview) or not isinstance(
        values,
        Iterable,
    ):
        raise InvalidTrustedContextError("tokens de contexto inválidos")

    normalized_tokens: set[str] = set()
    for value in values:
        if not isinstance(value, str):
            raise InvalidTrustedContextError("tokens de contexto inválidos")
        normalized_value = value.strip()
        if _CONTEXT_TOKEN_PATTERN.fullmatch(normalized_value) is None:
            raise InvalidTrustedContextError("tokens de contexto inválidos")
        normalized_tokens.add(normalized_value)
        if len(normalized_tokens) > _MAX_CONTEXT_TOKENS:
            raise InvalidTrustedContextError("tokens de contexto excedem limite")
    return frozenset(normalized_tokens)


def context_to_grpc_metadata(context: PropagatedContext) -> tuple[tuple[str, str], ...]:
    if not isinstance(context, PropagatedContext):
        raise InvalidTrustedContextError("contexto propagado inválido")

    metadata: list[tuple[str, str]] = [
        ("x-correlation-id", context.correlation_id),
        ("x-request-id", context.request_id),
        ("traceparent", context.traceparent),
        ("x-creditos-tenant-id", context.trusted.tenant_id),
        ("x-creditos-tenant-isolation-tier", context.trusted.tenant_isolation_tier),
        ("x-creditos-subject-id", context.trusted.subject_id),
    ]
    if context.trusted.client_id is not None:
        metadata.append(("x-creditos-client-id", context.trusted.client_id))
    metadata.extend(
        [
            ("x-creditos-principal-type", context.trusted.principal_type),
            ("x-creditos-scopes", " ".join(sorted(context.trusted.scopes))),
        ]
    )
    if context.trusted.roles:
        metadata.append(("x-creditos-roles", " ".join(sorted(context.trusted.roles))))
    metadata.append(("x-creditos-schema-version", context.schema_version))
    return tuple(metadata)


def context_from_grpc_metadata(
    metadata: Mapping[str, str] | Sequence[tuple[str, str]],
) -> PropagatedContext:
    carrier = _metadata_to_mapping(metadata)
    return PropagatedContext(
        trusted=TrustedContext(
            tenant_id=_required_metadata(carrier, "x-creditos-tenant-id"),
            tenant_isolation_tier=_required_metadata(
                carrier,
                "x-creditos-tenant-isolation-tier",
            ),
            subject_id=_required_metadata(carrier, "x-creditos-subject-id"),
            scopes=_split_metadata_tokens(_required_metadata(carrier, "x-creditos-scopes")),
            roles=_split_metadata_tokens(carrier.get("x-creditos-roles", "")),
            client_id=carrier.get("x-creditos-client-id"),
            principal_type=_required_metadata(carrier, "x-creditos-principal-type"),
        ),
        correlation_id=_required_metadata(carrier, "x-correlation-id"),
        request_id=_required_metadata(carrier, "x-request-id"),
        traceparent=_required_metadata(carrier, "traceparent"),
        schema_version=_required_metadata(carrier, "x-creditos-schema-version"),
    )


def _metadata_to_mapping(
    metadata: Mapping[str, str] | Sequence[tuple[str, str]],
) -> dict[str, str]:
    if isinstance(metadata, str | bytes | bytearray | memoryview) or not isinstance(
        metadata,
        Mapping | Sequence,
    ):
        raise InvalidTrustedContextError("metadata gRPC inválida")

    items = metadata.items() if isinstance(metadata, Mapping) else metadata
    carrier: dict[str, str] = {}
    for item in items:
        if isinstance(item, str | bytes | bytearray | memoryview) or not isinstance(
            item,
            Sequence,
        ):
            raise InvalidTrustedContextError("metadata gRPC inválida")
        if len(item) != 2:
            raise InvalidTrustedContextError("metadata gRPC inválida")
        raw_key, raw_value = item
        if not isinstance(raw_key, str) or not isinstance(raw_value, str):
            raise InvalidTrustedContextError("metadata gRPC inválida")
        if raw_key != raw_key.lower():
            raise InvalidTrustedContextError("metadata gRPC deve usar chaves lower-case")
        key = raw_key.strip()
        if key.endswith("-bin") or key in _SENSITIVE_METADATA_KEYS or _is_sensitive_key(key):
            raise InvalidTrustedContextError("metadata gRPC proibida")
        if key not in _GRPC_METADATA_KEYS:
            continue
        if key in carrier:
            raise InvalidTrustedContextError("metadata gRPC duplicada")
        carrier[key] = raw_value.strip()
    return carrier


def _required_metadata(carrier: Mapping[str, str], key: str) -> str:
    value = carrier.get(key)
    if value is None or not value.strip():
        raise InvalidTrustedContextError("metadata gRPC obrigatória ausente")
    return value


def _split_metadata_tokens(value: str) -> tuple[str, ...]:
    if not value.strip():
        return ()
    return tuple(value.split())


def context_to_cloudevent_attributes(
    context: PropagatedContext,
    *,
    idempotency_key: str,
) -> dict[str, str]:
    if not isinstance(context, PropagatedContext):
        raise InvalidTrustedContextError("contexto propagado inválido")

    attributes = {
        "tenantid": context.trusted.tenant_id,
        "tenanttier": context.trusted.tenant_isolation_tier,
        "subjectid": context.trusted.subject_id,
        "principaltype": context.trusted.principal_type,
        "scopes": " ".join(sorted(context.trusted.scopes)),
        "correlationid": context.correlation_id,
        "requestid": context.request_id,
        "traceparent": context.traceparent,
        "schemaversion": context.schema_version,
    }
    if context.trusted.client_id is not None:
        attributes["clientid"] = context.trusted.client_id
    if context.trusted.roles:
        attributes["roles"] = " ".join(sorted(context.trusted.roles))
    attributes["idempotencykey"] = _required_text(idempotency_key, "idempotencykey")
    return attributes


def context_from_cloudevent_attributes(attributes: Mapping[str, str]) -> PropagatedContext:
    return cloudevent_context_from_attributes(attributes).context


def cloudevent_context_from_attributes(attributes: Mapping[str, str]) -> CloudEventTrustedContext:
    carrier = _cloudevent_attributes_to_mapping(attributes)
    specversion = _required_cloudevent_attribute(carrier, "specversion")
    if specversion != "1.0":
        raise InvalidTrustedContextError("specversion CloudEvents inválida")
    return CloudEventTrustedContext(
        context=PropagatedContext(
            trusted=TrustedContext(
                tenant_id=_required_cloudevent_attribute(carrier, "tenantid"),
                tenant_isolation_tier=_required_cloudevent_attribute(carrier, "tenanttier"),
                subject_id=_required_cloudevent_attribute(carrier, "subjectid"),
                scopes=_split_metadata_tokens(_required_cloudevent_attribute(carrier, "scopes")),
                roles=_split_metadata_tokens(carrier.get("roles", "")),
                client_id=carrier.get("clientid"),
                principal_type=_required_cloudevent_attribute(carrier, "principaltype"),
            ),
            correlation_id=_required_cloudevent_attribute(carrier, "correlationid"),
            request_id=_required_cloudevent_attribute(carrier, "requestid"),
            traceparent=_required_cloudevent_attribute(carrier, "traceparent"),
            schema_version=_required_cloudevent_attribute(carrier, "schemaversion"),
        ),
        idempotency_key=_required_cloudevent_attribute(carrier, "idempotencykey"),
        event_id=_required_cloudevent_attribute(carrier, "id"),
        source=_required_cloudevent_attribute(carrier, "source"),
        event_type=_required_cloudevent_attribute(carrier, "type"),
        subject=_required_cloudevent_attribute(carrier, "subject"),
        time=_required_cloudevent_attribute(carrier, "time"),
        datacontenttype=_required_cloudevent_attribute(carrier, "datacontenttype"),
    )


def _cloudevent_attributes_to_mapping(attributes: Mapping[str, str]) -> dict[str, str]:
    if not isinstance(attributes, Mapping):
        raise InvalidTrustedContextError("atributos CloudEvents inválidos")
    carrier: dict[str, str] = {}
    for raw_key, raw_value in attributes.items():
        if not isinstance(raw_key, str) or not isinstance(raw_value, str):
            raise InvalidTrustedContextError("atributos CloudEvents inválidos")
        key = raw_key.strip()
        if key != key.lower() or "_" in key:
            raise InvalidTrustedContextError("extensão CloudEvents inválida")
        if (
            key in _SENSITIVE_CLOUDEVENT_KEYS
            or key not in _CLOUDEVENT_ALLOWED_DATA_KEYS
            and _is_sensitive_key(key)
        ):
            raise InvalidTrustedContextError("atributo CloudEvents proibido")
        if key not in _CLOUDEVENT_CONTEXT_KEYS and key not in _CLOUDEVENT_CORE_KEYS:
            continue
        carrier[key] = raw_value.strip()
    return carrier


def _required_cloudevent_attribute(carrier: Mapping[str, str], key: str) -> str:
    value = carrier.get(key)
    if value is None or not value.strip():
        raise InvalidTrustedContextError("atributo CloudEvents obrigatório ausente")
    return value


def _is_sensitive_key(key: str) -> bool:
    normalized_key = re.sub(r"[^a-z0-9]", "", key.lower())
    return normalized_key in _SENSITIVE_KEY_EXACT or any(
        part in normalized_key for part in _SENSITIVE_KEY_PARTS
    )
