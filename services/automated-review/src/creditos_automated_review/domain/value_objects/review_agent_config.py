from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum

from creditos_security import mask_text

from creditos_automated_review.domain.errors import AutomatedReviewValidationError

_TECHNICAL_ID_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_./:-]{2,127}$")
_FORBIDDEN_TEXT_PARTS = (
    "address",
    "authorization",
    "bearer ",
    "celular",
    "cookie",
    "credential",
    "cpf",
    "cnpj",
    "document",
    "documento",
    "endereco",
    "endereço",
    "email",
    "e-mail",
    "header",
    "logradouro",
    "name",
    "nome",
    "payload",
    "password",
    "phone",
    "raw",
    "rua",
    "secret",
    "senha",
    "street",
    "telefone",
    "token",
)
_FORBIDDEN_TECHNICAL_PARTS = (
    "apikey",
    "api_key",
    "authorization",
    "credential",
    "password",
    "private",
    "payload",
    "provider_payload",
    "raw_payload",
    "secret",
    "token",
)
_CAPITALIZED_NAME_PATTERN = re.compile(
    r"\b[A-ZÁÀÂÃÉÊÍÓÔÕÚÇ][a-záàâãéêíóôõúç]{2,}"
    r"\s+(?:d[aeo]s?\s+)?[A-ZÁÀÂÃÉÊÍÓÔÕÚÇ][a-záàâãéêíóôõúç]{2,}\b"
)
_FINANCIAL_DETAIL_PATTERN = re.compile(
    r"(?:R\$\s?\d|BRL\s?\d|\b\d{1,3}(?:\.\d{3})*,\d{2}\b)",
    re.IGNORECASE,
)
_SECRET_LIKE_PATTERN = re.compile(
    r"^(?:sk-[A-Za-z0-9_-]{8,}|AKIA[A-Z0-9]{12,}|[A-Za-z0-9_-]{32,})$"
)
_PRODUCT_TYPES = frozenset({"personal_credit", "bnpl", "business_credit", "receivables"})
_CHANNELS = frozenset({"api", "batch", "partner_api", "console"})
_REVIEW_PURPOSES = frozenset(
    {
        "missing_data",
        "inconsistency",
        "explainability_factor",
        "fallback_limitation",
        "risk_signal",
    }
)
_INPUT_ALLOWLIST = frozenset(
    {
        "requested_amount_units",
        "requested_installments",
        "requested_term_days",
        "monthly_income_units",
        "declared_revenue_units",
        "company_age_months",
        "relationship_age_days",
    }
)
_FALLBACK_ACTIONS = frozenset({"continue_without_review", "request_more_data", "unable_to_decide"})


class ReviewAgentStatus(StrEnum):
    DRAFT = "draft"
    PUBLISHED = "published"
    ARCHIVED = "archived"


@dataclass(frozen=True, slots=True)
class ReviewAgentScope:
    product_type: str
    channels: tuple[str, ...]
    review_purposes: tuple[str, ...]

    def __post_init__(self) -> None:
        product_type = _validate_product_type(self.product_type)
        channels = _validate_unique_allowed_tokens(
            self.channels,
            allowed=_CHANNELS,
            code="unsupported_review_channel",
            field_path="scope.channels",
        )
        review_purposes = _validate_unique_allowed_tokens(
            self.review_purposes,
            allowed=_REVIEW_PURPOSES,
            code="unsupported_review_purpose",
            field_path="scope.review_purposes",
        )
        object.__setattr__(self, "product_type", product_type)
        object.__setattr__(self, "channels", channels)
        object.__setattr__(self, "review_purposes", review_purposes)

    @classmethod
    def create(
        cls,
        *,
        product_type: str,
        channels: tuple[str, ...],
        review_purposes: tuple[str, ...],
    ) -> ReviewAgentScope:
        return cls(
            product_type=product_type,
            channels=channels,
            review_purposes=review_purposes,
        )


@dataclass(frozen=True, slots=True)
class ReviewAgentPrompt:
    prompt_version: str
    instructions: str
    input_allowlist: tuple[str, ...]
    output_schema_ref: str
    prompt_fingerprint: str = ""

    def __post_init__(self) -> None:
        prompt_version = _validate_technical_id(
            self.prompt_version,
            field_path="prompt.prompt_version",
        )
        instructions = _validate_safe_text(
            self.instructions,
            field_path="prompt.instructions",
            code="sensitive_prompt_content",
            min_length=12,
            max_length=4000,
        )
        input_allowlist = _validate_unique_allowed_tokens(
            self.input_allowlist,
            allowed=_INPUT_ALLOWLIST,
            code="unsupported_prompt_input_field",
            field_path="prompt.input_allowlist",
        )
        output_schema_ref = _validate_technical_id(
            self.output_schema_ref,
            field_path="prompt.output_schema_ref",
        )
        object.__setattr__(self, "prompt_version", prompt_version)
        object.__setattr__(self, "instructions", instructions)
        object.__setattr__(self, "input_allowlist", input_allowlist)
        object.__setattr__(self, "output_schema_ref", output_schema_ref)
        expected_fingerprint = _fingerprint(
            {
                "prompt_version": prompt_version,
                "instructions": instructions,
                "input_allowlist": input_allowlist,
                "output_schema_ref": output_schema_ref,
            }
        )
        fingerprint = self.prompt_fingerprint or expected_fingerprint
        object.__setattr__(
            self,
            "prompt_fingerprint",
            _validate_hex_fingerprint(fingerprint, field_path="prompt.prompt_fingerprint"),
        )
        if fingerprint != expected_fingerprint:
            raise AutomatedReviewValidationError(
                "fingerprint incompatível com o prompt",
                code="prompt_fingerprint_mismatch",
                field_path="prompt.prompt_fingerprint",
            )

    @classmethod
    def create(
        cls,
        *,
        prompt_version: str,
        instructions: str,
        input_allowlist: tuple[str, ...],
        output_schema_ref: str,
    ) -> ReviewAgentPrompt:
        return cls(
            prompt_version=prompt_version,
            instructions=instructions,
            input_allowlist=input_allowlist,
            output_schema_ref=output_schema_ref,
        )


@dataclass(frozen=True, slots=True)
class ReviewModelRef:
    provider_ref: str
    model_ref: str
    model_version: str | None = None

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "provider_ref",
            _validate_non_sensitive_technical_ref(
                self.provider_ref,
                field_path="model_ref.provider_ref",
            ),
        )
        object.__setattr__(
            self,
            "model_ref",
            _validate_non_sensitive_technical_ref(self.model_ref, field_path="model_ref.model_ref"),
        )
        if self.model_version is not None:
            object.__setattr__(
                self,
                "model_version",
                _validate_non_sensitive_technical_ref(
                    self.model_version,
                    field_path="model_ref.model_version",
                ),
            )

    @classmethod
    def create(
        cls,
        *,
        provider_ref: str,
        model_ref: str,
        model_version: str | None = None,
    ) -> ReviewModelRef:
        return cls(
            provider_ref=provider_ref,
            model_ref=model_ref,
            model_version=model_version,
        )


@dataclass(frozen=True, slots=True)
class ReviewAgentGuardrails:
    require_schema_validation: bool
    require_input_minimization: bool
    block_sensitive_data: bool
    block_final_decision: bool
    block_tool_use: bool
    fallback_action: str
    max_prompt_tokens: int
    max_output_tokens: int

    def __post_init__(self) -> None:
        for field_name in (
            "require_schema_validation",
            "require_input_minimization",
            "block_sensitive_data",
            "block_final_decision",
            "block_tool_use",
        ):
            if getattr(self, field_name) is not True:
                raise AutomatedReviewValidationError(
                    "guardrail obrigatório ausente",
                    code="missing_required_guardrail",
                    field_path=f"guardrails.{field_name}",
                )
        fallback_action = _validate_allowed_token(
            self.fallback_action,
            allowed=_FALLBACK_ACTIONS,
            code="unsupported_review_fallback",
            field_path="guardrails.fallback_action",
        )
        object.__setattr__(self, "fallback_action", fallback_action)
        object.__setattr__(
            self,
            "max_prompt_tokens",
            _validate_token_limit(
                self.max_prompt_tokens, field_path="guardrails.max_prompt_tokens"
            ),
        )
        object.__setattr__(
            self,
            "max_output_tokens",
            _validate_token_limit(
                self.max_output_tokens, field_path="guardrails.max_output_tokens"
            ),
        )

    @classmethod
    def create(
        cls,
        *,
        require_schema_validation: bool,
        require_input_minimization: bool,
        block_sensitive_data: bool,
        block_final_decision: bool,
        block_tool_use: bool,
        fallback_action: str,
        max_prompt_tokens: int,
        max_output_tokens: int,
    ) -> ReviewAgentGuardrails:
        return cls(
            require_schema_validation=require_schema_validation,
            require_input_minimization=require_input_minimization,
            block_sensitive_data=block_sensitive_data,
            block_final_decision=block_final_decision,
            block_tool_use=block_tool_use,
            fallback_action=fallback_action,
            max_prompt_tokens=max_prompt_tokens,
            max_output_tokens=max_output_tokens,
        )


@dataclass(frozen=True, slots=True)
class ReviewAgentCapabilities:
    can_suggest_missing_data: bool = False
    can_suggest_inconsistencies: bool = False
    can_suggest_explainability_factors: bool = False
    can_approve: bool = False
    can_reject: bool = False
    can_change_terms: bool = False
    can_call_tools: bool = False
    can_call_external_services: bool = False
    can_execute_callback: bool = False
    can_publish_decision: bool = False

    def __post_init__(self) -> None:
        for field_name in self.__dataclass_fields__:
            if type(getattr(self, field_name)) is not bool:
                raise AutomatedReviewValidationError(
                    "capacidade inválida",
                    code="invalid_review_capability",
                    field_path=f"capabilities.{field_name}",
                )
        if not self.consultative_only:
            raise AutomatedReviewValidationError(
                "IA consultiva não pode executar decisão final ou ação externa",
                code="automated_review_autonomous_capability",
                field_path="capabilities",
            )

    @property
    def consultative_only(self) -> bool:
        return not any(
            (
                self.can_approve,
                self.can_reject,
                self.can_change_terms,
                self.can_call_tools,
                self.can_call_external_services,
                self.can_execute_callback,
                self.can_publish_decision,
            )
        )

    @classmethod
    def create(
        cls,
        *,
        can_suggest_missing_data: bool = False,
        can_suggest_inconsistencies: bool = False,
        can_suggest_explainability_factors: bool = False,
        can_approve: bool = False,
        can_reject: bool = False,
        can_change_terms: bool = False,
        can_call_tools: bool = False,
        can_call_external_services: bool = False,
        can_execute_callback: bool = False,
        can_publish_decision: bool = False,
    ) -> ReviewAgentCapabilities:
        return cls(
            can_suggest_missing_data=can_suggest_missing_data,
            can_suggest_inconsistencies=can_suggest_inconsistencies,
            can_suggest_explainability_factors=can_suggest_explainability_factors,
            can_approve=can_approve,
            can_reject=can_reject,
            can_change_terms=can_change_terms,
            can_call_tools=can_call_tools,
            can_call_external_services=can_call_external_services,
            can_execute_callback=can_execute_callback,
            can_publish_decision=can_publish_decision,
        )


@dataclass(frozen=True, slots=True)
class ReviewAgentChangeLogEntry:
    change_type: str
    actor_subject_id: str
    occurred_at: datetime
    correlation_id: str
    change_summary: str
    previous_revision: int
    resulting_revision: int

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "change_type",
            _validate_technical_id(self.change_type, field_path="changelog.change_type"),
        )
        object.__setattr__(
            self,
            "actor_subject_id",
            _validate_technical_id(
                self.actor_subject_id,
                field_path="changelog.actor_subject_id",
            ),
        )
        if self.occurred_at.tzinfo is None or self.occurred_at.utcoffset() is None:
            raise AutomatedReviewValidationError(
                "timestamp deve possuir timezone",
                code="invalid_review_changelog_timestamp",
                field_path="changelog.occurred_at",
            )
        object.__setattr__(
            self,
            "correlation_id",
            _validate_technical_id(self.correlation_id, field_path="changelog.correlation_id"),
        )
        object.__setattr__(
            self,
            "change_summary",
            _validate_safe_text(
                self.change_summary,
                field_path="changelog.change_summary",
                code="sensitive_change_summary",
                min_length=8,
                max_length=500,
            ),
        )
        if self.previous_revision < 0 or self.resulting_revision < 1:
            raise AutomatedReviewValidationError(
                "revisão de changelog inválida",
                code="invalid_review_changelog_revision",
                field_path="changelog.revision",
            )


def validate_review_agent_config_id(value: str) -> str:
    return _validate_technical_id(value, field_path="review_agent_config_id")


def validate_review_agent_config_version_id(value: str) -> str:
    return _validate_technical_id(value, field_path="review_agent_config_version_id")


def validate_tenant_id(value: str) -> str:
    return _validate_technical_id(value, field_path="tenant_id")


def validate_subject_id(value: str) -> str:
    return _validate_technical_id(value, field_path="subject_id")


def validate_agent_version(value: str, *, field_path: str = "agent_version") -> str:
    return _validate_non_sensitive_technical_ref(value, field_path=field_path)


def validate_correlation_id(value: str) -> str:
    return _validate_technical_id(value, field_path="correlation_id")


def _validate_product_type(value: str) -> str:
    return _validate_allowed_token(
        value,
        allowed=_PRODUCT_TYPES,
        code="unsupported_review_product_type",
        field_path="scope.product_type",
    )


def _validate_unique_allowed_tokens(
    values: tuple[str, ...],
    *,
    allowed: frozenset[str],
    code: str,
    field_path: str,
) -> tuple[str, ...]:
    if not values:
        raise AutomatedReviewValidationError(
            "lista governada obrigatória",
            code=code,
            field_path=field_path,
        )
    normalized = tuple(
        _validate_allowed_token(value, allowed=allowed, code=code, field_path=field_path)
        for value in values
    )
    if len(set(normalized)) != len(normalized):
        raise AutomatedReviewValidationError(
            "valor duplicado",
            code=f"duplicate_{code}",
            field_path=field_path,
        )
    return normalized


def _validate_allowed_token(
    value: str,
    *,
    allowed: frozenset[str],
    code: str,
    field_path: str,
) -> str:
    token = _validate_technical_shape(value, field_path=field_path)
    if token not in allowed:
        raise AutomatedReviewValidationError(
            "valor governado não suportado",
            code=code,
            field_path=field_path,
        )
    return token


def _validate_non_sensitive_technical_ref(value: str, *, field_path: str) -> str:
    technical_ref = _validate_technical_shape(value, field_path=field_path)
    lowered = technical_ref.casefold()
    if any(part in lowered for part in _FORBIDDEN_TECHNICAL_PARTS):
        raise AutomatedReviewValidationError(
            "referência técnica sensível não permitida",
            code="sensitive_model_reference",
            field_path=field_path,
        )
    if _SECRET_LIKE_PATTERN.fullmatch(technical_ref) is not None:
        raise AutomatedReviewValidationError(
            "referência técnica com formato de credencial não permitida",
            code="sensitive_model_reference",
            field_path=field_path,
        )
    return technical_ref


def _validate_safe_text(
    value: str,
    *,
    field_path: str,
    code: str,
    min_length: int,
    max_length: int,
) -> str:
    if not isinstance(value, str):
        raise AutomatedReviewValidationError(
            "texto obrigatório",
            code=code,
            field_path=field_path,
        )
    normalized = " ".join(value.strip().split())
    if len(normalized) < min_length or len(normalized) > max_length:
        raise AutomatedReviewValidationError(
            "texto com tamanho inválido",
            code=code,
            field_path=field_path,
        )
    lowered = normalized.casefold()
    if (
        mask_text(normalized) != normalized
        or any(part in lowered for part in _FORBIDDEN_TEXT_PARTS)
        or _CAPITALIZED_NAME_PATTERN.search(normalized) is not None
        or _FINANCIAL_DETAIL_PATTERN.search(normalized) is not None
    ):
        raise AutomatedReviewValidationError(
            "texto sensível não permitido",
            code=code,
            field_path=field_path,
        )
    return normalized


def _validate_technical_id(value: str, *, field_path: str) -> str:
    normalized = _validate_technical_shape(value, field_path=field_path)
    lowered = normalized.casefold()
    if any(part in lowered for part in _FORBIDDEN_TECHNICAL_PARTS):
        raise AutomatedReviewValidationError(
            "identificador técnico sensível não permitido",
            code="sensitive_technical_id",
            field_path=field_path,
        )
    return normalized


def _validate_technical_shape(value: str, *, field_path: str) -> str:
    if not isinstance(value, str):
        raise AutomatedReviewValidationError(
            "identificador técnico inválido",
            code="invalid_technical_id",
            field_path=field_path,
        )
    normalized = value.strip()
    if _TECHNICAL_ID_PATTERN.fullmatch(normalized) is None:
        raise AutomatedReviewValidationError(
            "identificador técnico inválido",
            code="invalid_technical_id",
            field_path=field_path,
        )
    return normalized


def _validate_hex_fingerprint(value: str, *, field_path: str) -> str:
    if not isinstance(value, str) or re.fullmatch(r"[0-9a-f]{64}", value) is None:
        raise AutomatedReviewValidationError(
            "fingerprint inválido",
            code="invalid_fingerprint",
            field_path=field_path,
        )
    return value


def _validate_token_limit(value: int, *, field_path: str) -> int:
    if type(value) is not int or value < 1 or value > 200_000:
        raise AutomatedReviewValidationError(
            "limite de tokens inválido",
            code="invalid_review_token_limit",
            field_path=field_path,
        )
    return value


def _fingerprint(payload: object) -> str:
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(encoded).hexdigest()
