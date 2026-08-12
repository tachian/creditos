from __future__ import annotations

import pytest
from creditos_security.context import (
    InvalidTrustedContextError,
    PropagatedContext,
    TrustedContext,
    context_from_grpc_metadata,
    context_to_grpc_metadata,
)


def test_grpc_metadata_round_trip_uses_safe_lowercase_ascii_keys() -> None:
    context = _propagated_context()

    metadata = context_to_grpc_metadata(context)

    assert metadata == (
        ("x-correlation-id", "corr-alpha"),
        ("x-request-id", "req-alpha"),
        ("traceparent", "00-4bf92f3577b34da6a3ce929d0e0e4736-00f067aa0ba902b7-01"),
        ("x-creditos-tenant-id", "tenant_alpha"),
        ("x-creditos-tenant-isolation-tier", "bridge"),
        ("x-creditos-subject-id", "client-alpha"),
        ("x-creditos-client-id", "client-alpha"),
        ("x-creditos-principal-type", "m2m"),
        ("x-creditos-scopes", "decision:read proposal:submit"),
        ("x-creditos-roles", "service-client"),
        ("x-creditos-schema-version", "v1"),
    )
    assert context_from_grpc_metadata(metadata) == context


@pytest.mark.parametrize(
    "metadata",
    [
        (),
        (("x-creditos-tenant-id", "tenant_alpha"),),
        (("x-creditos-tenant-id", "tenant_alpha"), ("x-creditos-scopes", "proposal:submit")),
        (("x-creditos-tenant-id", b"tenant_alpha"),),
        (("x-creditos-tenant-id-bin", b"tenant_alpha"),),
        (("X-Creditos-Tenant-Id", "tenant_alpha"),),
        (("authorization", "Bearer raw-token"),),
        (("x-creditos-tenant-id", "tenant alpha"),),
        (("x-creditos-scopes", "proposal:submit decision:read"),),
    ],
)
def test_grpc_metadata_rejects_missing_binary_sensitive_or_malformed_values(
    metadata: tuple[tuple[object, object], ...],
) -> None:
    with pytest.raises(InvalidTrustedContextError):
        context_from_grpc_metadata(metadata)  # type: ignore[arg-type]


def test_grpc_metadata_rejects_traceparent_invalid() -> None:
    metadata = dict(context_to_grpc_metadata(_propagated_context()))
    metadata["traceparent"] = "invalid"

    with pytest.raises(InvalidTrustedContextError):
        context_from_grpc_metadata(metadata)


@pytest.mark.parametrize(
    "mutation",
    [
        "duplicate",
        "token",
        "secret",
        "payload",
        "cpf",
        (("x-creditos-tenant-id",),),
        ("x-creditos-tenant-id",),  # type: ignore[list-item]
    ],
)
def test_grpc_metadata_rejects_duplicate_sensitive_unknown_or_malformed_items(
    mutation: object,
) -> None:
    metadata: object
    match mutation:
        case "duplicate":
            metadata = (
                *context_to_grpc_metadata(_propagated_context()),
                ("x-creditos-tenant-id", "tenant_beta"),
            )
        case "token":
            metadata = (
                ("x-creditos-token-id", "raw-token"),
                *context_to_grpc_metadata(_propagated_context()),
            )
        case "secret":
            metadata = (
                ("x-secret", "raw-secret"),
                *context_to_grpc_metadata(_propagated_context()),
            )
        case "payload":
            metadata = (
                ("x-payload", "raw-payload"),
                *context_to_grpc_metadata(_propagated_context()),
            )
        case "cpf":
            metadata = (
                ("x-cpf", "12345678901"),
                *context_to_grpc_metadata(_propagated_context()),
            )
        case _:
            metadata = mutation

    with pytest.raises(InvalidTrustedContextError):
        context_from_grpc_metadata(metadata)  # type: ignore[arg-type]


def test_grpc_metadata_does_not_expose_sensitive_identifiers_or_payload() -> None:
    serialized = str(context_to_grpc_metadata(_propagated_context())).lower()

    assert "authorization" not in serialized
    assert "bearer" not in serialized
    assert "token_id" not in serialized
    assert "raw-token" not in serialized
    assert "12345678901" not in serialized
    assert "12.345.678/0001-90" not in serialized
    assert "client-alpha@example.com" not in serialized
    assert "payload" not in serialized


def _propagated_context() -> PropagatedContext:
    return PropagatedContext(
        trusted=TrustedContext(
            tenant_id="tenant_alpha",
            tenant_isolation_tier="bridge",
            subject_id="client-alpha",
            scopes=("proposal:submit", "decision:read"),
            roles=("service-client",),
            client_id="client-alpha",
        ),
        correlation_id="corr-alpha",
        request_id="req-alpha",
        traceparent="00-4bf92f3577b34da6a3ce929d0e0e4736-00f067aa0ba902b7-01",
        schema_version="v1",
    )
