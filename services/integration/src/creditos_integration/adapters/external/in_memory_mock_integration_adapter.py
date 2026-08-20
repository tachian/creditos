from __future__ import annotations

from collections.abc import Callable, Mapping
from datetime import datetime
from hashlib import sha256

from creditos_observability.context import ObservabilityContext

from creditos_integration.application.ports.mock_integration_adapter import MockIntegrationAdapter
from creditos_integration.domain.entities import IntegrationPlanItem, IntegrationResult
from creditos_integration.domain.value_objects.result import (
    IntegrationResultStatus,
    MockIntegrationScenario,
    SyntheticDataType,
    validate_supported_mock_integration_class,
)


class InMemoryMockIntegrationAdapter:
    def __init__(
        self,
        *,
        integration_class: str,
        adapter_id: str,
        result_id_factory: Callable[[str], str] | None = None,
    ) -> None:
        self.integration_class = validate_supported_mock_integration_class(integration_class)
        self.adapter_id = adapter_id
        self._result_id_factory = result_id_factory or _default_result_id
        self.execution_attempts: list[tuple[str, str, str]] = []

    def execute(
        self,
        item: IntegrationPlanItem,
        *,
        scenario: str,
        synthetic_subject_reference: str,
        context: ObservabilityContext,
        started_at: datetime,
        completed_at: datetime,
        duration_ms: float,
    ) -> IntegrationResult:
        self.execution_attempts.append((item.integration_class, item.adapter_id, scenario))
        result_status = _status_for_scenario(scenario)
        result_id = self._result_id_factory(
            "|".join(
                (
                    item.tenant_id,
                    item.product_type,
                    item.integration_class,
                    item.adapter_id,
                    scenario,
                    synthetic_subject_reference,
                )
            )
        )
        return IntegrationResult.create(
            result_id=result_id,
            tenant_id=item.tenant_id,
            product_type=item.product_type,
            integration_class=item.integration_class,
            adapter_id=item.adapter_id,
            status=result_status,
            scenario=scenario,
            reason_codes=_reason_codes_for_scenario(scenario),
            summary=_summary_for(item.integration_class, scenario),
            correlation_id=context.correlation_id,
            trace_id=context.trace_id,
            started_at=started_at,
            completed_at=completed_at,
            duration_ms=duration_ms,
        )


class InMemoryMockIntegrationAdapterRegistry:
    def __init__(self, adapters: tuple[InMemoryMockIntegrationAdapter, ...]) -> None:
        self._adapters: dict[tuple[str, str], MockIntegrationAdapter] = {
            (adapter.integration_class, adapter.adapter_id): adapter for adapter in adapters
        }

    @classmethod
    def for_mvp_defaults(cls) -> InMemoryMockIntegrationAdapterRegistry:
        return cls(
            (
                InMemoryMockIntegrationAdapter(
                    integration_class="kyc_kyb",
                    adapter_id="mock-kyc-basic-v1",
                ),
                InMemoryMockIntegrationAdapter(
                    integration_class="credit_bureau",
                    adapter_id="mock-credit-bureau-v1",
                ),
                InMemoryMockIntegrationAdapter(
                    integration_class="anti_fraud",
                    adapter_id="mock-antifraud-v1",
                ),
                InMemoryMockIntegrationAdapter(
                    integration_class="receivables",
                    adapter_id="mock-receivables-v1",
                ),
            )
        )

    @property
    def execution_attempts(self) -> tuple[tuple[str, str, str], ...]:
        attempts: list[tuple[str, str, str]] = []
        for adapter in self._adapters.values():
            if isinstance(adapter, InMemoryMockIntegrationAdapter):
                attempts.extend(adapter.execution_attempts)
        return tuple(attempts)

    def get_adapter(self, integration_class: str, adapter_id: str) -> MockIntegrationAdapter | None:
        return self._adapters.get((integration_class, adapter_id))


def _status_for_scenario(scenario: str) -> str:
    return {
        MockIntegrationScenario.SYNTHETIC_SUCCESS.value: IntegrationResultStatus.COMPLETED.value,
        MockIntegrationScenario.SYNTHETIC_PARTIAL.value: IntegrationResultStatus.PARTIAL.value,
        MockIntegrationScenario.SYNTHETIC_NOT_FOUND.value: IntegrationResultStatus.NOT_FOUND.value,
        MockIntegrationScenario.SYNTHETIC_FAILURE.value: IntegrationResultStatus.FAILED.value,
    }[scenario]


def _reason_codes_for_scenario(scenario: str) -> tuple[str, ...]:
    return {
        MockIntegrationScenario.SYNTHETIC_SUCCESS.value: ("synthetic_match",),
        MockIntegrationScenario.SYNTHETIC_PARTIAL.value: ("synthetic_partial_data",),
        MockIntegrationScenario.SYNTHETIC_NOT_FOUND.value: ("synthetic_subject_not_found",),
        MockIntegrationScenario.SYNTHETIC_FAILURE.value: ("synthetic_controlled_failure",),
    }[scenario]


def _summary_for(integration_class: str, scenario: str) -> Mapping[str, object]:
    synthetic_data_type = SyntheticDataType.MOCK_INTEGRATION_RESULT.value
    summaries = {
        "kyc_kyb": {
            MockIntegrationScenario.SYNTHETIC_SUCCESS.value: {
                "synthetic_data_type": synthetic_data_type,
                "identity_status": "verified",
                "document_status": "valid",
                "sanctions_status": "clear",
            },
            MockIntegrationScenario.SYNTHETIC_PARTIAL.value: {
                "synthetic_data_type": synthetic_data_type,
                "identity_status": "partial",
                "document_status": "pending",
                "sanctions_status": "clear",
            },
            MockIntegrationScenario.SYNTHETIC_NOT_FOUND.value: {
                "synthetic_data_type": synthetic_data_type,
                "identity_status": "not_found",
                "document_status": "not_found",
                "sanctions_status": "unknown",
            },
            MockIntegrationScenario.SYNTHETIC_FAILURE.value: {
                "synthetic_data_type": synthetic_data_type,
                "identity_status": "unavailable",
                "document_status": "unavailable",
                "sanctions_status": "unknown",
            },
        },
        "credit_bureau": {
            MockIntegrationScenario.SYNTHETIC_SUCCESS.value: {
                "synthetic_data_type": synthetic_data_type,
                "score_band": "high",
                "restriction_status": "clear",
                "debt_profile": "stable",
            },
            MockIntegrationScenario.SYNTHETIC_PARTIAL.value: {
                "synthetic_data_type": synthetic_data_type,
                "score_band": "medium",
                "restriction_status": "partial",
                "debt_profile": "limited",
            },
            MockIntegrationScenario.SYNTHETIC_NOT_FOUND.value: {
                "synthetic_data_type": synthetic_data_type,
                "score_band": "unknown",
                "restriction_status": "not_found",
                "debt_profile": "unknown",
            },
            MockIntegrationScenario.SYNTHETIC_FAILURE.value: {
                "synthetic_data_type": synthetic_data_type,
                "score_band": "unavailable",
                "restriction_status": "unknown",
                "debt_profile": "unknown",
            },
        },
        "anti_fraud": {
            MockIntegrationScenario.SYNTHETIC_SUCCESS.value: {
                "synthetic_data_type": synthetic_data_type,
                "risk_band": "low",
                "device_status": "trusted",
                "velocity_status": "normal",
            },
            MockIntegrationScenario.SYNTHETIC_PARTIAL.value: {
                "synthetic_data_type": synthetic_data_type,
                "risk_band": "medium",
                "device_status": "unknown",
                "velocity_status": "elevated",
            },
            MockIntegrationScenario.SYNTHETIC_NOT_FOUND.value: {
                "synthetic_data_type": synthetic_data_type,
                "risk_band": "unknown",
                "device_status": "not_found",
                "velocity_status": "unknown",
            },
            MockIntegrationScenario.SYNTHETIC_FAILURE.value: {
                "synthetic_data_type": synthetic_data_type,
                "risk_band": "unavailable",
                "device_status": "unknown",
                "velocity_status": "unknown",
            },
        },
        "receivables": {
            MockIntegrationScenario.SYNTHETIC_SUCCESS.value: {
                "synthetic_data_type": synthetic_data_type,
                "eligibility_status": "eligible",
                "coverage_band": "high",
                "settlement_status": "current",
            },
            MockIntegrationScenario.SYNTHETIC_PARTIAL.value: {
                "synthetic_data_type": synthetic_data_type,
                "eligibility_status": "partial",
                "coverage_band": "medium",
                "settlement_status": "limited",
            },
            MockIntegrationScenario.SYNTHETIC_NOT_FOUND.value: {
                "synthetic_data_type": synthetic_data_type,
                "eligibility_status": "not_found",
                "coverage_band": "unknown",
                "settlement_status": "unknown",
            },
            MockIntegrationScenario.SYNTHETIC_FAILURE.value: {
                "synthetic_data_type": synthetic_data_type,
                "eligibility_status": "unavailable",
                "coverage_band": "unknown",
                "settlement_status": "unknown",
            },
        },
    }
    return summaries[integration_class][scenario]


def _default_result_id(seed: str) -> str:
    return f"ires_{sha256(seed.encode('utf-8')).hexdigest()[:32]}"
