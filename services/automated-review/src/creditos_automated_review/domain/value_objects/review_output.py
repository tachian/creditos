from __future__ import annotations

import re
from collections.abc import Mapping
from dataclasses import dataclass
from types import MappingProxyType

from creditos_security import mask_text

from creditos_automated_review.domain.errors import AutomatedReviewValidationError
from creditos_automated_review.domain.value_objects.review_execution import (
    validate_review_technical_token,
    validate_safe_review_reference,
)

_ALLOWED_OUTPUT_FIELDS = frozenset(
    {
        "item_ref",
        "item_type",
        "severity",
        "reason_ref",
        "confidence",
        "evidence_refs",
        "safe_summary",
    }
)
_CONSULTATIVE_ITEM_TYPES = frozenset(
    {"missing_data", "inconsistency", "explainability_factor", "limitation"}
)
_CONSULTATIVE_SEVERITIES = frozenset({"info", "low", "medium", "high"})
_FINDING_ITEM_TYPES = _CONSULTATIVE_ITEM_TYPES - {"limitation"}
_INJECTION_PATTERNS = (
    re.compile(r"\bignore\s+(?:all\s+)?(?:previous|prior)\s+instructions\b", re.I),
    re.compile(r"\bjailbreak\b", re.I),
    re.compile(r"\bsystem\s+prompt\b", re.I),
    re.compile(r"\bdeveloper\s+message\b", re.I),
    re.compile(r"\bprompt\s+injection\b", re.I),
)
_AUTONOMOUS_ACTION_PATTERNS = (
    re.compile(r"\bapproved?\b", re.I),
    re.compile(r"\brejected?\b", re.I),
    re.compile(r"\bapprove\b", re.I),
    re.compile(r"\breject\b", re.I),
    re.compile(r"\balter(?:ar|e)?\s+terms?\b", re.I),
    re.compile(r"\bchange\s+terms?\b", re.I),
    re.compile(r"\bcallback\b", re.I),
    re.compile(r"\bcall(?:ing)?\s+(?:a\s+)?tool\b", re.I),
    re.compile(r"\binvoke\s+(?:a\s+)?tool\b", re.I),
    re.compile(r"\buse\s+(?:a\s+)?tool\b", re.I),
    re.compile(r"\bchamar\s+ferramenta\b", re.I),
    re.compile(r"\busar\s+ferramenta\b", re.I),
    re.compile(r"\btool(?:_|\s*)call\b", re.I),
    re.compile(r"\btool(?:_|\s*)use\b", re.I),
    re.compile(r"\bfunction(?:_|\s*)call\b", re.I),
    re.compile(r"\bcall(?:ing)?\s+external\s+provider\b", re.I),
    re.compile(r"\bsend(?:ing)?\s+(?:a\s+)?webhook\b", re.I),
    re.compile(r"\benviar\s+webhook\b", re.I),
    re.compile(r"\bexternal(?:_|\s*)action\b", re.I),
    re.compile(r"\bintegration\b", re.I),
    re.compile(r"\bintegra(?:ç|c)[aã]o\b", re.I),
)
_SAFE_SUMMARY_MAX_LENGTH = 160


@dataclass(frozen=True, slots=True)
class ReviewOutputItem:
    item_ref: str
    item_type: str
    severity: str
    reason_ref: str
    confidence: int | None = None
    evidence_refs: tuple[str, ...] = ()
    safe_summary: str | None = None

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "item_ref",
            validate_safe_review_reference(
                self.item_ref,
                field_path="output_items[0].item_ref",
            ),
        )
        item_type = validate_review_technical_token(
            self.item_type,
            field_path="output_items[0].item_type",
        )
        if item_type not in _CONSULTATIVE_ITEM_TYPES:
            raise AutomatedReviewValidationError(
                "classificação consultiva de saída inválida",
                code="automated_review_invalid_output_item_type",
                field_path="output_items[0].item_type",
            )
        object.__setattr__(self, "item_type", item_type)
        severity = validate_review_technical_token(
            self.severity,
            field_path="output_items[0].severity",
        )
        if severity not in _CONSULTATIVE_SEVERITIES:
            raise AutomatedReviewValidationError(
                "severidade consultiva de saída inválida",
                code="automated_review_invalid_output_severity",
                field_path="output_items[0].severity",
            )
        object.__setattr__(self, "severity", severity)
        object.__setattr__(
            self,
            "reason_ref",
            validate_safe_review_reference(
                self.reason_ref,
                field_path="output_items[0].reason_ref",
            ),
        )
        if self.confidence is not None:
            object.__setattr__(self, "confidence", _validate_confidence(self.confidence))
        object.__setattr__(
            self,
            "evidence_refs",
            tuple(
                validate_safe_review_reference(
                    evidence_ref,
                    field_path=f"output_items[0].evidence_refs[{index}]",
                )
                for index, evidence_ref in enumerate(self.evidence_refs)
            ),
        )
        if self.safe_summary is not None:
            object.__setattr__(self, "safe_summary", _validate_safe_summary(self.safe_summary))

    @classmethod
    def create(
        cls,
        *,
        item_ref: str,
        item_type: str,
        severity: str,
        reason_ref: str,
        confidence: int | None = None,
        evidence_refs: tuple[str, ...] = (),
        safe_summary: str | None = None,
    ) -> ReviewOutputItem:
        return cls(
            item_ref=item_ref,
            item_type=item_type,
            severity=severity,
            reason_ref=reason_ref,
            confidence=confidence,
            evidence_refs=evidence_refs,
            safe_summary=safe_summary,
        )

    @classmethod
    def from_mapping(
        cls,
        value: Mapping[str, object],
        *,
        index: int = 0,
    ) -> ReviewOutputItem:
        unknown_fields = tuple(field for field in value if field not in _ALLOWED_OUTPUT_FIELDS)
        if unknown_fields:
            field_name = unknown_fields[0]
            raise AutomatedReviewValidationError(
                "campo de saída consultiva não permitido",
                code="automated_review_unknown_output_field",
                field_path=f"output_items[{index}].{field_name}",
            )
        missing_fields = tuple(
            field
            for field in ("item_ref", "item_type", "severity", "reason_ref")
            if field not in value
        )
        if missing_fields:
            field_name = missing_fields[0]
            raise AutomatedReviewValidationError(
                "campo obrigatório de saída consultiva ausente",
                code="automated_review_missing_output_field",
                field_path=f"output_items[{index}].{field_name}",
            )
        item_ref = _require_str(value["item_ref"], field_path=f"output_items[{index}].item_ref")
        item_type = _require_str(
            value["item_type"],
            field_path=f"output_items[{index}].item_type",
        )
        severity = _require_str(value["severity"], field_path=f"output_items[{index}].severity")
        reason_ref = _require_str(
            value["reason_ref"],
            field_path=f"output_items[{index}].reason_ref",
        )
        confidence = _optional_int(
            value.get("confidence"),
            field_path=f"output_items[{index}].confidence",
        )
        evidence_refs = _optional_str_tuple(
            value.get("evidence_refs"),
            field_path=f"output_items[{index}].evidence_refs",
        )
        safe_summary = _optional_str(
            value.get("safe_summary"),
            field_path=f"output_items[{index}].safe_summary",
        )
        try:
            return cls(
                item_ref=item_ref,
                item_type=item_type,
                severity=severity,
                reason_ref=reason_ref,
                confidence=confidence,
                evidence_refs=evidence_refs,
                safe_summary=safe_summary,
            )
        except AutomatedReviewValidationError as error:
            original_field_path = error.field_path or "output_items[0]"
            field_path = original_field_path.replace(
                "output_items[0]",
                f"output_items[{index}]",
                1,
            )
            raise AutomatedReviewValidationError(
                error.message,
                code=error.code,
                field_path=field_path,
            ) from error


@dataclass(frozen=True, slots=True)
class ReviewOutputValidationResult:
    status: str
    items: tuple[ReviewOutputItem, ...] = ()
    limitation_refs: tuple[str, ...] = ()
    blocked_counts_by_reason: MappingProxyType[str, int] = MappingProxyType({})

    def __post_init__(self) -> None:
        status = validate_review_technical_token(self.status, field_path="output_validation.status")
        if status not in {"accepted", "blocked"}:
            raise AutomatedReviewValidationError(
                "status de validação de saída inválido",
                code="automated_review_invalid_output_validation_status",
                field_path="output_validation.status",
            )
        object.__setattr__(self, "status", status)
        items = tuple(self.items)
        item_refs = [item.item_ref for item in items]
        if len(set(item_refs)) != len(item_refs):
            raise AutomatedReviewValidationError(
                "referência duplicada em saída consultiva",
                code="automated_review_duplicate_output_item_ref",
                field_path="output_items",
            )
        object.__setattr__(self, "items", items)
        limitation_refs = tuple(self.limitation_refs) or tuple(
            item.item_ref for item in items if item.item_type == "limitation"
        )
        object.__setattr__(
            self,
            "limitation_refs",
            tuple(
                validate_safe_review_reference(
                    limitation_ref,
                    field_path=f"output_validation.limitation_refs[{index}]",
                )
                for index, limitation_ref in enumerate(limitation_refs)
            ),
        )
        object.__setattr__(
            self,
            "blocked_counts_by_reason",
            MappingProxyType(_validate_counts_by_reason(self.blocked_counts_by_reason)),
        )

    @classmethod
    def accepted(
        cls,
        *,
        items: tuple[ReviewOutputItem, ...],
    ) -> ReviewOutputValidationResult:
        return cls(status="accepted", items=items)

    @classmethod
    def blocked(
        cls,
        *,
        reason_refs: tuple[str, ...],
        blocked_counts_by_reason: Mapping[str, int],
    ) -> ReviewOutputValidationResult:
        return cls(
            status="blocked",
            limitation_refs=reason_refs,
            blocked_counts_by_reason=MappingProxyType(dict(blocked_counts_by_reason)),
        )

    @property
    def finding_refs(self) -> tuple[str, ...]:
        return tuple(item.item_ref for item in self.items if item.item_type in _FINDING_ITEM_TYPES)

    @property
    def accepted_counts_by_type(self) -> dict[str, int]:
        counts: dict[str, int] = {}
        for item in self.items:
            counts[item.item_type] = counts.get(item.item_type, 0) + 1
        return counts


def _validate_confidence(value: int) -> int:
    if type(value) is not int or value < 0 or value > 100:
        raise AutomatedReviewValidationError(
            "confiança de saída consultiva fora da faixa permitida",
            code="automated_review_invalid_output_confidence",
            field_path="output_items[0].confidence",
        )
    return value


def _validate_safe_summary(value: str) -> str:
    if not isinstance(value, str):
        raise AutomatedReviewValidationError(
            "resumo seguro de saída consultiva inválido",
            code="automated_review_invalid_output_summary",
            field_path="output_items[0].safe_summary",
        )
    normalized = " ".join(value.strip().split())
    if not normalized or len(normalized) > _SAFE_SUMMARY_MAX_LENGTH:
        raise AutomatedReviewValidationError(
            "resumo seguro de saída consultiva inválido",
            code="automated_review_invalid_output_summary",
            field_path="output_items[0].safe_summary",
        )
    if mask_text(normalized) != normalized:
        raise AutomatedReviewValidationError(
            "conteúdo sensível em saída consultiva",
            code="automated_review_sensitive_output_content",
            field_path="output_items[0].safe_summary",
        )
    if any(pattern.search(normalized) for pattern in _INJECTION_PATTERNS):
        raise AutomatedReviewValidationError(
            "prompt injection em saída consultiva",
            code="automated_review_output_prompt_injection",
            field_path="output_items[0].safe_summary",
        )
    if any(pattern.search(normalized) for pattern in _AUTONOMOUS_ACTION_PATTERNS):
        raise AutomatedReviewValidationError(
            "ação autônoma em saída consultiva",
            code="automated_review_autonomous_output_content",
            field_path="output_items[0].safe_summary",
        )
    return normalized


def _require_str(value: object, *, field_path: str) -> str:
    if not isinstance(value, str):
        raise AutomatedReviewValidationError(
            "campo textual de saída consultiva inválido",
            code="automated_review_invalid_output_field",
            field_path=field_path,
        )
    return value


def _optional_str(value: object, *, field_path: str) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str):
        raise AutomatedReviewValidationError(
            "campo textual opcional de saída consultiva inválido",
            code="automated_review_invalid_output_field",
            field_path=field_path,
        )
    return value


def _optional_int(value: object, *, field_path: str) -> int | None:
    if value is None:
        return None
    if type(value) is not int:
        raise AutomatedReviewValidationError(
            "confiança de saída consultiva inválida",
            code="automated_review_invalid_output_confidence",
            field_path=field_path,
        )
    return value


def _optional_str_tuple(value: object, *, field_path: str) -> tuple[str, ...]:
    if value is None:
        return ()
    if isinstance(value, str) or not isinstance(value, tuple | list):
        raise AutomatedReviewValidationError(
            "referências de evidência de saída consultiva inválidas",
            code="automated_review_invalid_output_field",
            field_path=field_path,
        )
    refs: list[str] = []
    for index, item in enumerate(value):
        if not isinstance(item, str):
            raise AutomatedReviewValidationError(
                "referência de evidência de saída consultiva inválida",
                code="automated_review_invalid_output_field",
                field_path=f"{field_path}[{index}]",
            )
        refs.append(item)
    return tuple(refs)


def _validate_counts_by_reason(value: Mapping[str, int]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for reason_ref, count in value.items():
        safe_reason_ref = validate_safe_review_reference(
            reason_ref,
            field_path=f"output_validation.blocked_counts_by_reason.{reason_ref}",
        )
        if type(count) is not int or count < 0:
            raise AutomatedReviewValidationError(
                "contagem de bloqueio de saída inválida",
                code="automated_review_invalid_output_blocked_count",
                field_path=f"output_validation.blocked_counts_by_reason.{safe_reason_ref}",
            )
        counts[safe_reason_ref] = count
    return counts
