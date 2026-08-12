from __future__ import annotations

import json

import pytest
from creditos_identity_tenant.adapters.events.trusted_context import (
    cloudevent_attributes_from_authorization_subject,
    event_context_from_cloudevent_attributes,
    propagated_context_from_cloudevent_attributes,
)
from creditos_identity_tenant.adapters.grpc.trusted_context import (
    authorization_subject_from_grpc_metadata,
    grpc_metadata_from_authorization_subject,
    propagated_context_from_resolved_m2m_context,
)
from creditos_identity_tenant.adapters.logging.in_memory_operation_logger import (
    InMemoryOperationLogger,
)
from creditos_identity_tenant.application.security import AuthorizationSubject
from creditos_identity_tenant.application.use_cases.resolve_m2m_tenant_context import (
    ResolvedM2MTenantContext,
)
from creditos_observability.context import ObservabilityContext
from creditos_security.context import InvalidTrustedContextError


def test_grpc_adapter_derives_metadata_from_authorization_subject_without_token_id() -> None:
    metadata = grpc_metadata_from_authorization_subject(
        _authorization_subject(token_id="raw-token-id"),
        _observability_context(),
    )

    metadata_map = dict(metadata)
    assert metadata_map["x-creditos-tenant-id"] == "tenant_alpha"
    assert metadata_map["x-creditos-client-id"] == "client-alpha"
    assert metadata_map["x-creditos-scopes"] == "proposal:submit"
    assert metadata_map["traceparent"].startswith("00-4bf92f3577b34da6a3ce929d0e0e4736-")
    assert "token_id" not in str(metadata)
    assert authorization_subject_from_grpc_metadata(metadata) == _authorization_subject(
        token_id=None
    )


def test_grpc_adapter_derives_propagated_context_from_resolved_m2m_context() -> None:
    propagated = propagated_context_from_resolved_m2m_context(
        ResolvedM2MTenantContext(
            tenant_id="tenant_alpha",
            tenant_isolation_tier="bridge",
            client_id="client-alpha",
            subject="client-alpha",
            scopes=frozenset({"proposal:submit"}),
            issuer="https://issuer.creditos.local",
            audience="creditos-api",
            token_id="raw-token-id",
        ),
        _observability_context(),
        trusted_roles=("service-client",),
    )

    assert propagated.trusted.tenant_id == "tenant_alpha"
    assert propagated.trusted.roles == frozenset({"service-client"})
    assert "token_id" not in propagated.to_public_metadata()


def test_event_adapter_round_trips_authorization_subject_context() -> None:
    attributes = _cloudevent_attributes()

    assert attributes["tenantid"] == "tenant_alpha"
    assert attributes["idempotencykey"] == "idem-alpha"
    assert "tenant_id" not in attributes
    assert "raw-token-id" not in str(attributes)
    propagated = propagated_context_from_cloudevent_attributes(attributes)
    assert propagated.trusted.subject_id == "client-alpha"
    assert event_context_from_cloudevent_attributes(attributes).idempotency_key == "idem-alpha"


def test_adapters_reject_untrusted_metadata_before_case_use() -> None:
    metadata = dict(
        grpc_metadata_from_authorization_subject(
            _authorization_subject(),
            _observability_context(),
        )
    )
    metadata["x-creditos-tenant-id"] = "tenant beta"

    try:
        authorization_subject_from_grpc_metadata(metadata)
    except InvalidTrustedContextError as error:
        assert error.code == "invalid_trusted_context"
    else:  # pragma: no cover
        raise AssertionError("metadata malformada deveria ser rejeitada")


def test_grpc_adapter_rejects_cross_tenant_metadata_before_case_use_and_logs_safely() -> None:
    logger = InMemoryOperationLogger()
    metadata = grpc_metadata_from_authorization_subject(
        _authorization_subject(),
        _observability_context(),
    )

    with pytest.raises(InvalidTrustedContextError):
        authorization_subject_from_grpc_metadata(
            metadata,
            expected_tenant_id="tenant_beta",
            operation_logger=logger,
            observability_context=_observability_context(),
        )

    event = logger.events[-1]
    serialized = json.dumps(event, ensure_ascii=False)
    assert event["operation"] == "identity_tenant.validate_grpc_trusted_context"
    assert event["source"] == "trusted-context"
    assert event["status"] == "rejected"
    assert "tenant_id" not in event
    assert "tenant_isolation_tier" not in event
    assert "tenant_alpha" not in serialized


def test_event_adapter_rejects_cross_tenant_context_and_invalid_envelope() -> None:
    with pytest.raises(InvalidTrustedContextError):
        event_context_from_cloudevent_attributes(
            _cloudevent_attributes(),
            expected_tenant_id="tenant_beta",
        )

    invalid_envelope = _cloudevent_attributes()
    invalid_envelope["specversion"] = "0.3"

    with pytest.raises(InvalidTrustedContextError):
        event_context_from_cloudevent_attributes(invalid_envelope)


def test_event_adapter_requires_idempotency_key() -> None:
    attributes = _cloudevent_attributes()
    del attributes["idempotencykey"]

    with pytest.raises(InvalidTrustedContextError):
        event_context_from_cloudevent_attributes(attributes)


def _authorization_subject(token_id: str | None = "jti-alpha") -> AuthorizationSubject:
    return AuthorizationSubject(
        subject_id="client-alpha",
        tenant_id="tenant_alpha",
        tenant_isolation_tier="bridge",
        scopes=("proposal:submit",),
        roles=("service-client",),
        client_id="client-alpha",
        token_id=token_id,
    )


def _observability_context() -> ObservabilityContext:
    return ObservabilityContext.new(
        correlation_id="corr-alpha",
        request_id="req-alpha",
        trace_id="4bf92f3577b34da6a3ce929d0e0e4736",
    )


def _cloudevent_attributes() -> dict[str, str]:
    return {
        "specversion": "1.0",
        "id": "event-alpha",
        "source": "identity-tenant",
        "type": "creditos.proposal.v1.submitted",
        "subject": "proposal-alpha",
        "time": "2026-08-12T00:00:00Z",
        "datacontenttype": "application/json",
        **cloudevent_attributes_from_authorization_subject(
            _authorization_subject(token_id="raw-token-id"),
            _observability_context(),
            idempotency_key="idem-alpha",
        ),
    }
