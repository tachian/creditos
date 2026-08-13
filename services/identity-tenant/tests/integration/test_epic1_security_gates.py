from __future__ import annotations

import json
import re
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from creditos_identity_tenant.adapters.events.trusted_context import (
    event_context_from_cloudevent_attributes,
)
from creditos_identity_tenant.adapters.external.local_m2m_token_verifier import (
    LocalM2MTokenClaims,
    LocalM2MTokenVerifier,
)
from creditos_identity_tenant.adapters.grpc.trusted_context import (
    authorization_subject_from_grpc_metadata,
    grpc_metadata_from_authorization_subject,
)
from creditos_identity_tenant.adapters.logging.in_memory_operation_logger import (
    InMemoryOperationLogger,
)
from creditos_identity_tenant.adapters.persistence.in_memory_tenant_repository import (
    InMemoryTenantRepository,
)
from creditos_identity_tenant.application.security import (
    AuthorizationRequirement,
    AuthorizationSubject,
    ProtectedResource,
)
from creditos_identity_tenant.application.service import TenantApplicationService
from creditos_identity_tenant.application.trusted_context import (
    propagated_context_from_authorization_subject,
)
from creditos_identity_tenant.application.use_cases.authorize_operation import (
    AuthorizeOperationCommand,
)
from creditos_identity_tenant.application.use_cases.resolve_m2m_tenant_context import (
    ResolveM2MTenantContextCommand,
)
from creditos_identity_tenant.domain.entities.tenant import Tenant
from creditos_identity_tenant.domain.errors import (
    CrossTenantAccessDeniedError,
    ExpiredTokenError,
    InsufficientRoleError,
    InsufficientScopeError,
    InvalidAuthorizationRequirementError,
    InvalidTokenAudienceError,
    InvalidTokenError,
    InvalidTokenIssuerError,
    MissingTokenError,
    MissingTokenRequiredClaimError,
)
from creditos_observability.context import ObservabilityContext
from creditos_security.context import (
    InvalidTrustedContextError,
    context_to_cloudevent_attributes,
)

NOW = datetime(2026, 8, 6, 12, 0, tzinfo=UTC)
ROOT = Path(__file__).resolve().parents[4]
CI_WORKFLOW = ROOT / ".github" / "workflows" / "ci.yml"
DEV_SCRIPT = ROOT / "scripts" / "dev"
TRACE_ID = "4bf92f3577b34da6a3ce929d0e0e4736"
TRACEPARENT = f"00-{TRACE_ID}-00f067aa0ba902b7-01"
FORBIDDEN_LOG_FRAGMENTS = (
    "Bearer",
    "bearer",
    "raw-secret-token",
    "local-token-alpha",
    "jti-",
    "token_id",
    "secret",
    "client_secret",
    "access_token",
    "refresh_token",
    "api_key",
    "123.456.789-09",
    "12345678909",
    "12.345.678/0001-90",
    "12345678000190",
    "cliente.sensivel@example.com",
    "payload bruto",
    "renda_mensal",
    "100000",
)
FORBIDDEN_LOG_KEYS = frozenset(
    {
        "authorization",
        "x-creditos-token-id",
        "token_id",
        "jti",
        "client_secret",
        "access_token",
        "refresh_token",
        "api_key",
        "secret",
        "password",
        "senha",
    }
)
FORBIDDEN_LOG_VALUE_PATTERNS = (
    re.compile(r"(?i)\bbearer\s+[A-Za-z0-9._~+/-]+=*"),
    re.compile(r"\b\d{3}\.?\d{3}\.?\d{3}-?\d{2}\b"),
    re.compile(r"\b\d{2}\.?\d{3}\.?\d{3}/?\d{4}-?\d{2}\b"),
    re.compile(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", re.IGNORECASE),
)

SAFE_ERROR_EXPECTATIONS: dict[type[Exception], tuple[str, str, str]] = {
    MissingTokenError: ("missing_token", "token inválido", "UNAUTHENTICATED"),
    InvalidTokenError: ("invalid_token", "token inválido", "UNAUTHENTICATED"),
    ExpiredTokenError: ("expired_token", "token inválido", "UNAUTHENTICATED"),
    InvalidTokenIssuerError: ("invalid_token_issuer", "token inválido", "UNAUTHENTICATED"),
    InvalidTokenAudienceError: ("invalid_token_audience", "token inválido", "UNAUTHENTICATED"),
    MissingTokenRequiredClaimError: (
        "missing_token_required_claim",
        "token inválido",
        "UNAUTHENTICATED",
    ),
    InsufficientScopeError: ("insufficient_scope", "autorização negada", "PERMISSION_DENIED"),
    InsufficientRoleError: ("insufficient_role", "autorização negada", "PERMISSION_DENIED"),
    CrossTenantAccessDeniedError: (
        "cross_tenant_access_denied",
        "acesso cross-tenant negado",
        "PERMISSION_DENIED",
    ),
    InvalidAuthorizationRequirementError: (
        "invalid_authorization_requirement",
        "requisito de autorização inválido",
        "PERMISSION_DENIED",
    ),
    InvalidTrustedContextError: (
        "invalid_trusted_context",
        "contexto confiável inválido",
        "PERMISSION_DENIED",
    ),
}


def test_epic1_security_gate_matrix_documents_required_blocking_controls() -> None:
    readme = (ROOT / "services" / "identity-tenant" / "README.md").read_text(encoding="utf-8")

    required_rows = (
        "| Autenticação M2M negativa |",
        "| Autorização e cross-tenant |",
        "| Contexto confiável gRPC/CloudEvents |",
        "| Logs mascarados e rastreáveis |",
        "| CI bloqueante |",
    )
    for row in required_rows:
        assert row in readme

    assert "services/identity-tenant/tests/integration/test_epic1_security_gates.py" in readme
    assert "sem nova tecnologia" in readme
    assert "CTOS-135" in readme


@pytest.mark.parametrize(
    ("authorization_header", "claims_factory", "expected_error"),
    [
        (None, None, MissingTokenError),
        ("Bearer unknown-token", None, InvalidTokenError),
        (
            "Bearer local-token-alpha",
            lambda: _claims(expires_at=NOW - timedelta(seconds=1)),
            ExpiredTokenError,
        ),
        (
            "Bearer local-token-alpha",
            lambda: _claims(not_before=NOW + timedelta(seconds=1)),
            InvalidTokenError,
        ),
        (
            "Bearer local-token-alpha",
            lambda: _claims(issuer="https://evil.example"),
            InvalidTokenIssuerError,
        ),
        (
            "Bearer local-token-alpha",
            lambda: _claims(audience="other-api"),
            InvalidTokenAudienceError,
        ),
        ("Bearer local-token-alpha", lambda: _claims(algorithm="none"), InvalidTokenError),
        ("Bearer local-token-alpha", lambda: _claims(key_id="unknown-kid"), InvalidTokenError),
        (
            "Bearer local-token-alpha",
            lambda: _claims(signature_valid=False),
            InvalidTokenError,
        ),
        (
            "Bearer local-token-alpha",
            lambda: _claims(scopes=("decision:read",)),
            InvalidTokenError,
        ),
        (
            "Bearer local-token-alpha",
            lambda: _claims(subject=""),
            MissingTokenRequiredClaimError,
        ),
        (
            "Bearer local-token-alpha",
            lambda: _claims(client_id=""),
            MissingTokenRequiredClaimError,
        ),
        (
            "Bearer local-token-alpha",
            lambda: _claims(tenant_id=""),
            MissingTokenRequiredClaimError,
        ),
        (
            "Bearer local-token-alpha",
            lambda: _claims(tenant_isolation_tier=""),
            MissingTokenRequiredClaimError,
        ),
        (
            "Bearer local-token-alpha",
            lambda: _claims(scopes=()),
            MissingTokenRequiredClaimError,
        ),
        (
            "Bearer local-token-alpha",
            lambda: _claims(token_id=""),
            MissingTokenRequiredClaimError,
        ),
        (
            "Bearer local-token-alpha",
            lambda: _claims(issued_at=None),  # type: ignore[arg-type]
            MissingTokenRequiredClaimError,
        ),
        (
            "Bearer local-token-alpha",
            lambda: _claims(expires_at=None),  # type: ignore[arg-type]
            MissingTokenRequiredClaimError,
        ),
    ],
)
def test_epic1_gate_rejects_m2m_authentication_failures_without_sensitive_logs(
    authorization_header: str | None,
    claims_factory: Callable[[], LocalM2MTokenClaims] | None,
    expected_error: type[Exception],
) -> None:
    logger = InMemoryOperationLogger()
    service = _service_with_m2m(logger, claims_factory() if claims_factory is not None else None)

    with pytest.raises(expected_error) as raised:
        service.resolve_m2m_tenant_context(
            ResolveM2MTenantContextCommand(
                authorization_header=authorization_header,
                payload_tenant_id="tenant_alpha",
                now=NOW,
            ),
            context=ObservabilityContext.new(
                correlation_id="corr-auth-fail",
                request_id="req-auth-fail",
                trace_id=TRACE_ID,
                tenant_id="tenant_spoofed",
                tenant_isolation_tier="silo",
            ),
        )

    _assert_safe_error_shape(raised.value, expected_error)
    event = logger.events[-1]
    assert event["operation"] == "identity_tenant.resolve_m2m_tenant_context"
    assert event["source"] == "m2m-token-context"
    assert event["status"] == "rejected"
    assert event["payload"] == "[OMITIDO]"
    assert event["correlation_id"] == "corr-auth-fail"
    assert event["request_id"] == "req-auth-fail"
    assert event["trace_id"] == TRACE_ID
    assert "tenant_id" not in event
    assert "tenant_isolation_tier" not in event
    _assert_no_sensitive_log_leakage(event)


def test_epic1_gate_accepts_valid_m2m_authentication_with_traceable_masked_logs() -> None:
    logger = InMemoryOperationLogger()
    service = _service_with_m2m(logger, _claims())

    result = service.resolve_m2m_tenant_context(
        ResolveM2MTenantContextCommand(
            authorization_header="Bearer local-token-alpha",
            payload_tenant_id="tenant_alpha",
            now=NOW,
        ),
        context=ObservabilityContext.new(
            correlation_id="corr-auth-ok",
            request_id="req-auth-ok",
            trace_id=TRACE_ID,
        ),
    )

    assert result["tenant_id"] == "tenant_alpha"
    assert result["tenant_isolation_tier"] == "bridge"
    event = logger.events[-1]
    assert event["operation"] == "identity_tenant.resolve_m2m_tenant_context"
    assert event["source"] == "m2m-token-context"
    assert event["status"] == "accepted"
    assert event["tenant_id"] == "tenant_alpha"
    assert event["tenant_isolation_tier"] == "bridge"
    assert event["correlation_id"] == "corr-auth-ok"
    assert event["request_id"] == "req-auth-ok"
    assert event["trace_id"] == TRACE_ID
    _assert_no_sensitive_log_leakage(event)


@pytest.mark.parametrize(
    ("command", "expected_error", "denial_reason"),
    [
        (
            lambda: _authorize_command(scopes=("decision:read",), roles=("service-client",)),
            InsufficientScopeError,
            "insufficient_scope",
        ),
        (
            lambda: _authorize_command(scopes=("proposal:submit",), roles=("viewer",)),
            InsufficientRoleError,
            "insufficient_role",
        ),
        (
            lambda: _authorize_command(
                scopes=("proposal:submit",),
                roles=("service-client",),
                resource_tenant_id="tenant_beta",
            ),
            CrossTenantAccessDeniedError,
            "cross_tenant_access_denied",
        ),
        (
            lambda: _authorize_command(
                scopes=("proposal:submit",),
                roles=("service-client",),
                operation="proposal.delete",
            ),
            InvalidAuthorizationRequirementError,
            "invalid_authorization_requirement",
        ),
    ],
)
def test_epic1_gate_rejects_authorization_and_cross_tenant_failures_safely(
    command: Callable[[], AuthorizeOperationCommand],
    expected_error: type[Exception],
    denial_reason: str,
) -> None:
    logger = InMemoryOperationLogger()
    service = TenantApplicationService(
        repository=InMemoryTenantRepository(),
        operation_logger=logger,
        environment="test",
    )

    with pytest.raises(expected_error) as raised:
        service.authorize_operation(
            command(),
            context=ObservabilityContext.new(
                correlation_id="corr-authz-denied",
                request_id="req-authz-denied",
                trace_id=TRACE_ID,
            ),
        )

    _assert_safe_error_shape(raised.value, expected_error)
    event = logger.events[-1]
    assert event["operation"] == "identity_tenant.authorize_operation"
    assert event["source"] == "authorization-context"
    assert event["status"] == "rejected"
    assert event["tenant_id"] == "tenant_alpha"
    assert event["tenant_isolation_tier"] == "bridge"
    assert event["extra"]["authz_decision"] == "denied"
    assert event["extra"]["denial_reason"] == denial_reason
    assert event["correlation_id"] == "corr-authz-denied"
    assert event["request_id"] == "req-authz-denied"
    assert event["trace_id"] == TRACE_ID
    _assert_no_sensitive_log_leakage(event)


def test_epic1_gate_accepts_valid_authorization_with_traceable_masked_logs() -> None:
    logger = InMemoryOperationLogger()
    service = TenantApplicationService(
        repository=InMemoryTenantRepository(),
        operation_logger=logger,
        environment="test",
    )

    decision = service.authorize_operation(
        _authorize_command(scopes=("proposal:submit", "decision:read"), roles=("service-client",)),
        context=ObservabilityContext.new(
            correlation_id="corr-authz-ok",
            request_id="req-authz-ok",
            trace_id=TRACE_ID,
        ),
    )

    assert decision["granted"] is True
    event = logger.events[-1]
    assert event["operation"] == "identity_tenant.authorize_operation"
    assert event["source"] == "authorization-context"
    assert event["status"] == "accepted"
    assert event["tenant_id"] == "tenant_alpha"
    assert event["tenant_isolation_tier"] == "bridge"
    assert event["extra"]["authz_decision"] == "granted"
    assert event["correlation_id"] == "corr-authz-ok"
    assert event["request_id"] == "req-authz-ok"
    assert event["trace_id"] == TRACE_ID
    _assert_no_sensitive_log_leakage(event)


def test_epic1_gate_rejects_authorization_requirements_outside_registry() -> None:
    with pytest.raises(InvalidAuthorizationRequirementError) as raised:
        AuthorizationRequirement(
            operation="proposal.submit",
            required_scopes=("proposal:submit",),
            required_roles=("service-client",),
        )
    _assert_safe_error_shape(raised.value, InvalidAuthorizationRequirementError)


@pytest.mark.parametrize(
    "mutation",
    [
        "missing_x-correlation-id",
        "missing_x-request-id",
        "missing_traceparent",
        "missing_x-creditos-tenant-id",
        "missing_x-creditos-tenant-isolation-tier",
        "missing_x-creditos-subject-id",
        "missing_x-creditos-principal-type",
        "missing_x-creditos-scopes",
        "missing_x-creditos-schema-version",
        "duplicated_tenant",
        "sensitive_key",
        "binary_key",
        "uppercase_key",
        "malformed_scope",
        "tenant_mismatch",
        "invalid_traceparent",
    ],
)
def test_epic1_gate_rejects_untrusted_grpc_context_before_rebuilding_subject(
    mutation: str,
) -> None:
    logger = InMemoryOperationLogger()
    context = ObservabilityContext.new(
        correlation_id="corr-grpc",
        request_id="req-grpc",
        trace_id=TRACE_ID,
        tenant_id="tenant_spoofed",
        tenant_isolation_tier="silo",
    )
    metadata: object = grpc_metadata_from_authorization_subject(_subject(), context)
    expected_tenant_id = "tenant_alpha"

    match mutation:
        case mutation_name if mutation_name.startswith("missing_"):
            missing_key = mutation_name.removeprefix("missing_")
            metadata = tuple(
                (key, value)
                for key, value in metadata  # type: ignore[union-attr]
                if key != missing_key
            )
        case "duplicated_tenant":
            metadata = (*metadata, ("x-creditos-tenant-id", "tenant_beta"))  # type: ignore[misc]
        case "sensitive_key":
            metadata = (("x-creditos-token-id", "raw-secret-token"), *metadata)  # type: ignore[misc]
        case "binary_key":
            metadata = (("x-creditos-tenant-id-bin", "tenant_alpha"), *metadata)  # type: ignore[misc]
        case "uppercase_key":
            metadata = (("X-Creditos-Tenant-Id", "tenant_alpha"), *metadata)  # type: ignore[misc]
        case "malformed_scope":
            carrier = dict(metadata)  # type: ignore[arg-type]
            carrier["x-creditos-scopes"] = "proposal:submit decision:read!"
            metadata = carrier
        case "tenant_mismatch":
            expected_tenant_id = "tenant_beta"
        case "invalid_traceparent":
            carrier = dict(metadata)  # type: ignore[arg-type]
            carrier["traceparent"] = "invalid"
            metadata = carrier

    with pytest.raises(InvalidTrustedContextError) as raised:
        authorization_subject_from_grpc_metadata(
            metadata,  # type: ignore[arg-type]
            expected_tenant_id=expected_tenant_id,
            operation_logger=logger,
            observability_context=context,
            environment="test",
        )

    _assert_safe_error_shape(raised.value, InvalidTrustedContextError)
    event = logger.events[-1]
    assert event["operation"] == "identity_tenant.validate_grpc_trusted_context"
    assert event["source"] == "trusted-context"
    assert event["status"] == "rejected"
    assert event["correlation_id"] == "corr-grpc"
    assert event["request_id"] == "req-grpc"
    assert event["trace_id"] == TRACE_ID
    assert "tenant_id" not in event
    assert "tenant_isolation_tier" not in event
    _assert_no_sensitive_log_leakage(event)


def test_epic1_gate_accepts_valid_grpc_context_without_rejection_logs() -> None:
    logger = InMemoryOperationLogger()
    context = ObservabilityContext.new(
        correlation_id="corr-grpc-ok",
        request_id="req-grpc-ok",
        trace_id=TRACE_ID,
    )

    subject = authorization_subject_from_grpc_metadata(
        grpc_metadata_from_authorization_subject(_subject(), context),
        expected_tenant_id="tenant_alpha",
        operation_logger=logger,
        observability_context=context,
        environment="test",
    )

    assert subject.subject_id == "client-alpha"
    assert subject.tenant_id == "tenant_alpha"
    assert subject.tenant_isolation_tier == "bridge"
    assert subject.scopes == frozenset({"proposal:submit", "decision:read"})
    assert subject.roles == frozenset({"service-client"})
    assert logger.events == []


@pytest.mark.parametrize(
    "mutation",
    [
        "invalid_specversion",
        "missing_id",
        "missing_source",
        "missing_type",
        "missing_subject",
        "missing_time",
        "missing_datacontenttype",
        "underscore_extension",
        "missing_tenantid",
        "missing_tenanttier",
        "missing_subjectid",
        "missing_principaltype",
        "missing_scopes",
        "missing_correlationid",
        "missing_requestid",
        "missing_traceparent",
        "missing_schemaversion",
        "missing_idempotencykey",
        "invalid_traceparent",
        "sensitive_attribute",
        "tenant_mismatch",
        "payload_attribute",
    ],
)
def test_epic1_gate_rejects_untrusted_cloudevent_context_before_use_case(
    mutation: str,
) -> None:
    logger = InMemoryOperationLogger()
    context = ObservabilityContext.new(
        correlation_id="corr-event",
        request_id="req-event",
        trace_id=TRACE_ID,
        tenant_id="tenant_spoofed",
        tenant_isolation_tier="silo",
    )
    attributes = _cloudevent_attributes()
    expected_tenant_id = "tenant_alpha"

    match mutation:
        case "invalid_specversion":
            attributes["specversion"] = "0.3"
        case mutation_name if mutation_name.startswith("missing_"):
            del attributes[mutation_name.removeprefix("missing_")]
        case "underscore_extension":
            attributes["tenant_id"] = "tenant_alpha"
        case "invalid_traceparent":
            attributes["traceparent"] = "invalid"
        case "sensitive_attribute":
            attributes["authorization"] = "Bearer raw-secret-token"
        case "tenant_mismatch":
            expected_tenant_id = "tenant_beta"
        case "payload_attribute":
            attributes["payload"] = "payload bruto com cliente.sensivel@example.com"

    with pytest.raises(InvalidTrustedContextError) as raised:
        event_context_from_cloudevent_attributes(
            attributes,
            expected_tenant_id=expected_tenant_id,
            operation_logger=logger,
            observability_context=context,
            environment="test",
        )

    _assert_safe_error_shape(raised.value, InvalidTrustedContextError)
    event = logger.events[-1]
    assert event["operation"] == "identity_tenant.validate_cloudevent_trusted_context"
    assert event["source"] == "trusted-context"
    assert event["status"] == "rejected"
    assert event["correlation_id"] == "corr-event"
    assert event["request_id"] == "req-event"
    assert event["trace_id"] == TRACE_ID
    assert "tenant_id" not in event
    assert "tenant_isolation_tier" not in event
    _assert_no_sensitive_log_leakage(event)


def test_epic1_gate_accepts_valid_cloudevent_context_without_rejection_logs() -> None:
    logger = InMemoryOperationLogger()
    context = ObservabilityContext.new(
        correlation_id="corr-event-ok",
        request_id="req-event-ok",
        trace_id=TRACE_ID,
    )

    event_context = event_context_from_cloudevent_attributes(
        _cloudevent_attributes(),
        expected_tenant_id="tenant_alpha",
        operation_logger=logger,
        observability_context=context,
        environment="test",
    )

    assert event_context.event_id == "event-alpha"
    assert event_context.event_type == "creditos.proposal.v1.submitted"
    assert event_context.context.trusted.subject_id == "client-alpha"
    assert event_context.context.trusted.tenant_id == "tenant_alpha"
    assert event_context.idempotency_key == "idem-alpha"
    assert logger.events == []


def test_epic1_gate_preserves_ci_and_local_blocking_commands() -> None:
    workflow = CI_WORKFLOW.read_text(encoding="utf-8")
    dev_script = DEV_SCRIPT.read_text(encoding="utf-8")

    workflow_commands = (
        "uv lock --check",
        "uv sync --locked",
        "uv run ruff check .",
        "uv run ruff format --check .",
        "uv run pyright",
        "uv run python scripts/check_contracts.py",
        "uv run python scripts/local_harness.py check",
        "uv run pytest",
        "ghcr.io/gitleaks/gitleaks@sha256:",
        "--redact=100",
        "--exit-code 1",
    )
    local_commands = (
        "uv lock --check",
        "uv sync --locked",
        "uv run ruff check .",
        "uv run ruff format --check .",
        "uv run pyright",
        "uv run python scripts/check_contracts.py",
        "uv run python scripts/local_harness.py check",
        "uv run pytest",
    )

    for command in workflow_commands:
        assert command in _workflow_quality_gate_blocks(workflow)
    for command in local_commands:
        assert command in _dev_all_block(dev_script)

    assert "continue-on-error" not in workflow
    assert "paths:" not in workflow
    assert "paths-ignore:" not in workflow
    assert "pull_request_target" not in workflow


def _service_with_m2m(
    logger: InMemoryOperationLogger,
    claims: LocalM2MTokenClaims | None,
) -> TenantApplicationService:
    repository = InMemoryTenantRepository()
    repository.save_unique(
        Tenant.create(
            tenant_id="tenant_alpha",
            name="Financeira Alpha",
            status="active",
            operator_id="operator-platform",
        )
    )
    tokens = {"local-token-alpha": claims} if claims is not None else {}
    verifier = LocalM2MTokenVerifier(
        issuer="https://issuer.creditos.local",
        audience="creditos-api",
        trusted_key_ids={"kid-local"},
        required_scopes=("proposal:submit",),
        tokens=tokens,
    )
    return TenantApplicationService(
        repository=repository,
        operation_logger=logger,
        m2m_token_verifier=verifier,
        environment="test",
    )


def _claims(
    *,
    issuer: str = "https://issuer.creditos.local",
    audience: str = "creditos-api",
    subject: str = "client-alpha",
    client_id: str = "client-alpha",
    tenant_id: str = "tenant_alpha",
    tenant_isolation_tier: str = "bridge",
    scopes: tuple[str, ...] = ("proposal:submit", "decision:read"),
    token_id: str = "jti-local-alpha",
    issued_at: datetime = NOW - timedelta(minutes=1),
    expires_at: datetime = NOW + timedelta(minutes=5),
    not_before: datetime | None = None,
    key_id: str = "kid-local",
    algorithm: str = "RS256",
    signature_valid: bool = True,
) -> LocalM2MTokenClaims:
    return LocalM2MTokenClaims(
        issuer=issuer,
        audience=audience,
        subject=subject,
        client_id=client_id,
        tenant_id=tenant_id,
        tenant_isolation_tier=tenant_isolation_tier,
        scopes=scopes,
        token_id=token_id,
        issued_at=issued_at,
        expires_at=expires_at,
        not_before=not_before,
        key_id=key_id,
        algorithm=algorithm,
        signature_valid=signature_valid,
    )


def _authorize_command(
    *,
    scopes: tuple[str, ...],
    roles: tuple[str, ...],
    operation: str = "proposal.submit",
    resource_tenant_id: str = "tenant_alpha",
) -> AuthorizeOperationCommand:
    return AuthorizeOperationCommand(
        subject=_subject(scopes=scopes, roles=roles),
        operation=operation,
        resource=ProtectedResource(
            resource_type="proposal",
            resource_id="proposal-123",
            tenant_id=resource_tenant_id,
        ),
    )


def _subject(
    *,
    scopes: tuple[str, ...] = ("proposal:submit", "decision:read"),
    roles: tuple[str, ...] = ("service-client",),
) -> AuthorizationSubject:
    return AuthorizationSubject(
        subject_id="client-alpha",
        tenant_id="tenant_alpha",
        tenant_isolation_tier="bridge",
        scopes=scopes,
        roles=roles,
        client_id="client-alpha",
        token_id="jti-local-alpha",
    )


def _cloudevent_attributes() -> dict[str, str]:
    context = ObservabilityContext.new(
        correlation_id="corr-event",
        request_id="req-event",
        trace_id=TRACE_ID,
    )
    propagated = context_to_cloudevent_attributes(
        propagated_context_from_authorization_subject(_subject(), context),
        idempotency_key="idem-alpha",
    )
    return {
        "specversion": "1.0",
        "id": "event-alpha",
        "source": "identity-tenant",
        "type": "creditos.proposal.v1.submitted",
        "subject": "proposal-alpha",
        "time": "2026-08-12T00:00:00Z",
        "datacontenttype": "application/json",
        **propagated,
    }


def _assert_no_sensitive_log_leakage(event: dict[str, object]) -> None:
    serialized_event = json.dumps(event, ensure_ascii=False)
    for fragment in FORBIDDEN_LOG_FRAGMENTS:
        assert fragment not in serialized_event
        assert fragment.casefold() not in serialized_event.casefold()
    for pattern in FORBIDDEN_LOG_VALUE_PATTERNS:
        assert pattern.search(serialized_event) is None
    _assert_no_sensitive_keys(event)


def _assert_no_sensitive_keys(value: object) -> None:
    if isinstance(value, dict):
        for key, nested_value in value.items():
            assert key.casefold() not in FORBIDDEN_LOG_KEYS
            _assert_no_sensitive_keys(nested_value)
    elif isinstance(value, list | tuple | set | frozenset):
        for nested_value in value:
            _assert_no_sensitive_keys(nested_value)


def _assert_safe_error_shape(error: Exception, expected_error: type[Exception]) -> None:
    expected_code, expected_safe_message, expected_grpc_status = SAFE_ERROR_EXPECTATIONS[
        expected_error
    ]
    assert isinstance(error, expected_error)
    assert error.code == expected_code  # type: ignore[attr-defined]
    assert error.safe_message == expected_safe_message  # type: ignore[attr-defined]
    assert error.grpc_status == expected_grpc_status  # type: ignore[attr-defined]
    _assert_no_sensitive_log_leakage({"error": str(error)})


def _workflow_quality_gate_blocks(workflow: str) -> str:
    gate_names = (
        "Scan repository for secrets",
        "Check uv lockfile",
        "Sync locked dependencies",
        "Run Ruff lint",
        "Run Ruff format check",
        "Run Pyright",
        "Validate versioned contracts",
        "Validate local harness",
        "Run pytest",
    )
    blocks = [_workflow_step_block(workflow, gate_name) for gate_name in gate_names]
    for block in blocks:
        assert "run:" in block
        assert "if: false" not in block
        assert "continue-on-error" not in block
    return "\n".join(blocks)


def _workflow_step_block(workflow: str, step_name: str) -> str:
    marker = f"      - name: {step_name}"
    start = workflow.find(marker)
    assert start != -1, f"Step '{step_name}' não encontrado no workflow"
    next_step = workflow.find("\n      - name:", start + len(marker))
    return workflow[start:] if next_step == -1 else workflow[start:next_step]


def _dev_all_block(dev_script: str) -> str:
    marker = "  all)"
    start = dev_script.find(marker)
    assert start != -1, "Comando './scripts/dev all' deve existir"
    next_command = dev_script.find("\n  help)", start)
    assert next_command != -1, "Fim do bloco './scripts/dev all' não encontrado"
    block = dev_script[start:next_command]
    assert ";;" in block
    return block
