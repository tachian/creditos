from __future__ import annotations

import json
import re
import unicodedata
from collections import Counter
from collections.abc import Mapping, Sequence
from dataclasses import fields, is_dataclass
from datetime import UTC, datetime
from decimal import Decimal
from enum import Enum
from types import MappingProxyType
from typing import Any
from uuid import UUID

import pytest
from creditos_audit_evidence.adapters.persistence import InMemoryAuditEventRepository
from creditos_audit_evidence.application.service import AuditEvidenceApplicationService
from creditos_audit_evidence.domain.entities import AuditEvent, OperationalEvidenceReference
from creditos_automated_review.adapters.external.audit_evidence_publisher import (
    AuditEvidenceAutomatedReviewAuditPublisher,
)
from creditos_automated_review.application.ports import AutomatedReviewAuditIntent
from creditos_decision.adapters.external.audit_evidence_publisher import (
    AuditEvidenceDecisionAuditPublisher,
    AuditEvidenceDecisionSensitiveChangeAuditPublisher,
)
from creditos_decision.application.ports import (
    CreditDecisionAuditIntent,
    CreditPolicyAuditIntent,
)
from creditos_integration.application.ports.audit_event_publisher import IntegrationAuditEvent
from creditos_integration.application.ports.integration_execution import IntegrationExecutionEvent
from creditos_observability import ObservabilityContext
from creditos_observability.logging import build_structured_log
from creditos_observability.telemetry import InMemoryTelemetry
from creditos_proposal_intake.domain.entities import ProposalOutboxMessage
from creditos_security.masking import FINANCIAL_OMITTED, OMITTED, mask_sensitive_data

NOW = datetime(2026, 9, 22, 12, 0, tzinfo=UTC)
TRACE_ID = "1234567890abcdef1234567890abcdef"
TRACEPARENT = f"00-{TRACE_ID}-1234567890abcdef-01"
ALLOWED_PLACEHOLDERS = {OMITTED, FINANCIAL_OMITTED, "false", "true"}

VALUE_PATTERNS = (
    ("cpf", re.compile(r"(?<!\d)(?:\d{3}\.?\d{3}\.?\d{3}-?\d{2})(?!\d)")),
    ("cnpj", re.compile(r"(?<!\d)(?:\d{2}\.?\d{3}\.?\d{3}/?\d{4}-?\d{2})(?!\d)")),
    ("email", re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b")),
    ("telefone", re.compile(r"\(?\b\d{2}\)?\s?\d{4,5}-?\d{4}\b")),
    ("authorization_bearer", re.compile(r"(?i)\bauthorization\s*[:=]\s*bearer\s+\S+")),
    (
        "secret_assignment",
        re.compile(
            r"(?i)\b(?:api[_-]?key|access[_-]?token|refresh[_-]?token|password|senha|secret)"
            r"\b\s*[:=]\s*[^\s,;}\]]+"
        ),
    ),
)
SENSITIVE_PATH_TOKENS = {
    "authorization",
    "api_key",
    "apikey",
    "access_token",
    "refresh_token",
    "client_secret",
    "cookie",
    "set_cookie",
    "headers",
    "payload",
    "raw",
    "external_payload",
    "request_body",
    "response_body",
    "request_headers",
    "response_headers",
    "provider_payload",
    "prompt",
    "completion",
    "output",
    "ai_output",
    "model_output",
    "llm_output",
    "provider_output",
    "embedding",
    "document",
    "documento",
    "document_image",
    "image",
    "imagem",
    "attachment",
    "anexo",
    "renda",
    "renda_mensal",
    "income",
    "salary",
    "token",
    "secret",
    "password",
    "senha",
}
SENSITIVE_PATH_FRAGMENTS = (
    "authorization",
    "credential",
    "password",
    "senha",
    "secret",
    "token",
    "cookie",
    "headers",
    "payload",
    "request_body",
    "response_body",
    "provider_payload",
    "prompt",
    "completion",
    "output",
    "embedding",
    "document",
    "documento",
    "imagem",
    "image",
    "attachment",
    "anexo",
    "renda",
    "income",
    "salary",
    "faturamento",
    "revenue",
    "financial",
    "financeiro",
    "credit_limit",
)
SENSITIVE_PATH_SUFFIXES = ("api_key", "apikey", "private_key", "public_key")
SAFE_TECHNICAL_SUFFIXES = (
    "_id",
    "_ref",
    "_refs",
    "_version",
    "_version_id",
    "_fingerprint",
    "_digest",
    "_persisted",
)
SAFE_TECHNICAL_KEYS = {
    "contract",
    "contract_version",
    "correlation_id",
    "decision_id",
    "event_id",
    "fingerprint",
    "operation",
    "policy_id",
    "policy_version_id",
    "product_type",
    "proposal_id",
    "reason_code_catalog_id",
    "reason_code_catalog_version_id",
    "review_agent_config_id",
    "review_agent_config_version_id",
    "request_id",
    "schema_version",
    "source_event_id",
    "status",
    "technical_result",
    "tenant_id",
    "tenant_isolation_tier",
    "trace_id",
}


def test_sensitive_leak_gate_helper_redacts_findings_without_echoing_values() -> None:
    raw_artifact = {
        "subject_document": "000.000.000-00",
        "cnpj": "00.000.000/0000-00",
        "email": "pessoa.sintetica@example.test",
        "telefone": "(00) 00000-0000",
        "authorization": "Bearer valor-local",
        "_".join(("api", "key")): "valor-local",
        "_".join(("access", "token")): "valor-local",
        "_".join(("refresh", "token")): "valor-local",
        "ｐａｙｌｏａｄ": {"ｐｒｏｍｐｔ": "texto bruto de análise"},
        "payload": {"raw_prompt_id": "transcricao integral sem regex"},
        "documento": "arquivo sintético bruto",
        "document_image": b"imagem-sintetica-bruta",
        "raw_output": "resultado bruto de análise",
        "renda_mensal": 123456,
    }

    with pytest.raises(AssertionError) as error:
        assert_artifact_has_no_sensitive_leaks("raw_fixture", raw_artifact)

    message = str(error.value)
    assert "raw_fixture.subject_document" in message
    assert "raw_fixture.authorization" in message
    assert "raw_fixture.payload.raw_prompt_id" in message
    assert "raw_fixture.renda_mensal" in message
    assert "000.000.000-00" not in message
    assert "pessoa.sintetica@example.test" not in message
    assert "valor-local" not in message
    assert "transcricao integral" not in message


def test_sensitive_leak_gate_normalizes_anomalous_types_without_raw_output() -> None:
    safe_artifact = {
        "event_ids": {"audit_evt_a", "audit_evt_b"},
        "operation": _SyntheticOperation.APPROVED,
        "risk_score": Decimal("0.42"),
        "technical_reference": UUID("00000000-0000-4000-8000-000000000001"),
    }

    assert_artifact_has_no_sensitive_leaks("safe_anomalous_types", safe_artifact)


def test_transversal_gate_keeps_logs_traces_events_and_safe_details_free_of_sensitive_data() -> (
    None
):
    context = _context()
    artifacts = {
        "structured_log": _structured_log(context),
        "telemetry_span_attributes": _telemetry_span_attributes(context),
        "audit_event": _audit_event(),
        "proposal_outbox": _proposal_outbox_message(),
        "integration_execution_event": _integration_execution_event().to_log_safe_dict(),
        "integration_audit_event": _integration_audit_event().to_log_safe_dict(),
        "masked_payload": mask_sensitive_data(_raw_sensitive_payload()),
    }

    for artifact_name, artifact in artifacts.items():
        assert_artifact_has_no_sensitive_leaks(artifact_name, artifact)

    assert artifacts["structured_log"]["correlation_id"] == "corr_epic6_gate_001"
    assert artifacts["structured_log"]["request_id"] == "req_epic6_gate_001"
    assert artifacts["structured_log"]["trace_id"] == TRACE_ID
    assert artifacts["structured_log"]["tenant_id"] == "tenant_alpha"
    assert artifacts["structured_log"]["technical_result"] == "accepted"
    assert artifacts["telemetry_span_attributes"]["correlation_id"] == "corr_epic6_gate_001"
    assert artifacts["telemetry_span_attributes"]["tenant_id"] == "tenant_alpha"
    assert artifacts["integration_execution_event"]["data_keys"] == ("status",)


def test_critical_audit_publishers_append_official_events_with_minimum_context() -> None:
    repository = InMemoryAuditEventRepository()
    audit_service = AuditEvidenceApplicationService(repository=repository, environment="test")
    decision_publisher = AuditEvidenceDecisionAuditPublisher(
        audit_service=audit_service,
        clock=lambda: NOW,
        occurrence_token_factory=lambda: "decision_occurrence",
    )
    sensitive_change_publisher = AuditEvidenceDecisionSensitiveChangeAuditPublisher(
        audit_service=audit_service,
        clock=lambda: NOW,
        occurrence_token_factory=lambda: "policy_occurrence",
    )
    review_publisher = AuditEvidenceAutomatedReviewAuditPublisher(
        audit_service=audit_service,
        clock=lambda: NOW,
        occurrence_token_factory=lambda: "review_occurrence",
    )

    decision_publisher.publish(_credit_decision_intent())
    sensitive_change_publisher.publish(_credit_policy_intent())
    review_publisher.publish(_automated_review_config_intent())

    events = repository.list_by_tenant_chain(tenant_id="tenant_alpha")

    assert len(events) == 3
    assert Counter(event.event_type for event in events) == Counter(
        {
            "credit_decision.completed": 1,
            "credit_policy.published": 1,
            "automated_review.config.published": 1,
        }
    )
    for event in events:
        assert_official_audit_context(event)
        assert_artifact_has_no_sensitive_leaks(event.event_type, event)


def test_operational_evidence_cannot_replace_official_audit_event() -> None:
    with pytest.raises(AssertionError, match="evento oficial de auditoria"):
        assert_official_audit_context(
            {
                "tenant_id": "tenant_alpha",
                "correlation_id": "corr_epic6_gate_001",
                "trace_id": TRACE_ID,
                "request_id": "req_epic6_gate_001",
                "operation": "credit_decision.execute",
                "status": "accepted",
                "log_reference": "log_credit_decision_001",
            }
        )


def assert_artifact_has_no_sensitive_leaks(artifact_name: str, artifact: Any) -> None:
    normalized_artifact = _normalize_artifact(artifact)
    findings: list[str] = []
    serialized_artifact = json.dumps(
        normalized_artifact,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    normalized_text = unicodedata.normalize("NFKC", serialized_artifact)
    for pattern_name, pattern in VALUE_PATTERNS:
        if pattern.search(normalized_text):
            findings.append(f"{pattern_name} em {artifact_name}")
    findings.extend(_sensitive_path_findings(artifact_name, normalized_artifact))
    if findings:
        safe_findings = "; ".join(sorted(set(findings)))
        raise AssertionError(f"vazamento sensível detectado: {safe_findings}")


def assert_official_audit_context(event: AuditEvent | Mapping[str, Any]) -> None:
    if not isinstance(event, AuditEvent):
        raise AssertionError("evento oficial de auditoria é obrigatório")

    required_values = {
        "tenant_id": event.tenant_id,
        "actor_subject_id": event.actor_subject_id,
        "resource_type": event.resource_type,
        "resource_id": event.resource_id,
        "result": event.result,
        "correlation_id": event.correlation_id,
        "trace_id": event.trace_id,
        "request_id": event.request_id,
        "source_service": event.source_service,
        "source_kind": event.source_kind,
    }
    missing_fields = sorted(
        field_name for field_name, value in required_values.items() if not value
    )
    assert missing_fields == []
    assert event.operational_evidence_refs
    assert event.operational_evidence_refs[0].kind == "trace"
    assert event.operational_evidence_refs[0].reference == event.trace_id
    assert event.safe_details.get("operation") is not None
    assert event.safe_details.get("status") is not None
    _assert_event_versions(event)


def _sensitive_path_findings(artifact_name: str, value: Any) -> list[str]:
    findings: list[str] = []
    for path, leaf_value in _iter_leaf_values(value):
        normalized_leaf = str(leaf_value)
        for pattern_name, pattern in VALUE_PATTERNS:
            if pattern.search(normalized_leaf):
                findings.append(f"{pattern_name} em {artifact_name}{_format_path(path)}")
        if _is_sensitive_path(path) and not _is_allowed_sensitive_placeholder(path, leaf_value):
            findings.append(f"valor bruto em {artifact_name}{_format_path(path)}")
    return findings


def _iter_leaf_values(value: Any, path: tuple[str, ...] = ()) -> list[tuple[tuple[str, ...], Any]]:
    if isinstance(value, Mapping):
        leaves: list[tuple[tuple[str, ...], Any]] = []
        for raw_key, item_value in value.items():
            leaves.extend(_iter_leaf_values(item_value, (*path, str(raw_key))))
        return leaves
    if isinstance(value, Sequence) and not isinstance(value, str | bytes | bytearray):
        leaves = []
        for index, item_value in enumerate(value):
            leaves.extend(_iter_leaf_values(item_value, (*path, str(index))))
        return leaves
    return [(path, value)]


def _is_sensitive_path(path: tuple[str, ...]) -> bool:
    normalized_segments = {_normalize_path_segment(segment) for segment in path}
    return any(
        segment in SENSITIVE_PATH_TOKENS
        or any(fragment in segment for fragment in SENSITIVE_PATH_FRAGMENTS)
        or any(segment.endswith(suffix) for suffix in SENSITIVE_PATH_SUFFIXES)
        for segment in normalized_segments
    )


def _is_allowed_sensitive_placeholder(path: tuple[str, ...], value: Any) -> bool:
    normalized_value = str(value).strip()
    leaf_key = _normalize_path_segment(path[-1]) if path else ""
    if normalized_value in ALLOWED_PLACEHOLDERS:
        return True
    if leaf_key in SAFE_TECHNICAL_KEYS:
        return True
    if leaf_key in {"prompt_version", "prompt_fingerprint", "output_fingerprint"}:
        return True
    if _has_sensitive_ancestor(path):
        return False
    return bool(leaf_key.endswith(SAFE_TECHNICAL_SUFFIXES))


def _has_sensitive_ancestor(path: tuple[str, ...]) -> bool:
    return any(_is_sensitive_path(path[:index]) for index in range(1, len(path)))


def _normalize_path_segment(segment: str) -> str:
    normalized = unicodedata.normalize("NFKC", segment)
    without_controls = "".join(
        "" if unicodedata.category(character) in {"Cc", "Cf", "Zl", "Zp"} else character
        for character in normalized
    )
    return without_controls.lower().replace("-", "_").replace(".", "_")


def _format_path(path: tuple[str, ...]) -> str:
    return "".join(f".{segment}" for segment in path)


def _normalize_artifact(value: Any) -> Any:
    if isinstance(value, MappingProxyType):
        return {str(key): _normalize_artifact(item) for key, item in value.items()}
    if isinstance(value, Mapping):
        return {str(key): _normalize_artifact(item) for key, item in value.items()}
    if is_dataclass(value) and not isinstance(value, type):
        return {
            field.name: _normalize_artifact(getattr(value, field.name)) for field in fields(value)
        }
    if isinstance(value, set | frozenset):
        return tuple(sorted(str(_normalize_artifact(item)) for item in value))
    if isinstance(value, Decimal | UUID):
        return str(value)
    if isinstance(value, Enum):
        return _normalize_artifact(value.value)
    if isinstance(value, Sequence) and not isinstance(value, str | bytes | bytearray):
        return tuple(_normalize_artifact(item) for item in value)
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, bytes | bytearray | memoryview):
        return "[BYTES]"
    return value


def _assert_event_versions(event: AuditEvent) -> None:
    expected_safe_detail_keys_by_event_type = {
        "credit_decision.completed": {
            "policy_version_id",
            "reason_code_catalog_version_id",
            "fingerprint",
        },
        "credit_policy.published": {
            "policy_version_id",
            "previous_revision",
            "resulting_revision",
        },
        "automated_review.config.published": {
            "review_agent_config_version_id",
            "prompt_fingerprint",
            "prompt_version",
            "previous_revision",
            "resulting_revision",
        },
    }
    expected_keys = expected_safe_detail_keys_by_event_type.get(event.event_type, set())
    missing_keys = sorted(key for key in expected_keys if not event.safe_details.get(key))
    assert missing_keys == []


class _SyntheticOperation(Enum):
    APPROVED = "approved"


def _context() -> ObservabilityContext:
    return ObservabilityContext.new(
        correlation_id="corr_epic6_gate_001",
        request_id="req_epic6_gate_001",
        trace_id=TRACE_ID,
        tenant_id="tenant_alpha",
        tenant_isolation_tier="bridge",
    )


def _structured_log(context: ObservabilityContext) -> dict[str, Any]:
    return build_structured_log(
        context=context,
        service_name="audit-evidence",
        service_version="0.1.0",
        environment="test",
        operation="audit_event.register",
        source="audit-evidence.application",
        destination="audit-evidence.repository",
        contract="audit-event",
        contract_version="v1",
        status="accepted",
        technical_result="accepted",
        duration_ms=7.5,
        payload=_raw_sensitive_payload(),
        extra={
            "operation": "audit_event.register",
            "status": "accepted",
            "provider_payload": _raw_sensitive_payload(),
            "prompt": "análise com dados sintéticos",
            "raw_output": "resultado bruto sintético",
            "renda_mensal": 123456,
        },
    )


def _telemetry_span_attributes(context: ObservabilityContext) -> dict[str, Any]:
    telemetry = InMemoryTelemetry(service_name="automated-review", service_version="0.1.0")
    with telemetry.start_span(
        "automated_review.execute",
        context=context,
        attributes={
            "contract": "automated-review",
            "contract_version": "v1",
            "operation": "automated_review.execute",
            "prompt_version": "prompt_credit_review_v1",
            "prompt": "texto bruto não permitido",
            "output": "saída bruta não permitida",
            "email": "pessoa.sintetica@example.test",
        },
    ):
        pass
    spans = telemetry.finished_spans()
    assert len(spans) == 1
    return dict(spans[0].attributes or {})


def _audit_event() -> AuditEvent:
    return AuditEvent.create(
        event_id="audit_evt_epic6_gate_001",
        tenant_id="tenant_alpha",
        aggregate_type="audit_event",
        aggregate_id="audit_evt_source_001",
        event_type="audit_event.read",
        action="read",
        resource_type="audit_event",
        resource_id="audit_evt_source_001",
        actor_subject_id="audit-reader",
        source_service="audit_evidence",
        source_kind="grpc",
        result="accepted",
        occurred_at=NOW,
        correlation_id="corr_epic6_gate_001",
        trace_id=TRACE_ID,
        request_id="req_epic6_gate_001",
        safe_details={
            "operation": "audit_event.read",
            "status": "accepted",
            "outcome": "accepted",
            "source_event_id": "audit_evt_source_001",
        },
        operational_evidence_refs=(
            OperationalEvidenceReference(kind="trace", reference=TRACE_ID, source="otel"),
        ),
    )


def _proposal_outbox_message() -> ProposalOutboxMessage:
    return ProposalOutboxMessage(
        tenant_id="tenant_alpha",
        message_id="msg_proposal_submitted_001",
        aggregate_type="proposal",
        aggregate_id="proposal_personal_credit_001",
        event_type="creditos.proposal.v1.submitted",
        subject="proposal/proposal_personal_credit_001",
        payload=MappingProxyType(
            {
                "proposal_id": "proposal_personal_credit_001",
                "product_type": "personal_credit",
                "status": "submitted",
                "schema_version": "1.0",
                "correlation_id": "corr_epic6_gate_001",
                "trace_id": TRACE_ID,
            }
        ),
        status="pending",
        created_at=NOW,
        deduplication_key="idem_proposal_personal_credit_001",
    )


def _integration_execution_event() -> IntegrationExecutionEvent:
    safe_idempotency_reference = "idem_integration_execution_001"
    return IntegrationExecutionEvent(
        specversion="1.0",
        id="evt_1234567890abcdef1234567890abcdef",
        type="creditos.integration.execution.completed.v1",
        source="/creditos/integration",
        subject="integration/execution/intexec_personal_credit_001",
        time=NOW.isoformat(),
        datacontenttype="application/json",
        dataschema="https://schemas.creditos.local/integration-execution/v1",
        tenant_id="tenant_alpha",
        correlation_id="corr_epic6_gate_001",
        trace_id=TRACE_ID,
        request_id="req_epic6_gate_001",
        idempotency_key=safe_idempotency_reference,
        schema_version="1.0",
        data=MappingProxyType({"status": "completed"}),
    )


def _integration_audit_event() -> IntegrationAuditEvent:
    return IntegrationAuditEvent(
        tenant_id="tenant_alpha",
        operation="integration.execution.completed",
        product_type="personal_credit",
        integration_class="bureau",
        adapter_id="adapter_mock_sandbox",
        result="accepted",
        correlation_id="corr_epic6_gate_001",
        trace_id=TRACE_ID,
        schema_version="1.0",
        occurred_at=NOW,
    )


def _raw_sensitive_payload() -> dict[str, Any]:
    return {
        "cpf": "000.000.000-00",
        "cnpj": "00.000.000/0000-00",
        "email": "pessoa.sintetica@example.test",
        "phone": "(00) 00000-0000",
        "authorization": "Bearer valor-local",
        "request_body": {"document": "00000000000"},
        "prompt": "avaliar pessoa sintética",
        "output": "resposta sintética",
        "renda_mensal": 123456,
    }


def _credit_decision_intent() -> CreditDecisionAuditIntent:
    return CreditDecisionAuditIntent(
        event_type="credit_decision.completed",
        tenant_id="tenant_alpha",
        tenant_isolation_tier="bridge",
        actor_subject_id="decision-service",
        decision_id="decision_personal_credit_001",
        proposal_id="proposal_personal_credit_001",
        policy_id="pol_personal_credit_default",
        policy_version_id="polver_personal_credit_default_v1",
        reason_code_catalog_id="rcc_personal_credit_default",
        reason_code_catalog_version_id="rccver_personal_credit_default_v1",
        correlation_id="corr_epic6_gate_001",
        request_id="req_epic6_gate_001",
        traceparent=TRACEPARENT,
        safe_details={
            "operation": "credit_decision.execute",
            "status": "completed",
            "fingerprint": "decision_fp_001",
        },
    )


def _credit_policy_intent() -> CreditPolicyAuditIntent:
    return CreditPolicyAuditIntent(
        event_type="credit_policy.published",
        tenant_id="tenant_alpha",
        tenant_isolation_tier="bridge",
        actor_subject_id="risk-manager",
        policy_id="pol_personal_credit_default",
        policy_version_id="polver_personal_credit_default_v1",
        correlation_id="corr_epic6_gate_002",
        request_id="req_epic6_gate_002",
        traceparent=TRACEPARENT,
        safe_details={
            "operation": "credit_policy.publish",
            "status": "published",
            "approval_reference": "approval_board_001",
            "previous_revision": "2",
            "resulting_revision": "3",
        },
    )


def _automated_review_config_intent() -> AutomatedReviewAuditIntent:
    return AutomatedReviewAuditIntent(
        event_type="automated_review.config.published",
        tenant_id="tenant_alpha",
        tenant_isolation_tier="bridge",
        actor_subject_id="risk-manager",
        review_agent_config_id="rac_personal_credit_default",
        review_agent_config_version_id="racver_personal_credit_default_v1",
        correlation_id="corr_epic6_gate_003",
        request_id="req_epic6_gate_003",
        traceparent=TRACEPARENT,
        occurred_at=NOW.isoformat(),
        change_summary="Publicação aprovada",
        previous_revision=2,
        resulting_revision=3,
        safe_details={
            "operation": "automated_review.config.publish",
            "status": "published",
            "consultative_only": "true",
            "fallback_action": "return_inconclusive",
            "model_ref": "model_credit_review",
            "model_version": "model_version_001",
            "prompt_fingerprint": "a" * 64,
            "prompt_version": "prompt_credit_review_v1",
            "provider_ref": "provider_llm_default",
        },
    )
