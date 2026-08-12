from __future__ import annotations

import pytest
from creditos_security.context import InvalidTrustedContextError, PropagatedContext, TrustedContext


def test_trusted_context_normalizes_minimal_authorized_context_without_token_id() -> None:
    context = TrustedContext(
        tenant_id=" tenant_alpha ",
        tenant_isolation_tier="bridge",
        subject_id="client-alpha",
        scopes=("proposal:submit", "decision:read"),
        roles=("service-client",),
        client_id="client-alpha",
        principal_type="m2m",
    )

    assert context.tenant_id == "tenant_alpha"
    assert context.scopes == frozenset({"proposal:submit", "decision:read"})
    assert context.roles == frozenset({"service-client"})
    assert context.to_public_metadata() == {
        "tenant_id": "tenant_alpha",
        "tenant_isolation_tier": "bridge",
        "subject_id": "client-alpha",
        "client_id": "client-alpha",
        "principal_type": "m2m",
        "scopes": ["decision:read", "proposal:submit"],
        "roles": ["service-client"],
    }
    assert "token_id" not in context.to_public_metadata()


@pytest.mark.parametrize(
    "kwargs",
    [
        {"tenant_id": ""},
        {"tenant_isolation_tier": "pooled"},
        {"subject_id": "client alpha"},
        {"principal_type": "anonymous"},
        {"scopes": "proposal:submit"},
        {"scopes": {"proposal:submit": True}},
        {"scopes": ("proposal:submit decision:read",)},
        {"roles": "service-client"},
        {"client_id": "client alpha"},
        {"subject_id": "12345678901"},
        {"subject_id": "client-12345678901"},
        {"subject_id": "12.345.678/0001-90"},
        {"subject_id": "merchant-12.345.678/0001-90"},
        {"client_id": "client-alpha@example.com"},
    ],
)
def test_trusted_context_rejects_malformed_context(kwargs: dict[str, object]) -> None:
    values: dict[str, object] = {
        "tenant_id": "tenant_alpha",
        "tenant_isolation_tier": "bridge",
        "subject_id": "client-alpha",
        "scopes": ("proposal:submit",),
        "roles": ("service-client",),
        "client_id": "client-alpha",
        "principal_type": "m2m",
    }
    values.update(kwargs)

    with pytest.raises(InvalidTrustedContextError) as error:
        TrustedContext(**values)  # type: ignore[arg-type]

    assert error.value.code == "invalid_trusted_context"
    assert error.value.grpc_status == "PERMISSION_DENIED"


def test_trusted_context_enforces_token_limits() -> None:
    with pytest.raises(InvalidTrustedContextError):
        TrustedContext(
            tenant_id="tenant_alpha",
            tenant_isolation_tier="bridge",
            subject_id="client-alpha",
            scopes=tuple(f"scope:{index}" for index in range(65)),
        )


def test_propagated_context_combines_trusted_context_with_traceability() -> None:
    context = PropagatedContext(
        trusted=TrustedContext(
            tenant_id="tenant_alpha",
            tenant_isolation_tier="bridge",
            subject_id="client-alpha",
            scopes=("proposal:submit",),
            roles=("service-client",),
            client_id="client-alpha",
        ),
        correlation_id="corr-alpha",
        request_id="req-alpha",
        traceparent="00-4bf92f3577b34da6a3ce929d0e0e4736-00f067aa0ba902b7-01",
        schema_version="v1",
    )

    assert context.trace_id == "4bf92f3577b34da6a3ce929d0e0e4736"
    assert context.to_public_metadata()["tenant_id"] == "tenant_alpha"
    assert context.to_public_metadata()["correlation_id"] == "corr-alpha"
    assert "token_id" not in context.to_public_metadata()


@pytest.mark.parametrize(
    "kwargs",
    [
        {"correlation_id": ""},
        {"request_id": "req alpha"},
        {"traceparent": "invalid"},
        {"traceparent": "00-00000000000000000000000000000000-00f067aa0ba902b7-01"},
        {"schema_version": "1"},
    ],
)
def test_propagated_context_rejects_malformed_traceability(kwargs: dict[str, object]) -> None:
    values: dict[str, object] = {
        "trusted": TrustedContext(
            tenant_id="tenant_alpha",
            tenant_isolation_tier="bridge",
            subject_id="client-alpha",
            scopes=("proposal:submit",),
        ),
        "correlation_id": "corr-alpha",
        "request_id": "req-alpha",
        "traceparent": "00-4bf92f3577b34da6a3ce929d0e0e4736-00f067aa0ba902b7-01",
        "schema_version": "v1",
    }
    values.update(kwargs)

    with pytest.raises(InvalidTrustedContextError):
        PropagatedContext(**values)  # type: ignore[arg-type]
