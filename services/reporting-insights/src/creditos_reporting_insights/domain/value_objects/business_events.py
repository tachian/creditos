from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from enum import StrEnum

from creditos_security import mask_text

from creditos_reporting_insights.domain.errors import BusinessEventValidationError
from creditos_reporting_insights.domain.value_objects.contract_versions import (
    INTEGRATION_SCHEMA_VERSION,
    INTERNAL_DTO_SCHEMA_VERSION,
    PROPOSAL_EVENT_SCHEMA_VERSION,
)

DeduplicationKey = tuple[str, ...]

_MAX_FUTURE_SKEW = timedelta(minutes=5)
_MAX_COST_UNITS = 1_000_000_000
_MAX_LATENCY_MS = 120_000
_MAX_ERROR_COUNT = 100
_MAX_REASON_CODES = 20
_TECHNICAL_REF_PATTERN = re.compile(r"^[a-z0-9][a-z0-9_.-]{1,119}$")
_CLOUDEVENT_SOURCE_PATTERN = re.compile(r"^creditos://[a-z0-9][a-z0-9_.-]{1,80}$")
_ADAPTER_ID_PATTERN = re.compile(r"^[a-z0-9][a-z0-9_.-]{2,80}$")
_PROVIDER_ID_PATTERN = re.compile(r"^iprv_[a-z0-9_.:-]{3,160}$")
_REASON_CODE_PATTERN = re.compile(r"^[a-z][a-z0-9_]{2,63}$")
_ALLOWED_REASON_CODE_PREFIXES = (
    "policy_",
    "risk_",
    "synthetic_",
    "integration_",
    "review_",
    "callback_",
    "data_",
)
_ALLOWED_CLOUDEVENT_SOURCES = frozenset(
    {
        "creditos://proposal-intake",
        "creditos://integration",
        "creditos://decision",
        "creditos://automated-review",
        "creditos://callback-dispatcher",
    }
)
_ALLOWED_INTEGRATION_CLASSES = frozenset(
    {
        "kyc_kyb",
        "credit_bureau",
        "anti_fraud",
        "receivables",
    }
)
_FORBIDDEN_DIMENSION_KEYS = frozenset(
    {
        "cpf",
        "cnpj",
        "document",
        "document_number",
        "email",
        "name",
        "address",
        "street",
        "proposal_id",
        "decision_id",
        "correlation_id",
        "request_id",
        "trace_id",
        "external_proposal_id",
        "token",
        "secret",
        "payload",
        "provider_payload",
        "prompt",
        "output",
    }
)


class BusinessEventType(StrEnum):
    PROPOSAL = "proposal"
    DECISION_QUERY = "decision_query"
    DECISION = "decision"
    INTEGRATION = "integration"
    AI_REVIEW = "ai_review"
    CALLBACK = "callback"


class ProductType(StrEnum):
    UNKNOWN = "unknown"
    PERSONAL_CREDIT = "personal_credit"
    BNPL = "bnpl"
    BUSINESS_CREDIT = "business_credit"
    RECEIVABLES = "receivables"


class Channel(StrEnum):
    API = "api"
    BATCH = "batch"
    PORTAL = "portal"
    PARTNER = "partner"
    CHECKOUT = "checkout"
    BACKOFFICE = "backoffice"


class TenantIsolationTier(StrEnum):
    BRIDGE = "bridge"
    SILO = "silo"


class ProposalFunnelStatus(StrEnum):
    RECEIVED = "received"
    VALIDATED = "validated"
    ENRICHED = "enriched"
    DECIDED = "decided"
    APPROVED = "approved"
    DECLINED = "declined"
    APPROVED_WITH_CHANGES = "approved_with_changes"
    INCONCLUSIVE = "inconclusive"
    ADDITIONAL_DATA_REQUESTED = "additional_data_requested"


class DecisionOutcome(StrEnum):
    APPROVED = "approved"
    DECLINED = "declined"
    APPROVED_WITH_CHANGES = "approved_with_changes"
    INCONCLUSIVE = "inconclusive"


class DecisionQueryStatus(StrEnum):
    SUCCEEDED = "succeeded"
    NOT_AVAILABLE = "not_available"
    INVALID_REQUEST = "invalid_request"
    FAILED = "failed"


class IntegrationStatus(StrEnum):
    REQUESTED = "requested"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    TIMEOUT = "timeout"
    SKIPPED = "skipped"


class ReviewStatus(StrEnum):
    REQUESTED = "requested"
    COMPLETED = "completed"
    FALLBACK = "fallback"
    BLOCKED = "blocked"


class CallbackStatus(StrEnum):
    DELIVERED = "delivered"
    FAILED = "failed"
    RETRYING = "retrying"
    DLQ = "dlq"
    REPROCESS_REQUESTED = "reprocess_requested"
    SKIPPED = "skipped"


@dataclass(frozen=True, slots=True)
class BusinessEvent:
    event_id: str
    source: str
    event_type: BusinessEventType
    tenant_id: str
    product_type: ProductType
    occurred_at: datetime
    processed_at: datetime
    schema_version: str
    idempotency_key: str | None = None
    tenant_isolation_tier: TenantIsolationTier = TenantIsolationTier.BRIDGE
    channel: Channel | None = None
    funnel_status: ProposalFunnelStatus | None = None
    decision_query_status: DecisionQueryStatus | None = None
    decision_outcome: DecisionOutcome | None = None
    integration_class: str | None = None
    adapter_id: str | None = None
    provider_id: str | None = None
    integration_status: IntegrationStatus | None = None
    review_status: ReviewStatus | None = None
    callback_status: CallbackStatus | None = None
    reason_codes: tuple[str, ...] = field(default_factory=tuple)
    estimated_cost_units: int = 0
    actual_cost_units: int = 0
    latency_ms: int | None = None
    error_count: int = 0

    def __post_init__(self) -> None:
        _validate_enum(self.event_type, BusinessEventType, field_path="event_type")
        _validate_enum(self.product_type, ProductType, field_path="product_type")
        _validate_enum(
            self.tenant_isolation_tier,
            TenantIsolationTier,
            field_path="tenant_isolation_tier",
        )
        if self.channel is not None:
            _validate_enum(self.channel, Channel, field_path="channel")
        _validate_schema_version(self.event_type, self.schema_version)
        _validate_technical_ref(self.event_id, field_path="event_id")
        _validate_event_source(self.source)
        _validate_technical_ref(self.tenant_id, field_path="tenant_id")
        _validate_timestamp(self.occurred_at, field_path="occurred_at")
        _validate_timestamp(self.processed_at, field_path="processed_at")
        _validate_timestamp_order(self.occurred_at, self.processed_at)
        if self.idempotency_key is not None:
            _validate_technical_ref(self.idempotency_key, field_path="idempotency_key")
        if self.integration_class is not None:
            _validate_integration_class(self.integration_class)
        if self.adapter_id is not None:
            _validate_integration_dimension(
                self.adapter_id,
                field_path="adapter_id",
                pattern=_ADAPTER_ID_PATTERN,
            )
        if self.provider_id is not None:
            _validate_integration_dimension(
                self.provider_id,
                field_path="provider_id",
                pattern=_PROVIDER_ID_PATTERN,
            )
        _validate_reason_codes(self.reason_codes)
        _validate_integer_units(
            self.estimated_cost_units,
            field_path="estimated_cost_units",
            maximum=_MAX_COST_UNITS,
        )
        _validate_integer_units(
            self.actual_cost_units,
            field_path="actual_cost_units",
            maximum=_MAX_COST_UNITS,
        )
        if self.latency_ms is not None:
            _validate_integer_units(
                self.latency_ms,
                field_path="latency_ms",
                maximum=_MAX_LATENCY_MS,
            )
        _validate_integer_units(
            self.error_count,
            field_path="error_count",
            maximum=_MAX_ERROR_COUNT,
        )
        self._validate_required_status()

    @property
    def canonical_event_key(self) -> DeduplicationKey:
        return ("source_event", self.source, self.event_id)

    @property
    def deduplication_keys(self) -> tuple[DeduplicationKey, ...]:
        keys = [self.canonical_event_key]
        if self.idempotency_key is not None:
            keys.append(
                (
                    "idempotency_key",
                    self.tenant_id,
                    self.event_type.value,
                    self.schema_version,
                    self.idempotency_key,
                )
            )
        return tuple(keys)

    @property
    def period(self) -> str:
        return self.occurred_at.astimezone(UTC).date().isoformat()

    @classmethod
    def proposal(
        cls,
        *,
        event_id: str,
        source: str,
        tenant_id: str,
        product_type: ProductType,
        occurred_at: datetime,
        processed_at: datetime,
        channel: Channel,
        funnel_status: ProposalFunnelStatus,
        schema_version: str = PROPOSAL_EVENT_SCHEMA_VERSION,
        idempotency_key: str | None = None,
    ) -> BusinessEvent:
        return cls(
            event_id=event_id,
            source=source,
            event_type=BusinessEventType.PROPOSAL,
            tenant_id=tenant_id,
            product_type=product_type,
            occurred_at=occurred_at,
            processed_at=processed_at,
            schema_version=schema_version,
            channel=channel,
            funnel_status=funnel_status,
            idempotency_key=idempotency_key,
        )

    @classmethod
    def decision(
        cls,
        *,
        event_id: str,
        source: str,
        tenant_id: str,
        product_type: ProductType,
        occurred_at: datetime,
        processed_at: datetime,
        channel: Channel,
        outcome: DecisionOutcome,
        reason_codes: tuple[str, ...],
        schema_version: str = INTERNAL_DTO_SCHEMA_VERSION,
        idempotency_key: str | None = None,
    ) -> BusinessEvent:
        return cls(
            event_id=event_id,
            source=source,
            event_type=BusinessEventType.DECISION,
            tenant_id=tenant_id,
            product_type=product_type,
            occurred_at=occurred_at,
            processed_at=processed_at,
            schema_version=schema_version,
            channel=channel,
            funnel_status=_outcome_to_funnel_status(outcome),
            decision_outcome=outcome,
            reason_codes=reason_codes,
            idempotency_key=idempotency_key,
        )

    @classmethod
    def decision_query(
        cls,
        *,
        event_id: str,
        source: str,
        tenant_id: str,
        product_type: ProductType,
        occurred_at: datetime,
        processed_at: datetime,
        status: DecisionQueryStatus,
        channel: Channel | None = None,
        schema_version: str = INTERNAL_DTO_SCHEMA_VERSION,
        idempotency_key: str | None = None,
        latency_ms: int | None = None,
        error_count: int = 0,
    ) -> BusinessEvent:
        return cls(
            event_id=event_id,
            source=source,
            event_type=BusinessEventType.DECISION_QUERY,
            tenant_id=tenant_id,
            product_type=product_type,
            occurred_at=occurred_at,
            processed_at=processed_at,
            schema_version=schema_version,
            channel=channel,
            decision_query_status=status,
            idempotency_key=idempotency_key,
            latency_ms=latency_ms,
            error_count=error_count,
        )

    @classmethod
    def integration(
        cls,
        *,
        event_id: str,
        source: str,
        tenant_id: str,
        product_type: ProductType,
        occurred_at: datetime,
        processed_at: datetime,
        integration_class: str,
        adapter_id: str,
        status: IntegrationStatus,
        provider_id: str | None = None,
        channel: Channel | None = None,
        schema_version: str = INTEGRATION_SCHEMA_VERSION,
        idempotency_key: str | None = None,
        estimated_cost_units: int = 0,
        actual_cost_units: int = 0,
        latency_ms: int | None = None,
        error_count: int = 0,
    ) -> BusinessEvent:
        return cls(
            event_id=event_id,
            source=source,
            event_type=BusinessEventType.INTEGRATION,
            tenant_id=tenant_id,
            product_type=product_type,
            occurred_at=occurred_at,
            processed_at=processed_at,
            schema_version=schema_version,
            channel=channel,
            integration_class=integration_class,
            adapter_id=adapter_id,
            provider_id=provider_id,
            integration_status=status,
            idempotency_key=idempotency_key,
            estimated_cost_units=estimated_cost_units,
            actual_cost_units=actual_cost_units,
            latency_ms=latency_ms,
            error_count=error_count,
        )

    @classmethod
    def ai_review(
        cls,
        *,
        event_id: str,
        source: str,
        tenant_id: str,
        product_type: ProductType,
        occurred_at: datetime,
        processed_at: datetime,
        status: ReviewStatus,
        channel: Channel | None = None,
        schema_version: str = INTERNAL_DTO_SCHEMA_VERSION,
        idempotency_key: str | None = None,
        estimated_cost_units: int = 0,
        actual_cost_units: int = 0,
        latency_ms: int | None = None,
        error_count: int = 0,
    ) -> BusinessEvent:
        return cls(
            event_id=event_id,
            source=source,
            event_type=BusinessEventType.AI_REVIEW,
            tenant_id=tenant_id,
            product_type=product_type,
            occurred_at=occurred_at,
            processed_at=processed_at,
            schema_version=schema_version,
            channel=channel,
            review_status=status,
            idempotency_key=idempotency_key,
            estimated_cost_units=estimated_cost_units,
            actual_cost_units=actual_cost_units,
            latency_ms=latency_ms,
            error_count=error_count,
        )

    @classmethod
    def callback(
        cls,
        *,
        event_id: str,
        source: str,
        tenant_id: str,
        product_type: ProductType,
        occurred_at: datetime,
        processed_at: datetime,
        status: CallbackStatus,
        channel: Channel | None = None,
        schema_version: str = INTERNAL_DTO_SCHEMA_VERSION,
        idempotency_key: str | None = None,
        latency_ms: int | None = None,
        error_count: int = 0,
    ) -> BusinessEvent:
        return cls(
            event_id=event_id,
            source=source,
            event_type=BusinessEventType.CALLBACK,
            tenant_id=tenant_id,
            product_type=product_type,
            occurred_at=occurred_at,
            processed_at=processed_at,
            schema_version=schema_version,
            channel=channel,
            callback_status=status,
            idempotency_key=idempotency_key,
            latency_ms=latency_ms,
            error_count=error_count,
        )

    def _validate_required_status(self) -> None:
        if self.funnel_status is not None:
            _validate_enum(self.funnel_status, ProposalFunnelStatus, field_path="funnel_status")
        if self.decision_query_status is not None:
            _validate_enum(
                self.decision_query_status,
                DecisionQueryStatus,
                field_path="decision_query_status",
            )
        if self.decision_outcome is not None:
            _validate_enum(self.decision_outcome, DecisionOutcome, field_path="decision_outcome")
        if self.integration_status is not None:
            _validate_enum(
                self.integration_status,
                IntegrationStatus,
                field_path="integration_status",
            )
        if self.review_status is not None:
            _validate_enum(self.review_status, ReviewStatus, field_path="review_status")
        if self.callback_status is not None:
            _validate_enum(self.callback_status, CallbackStatus, field_path="callback_status")
        required_by_type = {
            BusinessEventType.PROPOSAL: self.funnel_status,
            BusinessEventType.DECISION_QUERY: self.decision_query_status,
            BusinessEventType.DECISION: self.decision_outcome,
            BusinessEventType.INTEGRATION: self.integration_status,
            BusinessEventType.AI_REVIEW: self.review_status,
            BusinessEventType.CALLBACK: self.callback_status,
        }
        if required_by_type[self.event_type] is None:
            raise BusinessEventValidationError(
                code="business_event_missing_status",
                field_path=f"{self.event_type.value}_status",
            )
        if self.event_type is BusinessEventType.INTEGRATION and not (
            self.integration_class and self.adapter_id
        ):
            raise BusinessEventValidationError(
                code="business_event_missing_integration_dimension",
                field_path="integration_class",
            )


def _outcome_to_funnel_status(outcome: DecisionOutcome) -> ProposalFunnelStatus:
    _validate_enum(outcome, DecisionOutcome, field_path="decision_outcome")
    return {
        DecisionOutcome.APPROVED: ProposalFunnelStatus.APPROVED,
        DecisionOutcome.DECLINED: ProposalFunnelStatus.DECLINED,
        DecisionOutcome.APPROVED_WITH_CHANGES: ProposalFunnelStatus.APPROVED_WITH_CHANGES,
        DecisionOutcome.INCONCLUSIVE: ProposalFunnelStatus.INCONCLUSIVE,
    }[outcome]


def _validate_timestamp(value: datetime, *, field_path: str) -> None:
    if not isinstance(value, datetime) or value.tzinfo is None:
        raise BusinessEventValidationError(
            code="business_event_invalid_timestamp",
            field_path=field_path,
        )
    normalized = value.astimezone(UTC)
    if normalized > datetime.now(UTC) + _MAX_FUTURE_SKEW:
        raise BusinessEventValidationError(
            code="business_event_future_timestamp",
            field_path=field_path,
        )


def _validate_timestamp_order(occurred_at: datetime, processed_at: datetime) -> None:
    if processed_at.astimezone(UTC) < occurred_at.astimezone(UTC):
        raise BusinessEventValidationError(
            code="business_event_processed_before_occurred",
            field_path="processed_at",
        )


def _validate_integer_units(value: int, *, field_path: str, maximum: int) -> None:
    if type(value) is not int or value < 0 or value > maximum:
        raise BusinessEventValidationError(
            code="business_event_invalid_integer_units",
            field_path=field_path,
            details={"maximum": maximum},
        )


def _validate_reason_codes(reason_codes: tuple[str, ...]) -> None:
    if not isinstance(reason_codes, tuple) or len(reason_codes) > _MAX_REASON_CODES:
        raise BusinessEventValidationError(
            code="business_event_invalid_reason_codes",
            field_path="reason_codes",
        )
    for reason_code in reason_codes:
        if (
            not isinstance(reason_code, str)
            or not _REASON_CODE_PATTERN.fullmatch(reason_code)
            or not reason_code.startswith(_ALLOWED_REASON_CODE_PREFIXES)
            or _has_forbidden_dimension_key("reason_code", reason_code)
            or mask_text(reason_code) != reason_code
        ):
            raise BusinessEventValidationError(
                code="business_event_invalid_reason_code",
                field_path="reason_codes",
            )


def _validate_enum(value: object, enum_type: type[StrEnum], *, field_path: str) -> None:
    if not isinstance(value, enum_type):
        raise BusinessEventValidationError(
            code=f"business_event_invalid_{field_path}",
            field_path=field_path,
        )


def _validate_schema_version(event_type: BusinessEventType, schema_version: str) -> None:
    expected = {
        BusinessEventType.PROPOSAL: PROPOSAL_EVENT_SCHEMA_VERSION,
        BusinessEventType.INTEGRATION: INTEGRATION_SCHEMA_VERSION,
        BusinessEventType.DECISION_QUERY: INTERNAL_DTO_SCHEMA_VERSION,
        BusinessEventType.DECISION: INTERNAL_DTO_SCHEMA_VERSION,
        BusinessEventType.AI_REVIEW: INTERNAL_DTO_SCHEMA_VERSION,
        BusinessEventType.CALLBACK: INTERNAL_DTO_SCHEMA_VERSION,
    }[event_type]
    if schema_version != expected:
        raise BusinessEventValidationError(
            code="business_event_unsupported_schema_version",
            field_path="schema_version",
            details={"expected": expected},
        )


def _validate_integration_class(value: str) -> None:
    if value not in _ALLOWED_INTEGRATION_CLASSES or mask_text(value) != value:
        raise BusinessEventValidationError(
            code="business_event_invalid_integration_class",
            field_path="integration_class",
        )


def _validate_integration_dimension(
    value: str,
    *,
    field_path: str,
    pattern: re.Pattern[str],
) -> None:
    if (
        not isinstance(value, str)
        or not pattern.fullmatch(value)
        or _has_forbidden_dimension_key(field_path, value)
        or mask_text(value) != value
    ):
        raise BusinessEventValidationError(
            code=f"business_event_invalid_{field_path}",
            field_path=field_path,
        )


def _validate_event_source(value: str) -> None:
    if (
        isinstance(value, str)
        and value in _ALLOWED_CLOUDEVENT_SOURCES
        and _CLOUDEVENT_SOURCE_PATTERN.fullmatch(value)
        and not _has_forbidden_dimension_key("source", value)
        and mask_text(value) == value
    ):
        return
    _validate_technical_ref(value, field_path="source")


def _validate_technical_ref(value: str, *, field_path: str) -> None:
    if (
        not isinstance(value, str)
        or not _TECHNICAL_REF_PATTERN.fullmatch(value)
        or _has_forbidden_dimension_key(field_path, value)
        or mask_text(value) != value
    ):
        raise BusinessEventValidationError(
            code=f"business_event_invalid_{field_path}",
            field_path=field_path,
        )


def _has_forbidden_dimension_key(field_path: str, value: str) -> bool:
    normalized_field = field_path.lower()
    normalized_value = value.lower()
    return any(
        forbidden in normalized_field or forbidden in normalized_value
        for forbidden in _FORBIDDEN_DIMENSION_KEYS
    )
