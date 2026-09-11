from __future__ import annotations

import hashlib
import re
from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import datetime
from types import MappingProxyType

from creditos_automated_review.domain.entities.automated_review_execution import (
    AutomatedReviewExecutionResult,
)
from creditos_automated_review.domain.entities.review_agent_configuration import (
    ReviewAgentConfiguration,
)
from creditos_automated_review.domain.errors import AutomatedReviewValidationError
from creditos_automated_review.domain.value_objects.review_agent_config import (
    validate_agent_version,
    validate_correlation_id,
    validate_review_agent_config_id,
    validate_review_agent_config_version_id,
    validate_tenant_id,
)
from creditos_automated_review.domain.value_objects.review_execution import (
    validate_non_sensitive_execution_reference,
    validate_prompt_fingerprint,
    validate_review_technical_token,
    validate_safe_review_reference,
)
from creditos_automated_review.domain.value_objects.review_output import (
    ReviewOutputItem,
    ReviewOutputValidationResult,
)

_CONSULTATIVE_ITEM_TYPES = frozenset(
    {"missing_data", "inconsistency", "explainability_factor", "limitation"}
)
_TRACE_ID_PATTERN = re.compile(r"[0-9a-f]{32}")


@dataclass(frozen=True, slots=True)
class ConsultativeEvidenceItem:
    item_ref: str
    item_type: str
    severity: str
    reason_ref: str
    confidence: int | None = None
    evidence_refs: tuple[str, ...] = ()
    safe_summary: None = None

    def __post_init__(self) -> None:
        validated = ReviewOutputItem.create(
            item_ref=self.item_ref,
            item_type=self.item_type,
            severity=self.severity,
            reason_ref=self.reason_ref,
            confidence=self.confidence,
            evidence_refs=tuple(self.evidence_refs),
        )
        object.__setattr__(self, "item_ref", validated.item_ref)
        object.__setattr__(self, "item_type", validated.item_type)
        object.__setattr__(self, "severity", validated.severity)
        object.__setattr__(self, "reason_ref", validated.reason_ref)
        object.__setattr__(self, "confidence", validated.confidence)
        object.__setattr__(self, "evidence_refs", validated.evidence_refs)
        object.__setattr__(self, "safe_summary", None)

    @classmethod
    def from_review_output_item(
        cls,
        item: ReviewOutputItem,
    ) -> ConsultativeEvidenceItem:
        return cls(
            item_ref=item.item_ref,
            item_type=item.item_type,
            severity=item.severity,
            reason_ref=item.reason_ref,
            confidence=item.confidence,
            evidence_refs=item.evidence_refs,
        )


@dataclass(frozen=True, slots=True)
class ConsultativeEvidence:
    consultative_evidence_id: str
    tenant_id: str
    proposal_id: str
    execution_id: str
    review_agent_config_id: str
    review_agent_config_version_id: str
    agent_version: str
    product_type: str
    channel: str
    review_purpose: str
    minimization_policy_ref: str
    prompt_fingerprint: str
    correlation_id: str
    trace_id: str | None
    occurred_at: datetime
    classification: str = "consultative"
    provider_ref: str | None = None
    model_ref: str | None = None
    model_version: str | None = None
    items: tuple[ConsultativeEvidenceItem, ...] = ()
    counts_by_type: Mapping[str, int] = field(default_factory=lambda: MappingProxyType({}))

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "consultative_evidence_id",
            _validate_evidence_reference(
                self.consultative_evidence_id,
                field_path="consultative_evidence_id",
            ),
        )
        object.__setattr__(self, "tenant_id", validate_tenant_id(self.tenant_id))
        object.__setattr__(
            self,
            "proposal_id",
            _validate_evidence_reference(self.proposal_id, field_path="proposal_id"),
        )
        object.__setattr__(
            self,
            "execution_id",
            _validate_evidence_reference(self.execution_id, field_path="execution_id"),
        )
        object.__setattr__(
            self,
            "review_agent_config_id",
            validate_review_agent_config_id(self.review_agent_config_id),
        )
        object.__setattr__(
            self,
            "review_agent_config_version_id",
            validate_review_agent_config_version_id(self.review_agent_config_version_id),
        )
        for field_name in (
            "agent_version",
            "product_type",
            "channel",
            "review_purpose",
            "minimization_policy_ref",
        ):
            object.__setattr__(
                self,
                field_name,
                validate_agent_version(getattr(self, field_name), field_path=field_name),
            )
        object.__setattr__(
            self,
            "prompt_fingerprint",
            validate_prompt_fingerprint(self.prompt_fingerprint),
        )
        object.__setattr__(self, "correlation_id", validate_correlation_id(self.correlation_id))
        object.__setattr__(self, "trace_id", _validate_trace_id(self.trace_id))
        if self.occurred_at.tzinfo is None or self.occurred_at.utcoffset() is None:
            raise AutomatedReviewValidationError(
                "timestamp de evidência deve possuir timezone",
                code="automated_review_invalid_evidence_timestamp",
                field_path="occurred_at",
            )
        if self.classification != "consultative":
            raise AutomatedReviewValidationError(
                "evidência automatizada deve ser consultiva",
                code="automated_review_non_consultative_evidence",
                field_path="classification",
            )
        for field_name in ("provider_ref", "model_ref", "model_version"):
            value = getattr(self, field_name)
            if value is not None:
                object.__setattr__(
                    self,
                    field_name,
                    validate_safe_review_reference(value, field_path=field_name),
                )
        items = _sanitize_evidence_items(tuple(self.items))
        item_refs = [item.item_ref for item in items]
        if len(set(item_refs)) != len(item_refs):
            raise AutomatedReviewValidationError(
                "item duplicado em evidência consultiva",
                code="automated_review_duplicate_evidence_item_ref",
                field_path="items",
            )
        object.__setattr__(self, "items", items)
        object.__setattr__(
            self,
            "counts_by_type",
            MappingProxyType(_validate_counts_by_type(self.counts_by_type, items)),
        )

    @classmethod
    def from_execution(
        cls,
        *,
        execution: AutomatedReviewExecutionResult,
        output_validation: ReviewOutputValidationResult,
        config: ReviewAgentConfiguration,
        correlation_id: str,
        trace_id: str | None,
    ) -> ConsultativeEvidence:
        if execution.status != "completed":
            raise AutomatedReviewValidationError(
                "evidência consultiva exige execução concluída",
                code="automated_review_evidence_requires_completed_execution",
                field_path="execution.status",
            )
        if output_validation.status != "accepted":
            raise AutomatedReviewValidationError(
                "evidência consultiva exige saída aceita",
                code="automated_review_evidence_requires_accepted_output",
                field_path="output_validation.status",
            )
        items = cls.items_from_validation(output_validation)
        if not items:
            raise AutomatedReviewValidationError(
                "evidência consultiva exige itens governados",
                code="automated_review_empty_consultative_evidence",
                field_path="items",
            )
        _validate_execution_config_consistency(execution=execution, config=config)
        _validate_execution_output_consistency(
            execution=execution,
            output_validation=output_validation,
        )
        model_ref = config.model_ref
        return cls(
            consultative_evidence_id=consultative_evidence_id_for(execution.execution_id),
            tenant_id=execution.tenant_id,
            proposal_id=execution.proposal_id,
            execution_id=execution.execution_id,
            review_agent_config_id=execution.review_agent_config_id,
            review_agent_config_version_id=execution.review_agent_config_version_id,
            agent_version=config.agent_version,
            product_type=execution.product_type,
            channel=execution.channel,
            review_purpose=execution.review_purpose,
            minimization_policy_ref=execution.minimization_policy_ref,
            prompt_fingerprint=execution.prompt_fingerprint,
            correlation_id=correlation_id,
            trace_id=trace_id,
            occurred_at=execution.occurred_at,
            provider_ref=None if model_ref is None else model_ref.provider_ref,
            model_ref=None if model_ref is None else model_ref.model_ref,
            model_version=None if model_ref is None else model_ref.model_version,
            items=items,
            counts_by_type=output_validation.accepted_counts_by_type,
        )

    @staticmethod
    def items_from_validation(
        output_validation: ReviewOutputValidationResult,
    ) -> tuple[ConsultativeEvidenceItem, ...]:
        return tuple(
            ConsultativeEvidenceItem.from_review_output_item(item)
            for item in output_validation.items
        )

    @property
    def finding_refs(self) -> tuple[str, ...]:
        return tuple(item.item_ref for item in self.items if item.item_type != "limitation")

    @property
    def limitation_refs(self) -> tuple[str, ...]:
        return tuple(item.item_ref for item in self.items if item.item_type == "limitation")

    @property
    def confidence_present_count(self) -> int:
        return sum(1 for item in self.items if item.confidence is not None)


def consultative_evidence_id_for(execution_id: str) -> str:
    safe_execution_id = _validate_evidence_reference(execution_id, field_path="execution_id")
    candidate = f"cevid_{safe_execution_id}"
    if len(candidate) <= 128:
        return _validate_evidence_reference(candidate, field_path="consultative_evidence_id")
    digest = hashlib.sha256(safe_execution_id.encode("utf-8")).hexdigest()
    segmented_digest = ".".join(digest[index : index + 16] for index in range(0, len(digest), 16))
    return _validate_evidence_reference(
        f"cevid_{segmented_digest}",
        field_path="consultative_evidence_id",
    )


def _sanitize_evidence_items(
    items: tuple[object, ...],
) -> tuple[ConsultativeEvidenceItem, ...]:
    sanitized: list[ConsultativeEvidenceItem] = []
    for index, item in enumerate(items):
        if isinstance(item, ConsultativeEvidenceItem):
            sanitized.append(item)
            continue
        if isinstance(item, ReviewOutputItem):
            sanitized.append(ConsultativeEvidenceItem.from_review_output_item(item))
            continue
        raise AutomatedReviewValidationError(
            "item de evidência consultiva inválido",
            code="automated_review_invalid_consultative_evidence_item",
            field_path=f"items[{index}]",
        )
    return tuple(sanitized)


def _validate_execution_config_consistency(
    *,
    execution: AutomatedReviewExecutionResult,
    config: ReviewAgentConfiguration,
) -> None:
    if (
        config.tenant_id != execution.tenant_id
        or config.review_agent_config_id != execution.review_agent_config_id
        or config.review_agent_config_version_id != execution.review_agent_config_version_id
        or config.product_type != execution.product_type
    ):
        raise AutomatedReviewValidationError(
            "configuração incompatível com execução consultiva",
            code="automated_review_evidence_config_mismatch",
            field_path="review_agent_config_id",
        )


def _validate_execution_output_consistency(
    *,
    execution: AutomatedReviewExecutionResult,
    output_validation: ReviewOutputValidationResult,
) -> None:
    if (
        output_validation.status != execution.output_validation_status
        or output_validation.finding_refs != execution.finding_refs
        or output_validation.limitation_refs != execution.limitation_refs
        or dict(output_validation.accepted_counts_by_type)
        != dict(execution.accepted_output_counts_by_type)
    ):
        raise AutomatedReviewValidationError(
            "saída validada incompatível com execução consultiva",
            code="automated_review_evidence_output_mismatch",
            field_path="output_validation",
        )


def _validate_evidence_reference(value: str, *, field_path: str) -> str:
    return validate_non_sensitive_execution_reference(
        validate_agent_version(value, field_path=field_path),
        field_path=field_path,
    )


def _validate_trace_id(value: str | None) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str) or _TRACE_ID_PATTERN.fullmatch(value.strip()) is None:
        raise AutomatedReviewValidationError(
            "trace_id inválido",
            code="automated_review_invalid_trace_id",
            field_path="trace_id",
        )
    return value.strip()


def _validate_counts_by_type(
    counts_by_type: Mapping[str, int],
    items: tuple[ConsultativeEvidenceItem, ...],
) -> dict[str, int]:
    actual: dict[str, int] = {}
    for item in items:
        actual[item.item_type] = actual.get(item.item_type, 0) + 1
    if not counts_by_type:
        return actual
    counts: dict[str, int] = {}
    for item_type, count in counts_by_type.items():
        safe_item_type = validate_review_technical_token(
            item_type,
            field_path=f"counts_by_type.{item_type}",
        )
        if safe_item_type not in _CONSULTATIVE_ITEM_TYPES or type(count) is not int or count < 0:
            raise AutomatedReviewValidationError(
                "contagem de evidência consultiva inválida",
                code="automated_review_invalid_evidence_count",
                field_path=f"counts_by_type.{safe_item_type}",
            )
        counts[safe_item_type] = count
    if counts != actual:
        raise AutomatedReviewValidationError(
            "contagem de evidência consultiva incompatível com itens",
            code="automated_review_evidence_count_mismatch",
            field_path="counts_by_type",
        )
    return counts
