from __future__ import annotations

from dataclasses import dataclass
from time import perf_counter
from typing import Any

from creditos_observability.context import ObservabilityContext
from creditos_observability.logging import build_structured_log

from creditos_proposal_intake.application.ports import CanonicalProposalRepository
from creditos_proposal_intake.application.use_cases.validate_and_normalize_proposal import (
    ValidateAndNormalizeProposal,
    ValidateAndNormalizeProposalCommand,
)
from creditos_proposal_intake.domain.entities import CanonicalProposal

SERVICE_NAME = "proposal-intake"
SERVICE_VERSION = "0.1.0"
CONTRACT = "proposal-intake-public-application"
CONTRACT_VERSION = "v1"


@dataclass(frozen=True, slots=True)
class ProposalIntakeValidationResult:
    proposal: CanonicalProposal
    logs: tuple[dict[str, Any], ...]


class ProposalIntakeApplicationService:
    def __init__(
        self,
        *,
        repository: CanonicalProposalRepository,
        environment: str,
    ) -> None:
        self._validate_and_normalize = ValidateAndNormalizeProposal(repository=repository)
        self._environment = environment
        self._logged_events: list[dict[str, Any]] = []

    @property
    def logged_events(self) -> tuple[dict[str, Any], ...]:
        return tuple(self._logged_events)

    def validate_and_normalize(
        self,
        command: ValidateAndNormalizeProposalCommand,
        *,
        context: ObservabilityContext,
    ) -> ProposalIntakeValidationResult:
        started_at = perf_counter()
        try:
            tenant_id = _require_trusted_tenant(context)
            result = self._validate_and_normalize.execute(command, tenant_id=tenant_id)
            event = self._log_operation(
                context=context,
                status="accepted",
                duration_ms=_duration_ms(started_at),
                extra={
                    "schema_version": result.proposal.schema_version,
                    "product_type": result.proposal.product_type,
                    "channel": result.proposal.channel,
                    "callback_configured": result.proposal.callback_profile_ref is not None,
                },
                payload=command,
            )
            return ProposalIntakeValidationResult(
                proposal=result.proposal,
                logs=(event,),
            )
        except Exception as error:
            self._log_operation(
                context=context,
                status="rejected",
                duration_ms=_duration_ms(started_at),
                extra={
                    "error_code": getattr(error, "code", type(error).__name__),
                    "field_path": getattr(error, "field_path", None),
                },
                payload=command,
                error_type=type(error).__name__,
            )
            raise

    def _log_operation(
        self,
        *,
        context: ObservabilityContext,
        status: str,
        duration_ms: float,
        extra: dict[str, Any],
        payload: Any,
        error_type: str | None = None,
    ) -> dict[str, Any]:
        event = build_structured_log(
            context=context,
            service_name=SERVICE_NAME,
            service_version=SERVICE_VERSION,
            environment=self._environment,
            operation="proposal_intake.validate_and_normalize",
            source="public-proposal-command",
            destination=SERVICE_NAME,
            contract=CONTRACT,
            contract_version=CONTRACT_VERSION,
            status=status,
            duration_ms=duration_ms,
            error_type=error_type,
            payload=payload,
            extra=extra,
        )
        self._logged_events.append(event)
        return event


def _require_trusted_tenant(context: ObservabilityContext) -> str:
    if not context.tenant_id:
        from creditos_proposal_intake.domain.errors import ProposalValidationError

        raise ProposalValidationError(
            "tenant confiável ausente",
            field_path="context.tenant_id",
        )
    return context.tenant_id


def _duration_ms(started_at: float) -> float:
    return round((perf_counter() - started_at) * 1000, 3)
