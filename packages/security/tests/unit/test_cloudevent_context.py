from __future__ import annotations

import pytest
from creditos_security.context import (
    InvalidTrustedContextError,
    PropagatedContext,
    TrustedContext,
    cloudevent_context_from_attributes,
    context_from_cloudevent_attributes,
    context_to_cloudevent_attributes,
)


def test_cloudevent_attributes_round_trip_uses_valid_extensions_without_payload() -> None:
    context = _propagated_context()

    attributes = _cloudevent_attributes(context)

    assert attributes == {
        "specversion": "1.0",
        "id": "event-alpha",
        "source": "identity-tenant",
        "type": "creditos.proposal.v1.submitted",
        "subject": "proposal-alpha",
        "time": "2026-08-12T00:00:00Z",
        "datacontenttype": "application/json",
        "tenantid": "tenant_alpha",
        "tenanttier": "bridge",
        "subjectid": "client-alpha",
        "clientid": "client-alpha",
        "principaltype": "m2m",
        "scopes": "decision:read proposal:submit",
        "roles": "service-client",
        "correlationid": "corr-alpha",
        "requestid": "req-alpha",
        "traceparent": "00-4bf92f3577b34da6a3ce929d0e0e4736-00f067aa0ba902b7-01",
        "schemaversion": "v1",
        "idempotencykey": "idem-alpha",
    }
    event_context = cloudevent_context_from_attributes(attributes)
    assert event_context.context == context
    assert event_context.idempotency_key == "idem-alpha"
    assert all("_" not in key for key in attributes)
    assert "data" not in attributes
    assert context_from_cloudevent_attributes(attributes) == context


@pytest.mark.parametrize(
    "mutation",
    [
        {},
        {"tenant_id": "tenant_alpha"},
        {"tenantid": "tenant_alpha", "tenanttier": "bridge"},
        {"tenantid": "tenant alpha"},
        {"tenanttier": "pooled"},
        {"traceparent": "invalid"},
        "invalid_specversion",
        "missing_core_type",
        "missing_core_source",
        "xsecret",
        "payload",
        "cpf",
        {"authorization": "Bearer raw-token"},
        {"token": "raw-token"},
        {"scopes": "proposal:submit decision:read"},
    ],
)
def test_cloudevent_attributes_reject_missing_invalid_or_sensitive_context(
    mutation: object,
) -> None:
    attributes: dict[str, str]
    match mutation:
        case "invalid_specversion":
            attributes = _cloudevent_attributes(_propagated_context())
            attributes["specversion"] = "0.3"
        case "missing_core_type":
            attributes = _cloudevent_attributes(_propagated_context())
            del attributes["type"]
        case "missing_core_source":
            attributes = _cloudevent_attributes(_propagated_context())
            del attributes["source"]
        case "xsecret":
            attributes = {"xsecret": "raw-secret", **_cloudevent_attributes(_propagated_context())}
        case "payload":
            attributes = {"payload": "raw-payload", **_cloudevent_attributes(_propagated_context())}
        case "cpf":
            attributes = {"cpf": "12345678901", **_cloudevent_attributes(_propagated_context())}
        case _:
            attributes = mutation  # type: ignore[assignment]

    with pytest.raises(InvalidTrustedContextError):
        context_from_cloudevent_attributes(attributes)


def test_cloudevent_attributes_reject_unknown_extension_with_underscore() -> None:
    attributes = _cloudevent_attributes(_propagated_context())
    attributes["tenant_id"] = "tenant_alpha"

    with pytest.raises(InvalidTrustedContextError):
        context_from_cloudevent_attributes(attributes)


def test_cloudevent_attributes_require_idempotency_key_for_event_context() -> None:
    attributes = _cloudevent_attributes(_propagated_context())
    del attributes["idempotencykey"]

    with pytest.raises(InvalidTrustedContextError):
        cloudevent_context_from_attributes(attributes)


def test_cloudevent_attributes_do_not_expose_sensitive_identifiers_or_payload() -> None:
    serialized = str(
        context_to_cloudevent_attributes(_propagated_context(), idempotency_key="idem-alpha")
    ).lower()

    assert "authorization" not in serialized
    assert "bearer" not in serialized
    assert "token_id" not in serialized
    assert "raw-token" not in serialized
    assert "12345678901" not in serialized
    assert "12.345.678/0001-90" not in serialized
    assert "client-alpha@example.com" not in serialized
    assert "data" not in serialized


def _cloudevent_attributes(context: PropagatedContext) -> dict[str, str]:
    return {
        "specversion": "1.0",
        "id": "event-alpha",
        "source": "identity-tenant",
        "type": "creditos.proposal.v1.submitted",
        "subject": "proposal-alpha",
        "time": "2026-08-12T00:00:00Z",
        "datacontenttype": "application/json",
        **context_to_cloudevent_attributes(context, idempotency_key="idem-alpha"),
    }


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
