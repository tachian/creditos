from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import datetime

from creditos_decision.domain.entities.credit_policy import CreditPolicy
from creditos_decision.domain.entities.reason_code_catalog import ReasonCodeCatalog
from creditos_decision.domain.errors import PolicyValidationError
from creditos_decision.domain.value_objects.credit_decision import (
    CreditDecisionApprovedTerms,
    CreditDecisionInput,
    input_fingerprint_for,
    validate_credit_decision_id,
    validate_decided_at,
    validate_proposal_id,
)
from creditos_decision.domain.value_objects.policy import (
    PolicyApplicability,
    PolicyOutcome,
    _parse_enum,
    _validate_technical_id,
    parse_policy_fallback_action,
    parse_product_type,
    validate_correlation_id,
    validate_policy_id,
    validate_policy_version_id,
    validate_tenant_id,
)
from creditos_decision.domain.value_objects.policy_evaluation import (
    PolicyEvaluationIssue,
    PolicyEvaluationResult,
)
from creditos_decision.domain.value_objects.reason_codes import (
    validate_reason_code_catalog_id,
    validate_reason_code_catalog_version_id,
)


@dataclass(frozen=True, slots=True)
class CreditDecision:
    decision_id: str
    tenant_id: str
    proposal_id: str
    product_type: str
    channel: str
    decided_at: datetime
    policy_id: str
    policy_version_id: str
    policy_revision: int
    reason_code_catalog_id: str
    reason_code_catalog_version_id: str
    outcome: str
    triggered_rule_ids: tuple[str, ...]
    reason_code_refs: tuple[str, ...]
    factor_refs: tuple[str, ...]
    validation_issues: tuple[PolicyEvaluationIssue, ...]
    integration_result_refs: tuple[str, ...]
    input_fingerprint: str
    correlation_id: str
    decision_fingerprint: str
    approved_terms: CreditDecisionApprovedTerms | None = None
    fallback_action: str | None = None
    required_data_refs: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if self.policy_revision < 1:
            raise PolicyValidationError(
                "revisão de política inválida",
                code="invalid_decision_policy_revision",
                field_path="policy_revision",
            )
        channel = PolicyApplicability.create(channels=(self.channel,)).channels[0]
        outcome = _parse_enum(
            PolicyOutcome,
            self.outcome,
            code="unsupported_credit_decision_outcome",
            field_path="outcome",
        )
        for issue in self.validation_issues:
            if not isinstance(issue, PolicyEvaluationIssue):
                raise PolicyValidationError(
                    "issue de decisão inválida",
                    code="invalid_credit_decision_issue",
                    field_path="validation_issues",
                )
        object.__setattr__(self, "decision_id", validate_credit_decision_id(self.decision_id))
        object.__setattr__(self, "tenant_id", validate_tenant_id(self.tenant_id))
        object.__setattr__(self, "proposal_id", validate_proposal_id(self.proposal_id))
        object.__setattr__(self, "product_type", parse_product_type(self.product_type))
        object.__setattr__(self, "channel", channel)
        object.__setattr__(self, "decided_at", validate_decided_at(self.decided_at))
        object.__setattr__(self, "policy_id", validate_policy_id(self.policy_id))
        object.__setattr__(
            self,
            "policy_version_id",
            validate_policy_version_id(self.policy_version_id),
        )
        object.__setattr__(
            self,
            "reason_code_catalog_id",
            validate_reason_code_catalog_id(self.reason_code_catalog_id),
        )
        object.__setattr__(
            self,
            "reason_code_catalog_version_id",
            validate_reason_code_catalog_version_id(self.reason_code_catalog_version_id),
        )
        object.__setattr__(self, "outcome", outcome)
        object.__setattr__(
            self,
            "triggered_rule_ids",
            _validate_unique_ids(self.triggered_rule_ids, field_path="triggered_rule_ids"),
        )
        object.__setattr__(
            self,
            "reason_code_refs",
            _validate_unique_ids(self.reason_code_refs, field_path="reason_code_refs"),
        )
        object.__setattr__(
            self,
            "factor_refs",
            _validate_unique_ids(self.factor_refs, field_path="factor_refs"),
        )
        object.__setattr__(self, "validation_issues", tuple(self.validation_issues))
        object.__setattr__(
            self,
            "integration_result_refs",
            _validate_unique_ids(
                self.integration_result_refs,
                field_path="integration_result_refs",
            ),
        )
        if self.fallback_action is not None:
            object.__setattr__(
                self,
                "fallback_action",
                parse_policy_fallback_action(self.fallback_action),
            )
        object.__setattr__(
            self,
            "required_data_refs",
            _validate_unique_ids(self.required_data_refs, field_path="required_data_refs"),
        )
        object.__setattr__(
            self,
            "input_fingerprint",
            _validate_hex_fingerprint(self.input_fingerprint, field_path="input_fingerprint"),
        )
        object.__setattr__(self, "correlation_id", validate_correlation_id(self.correlation_id))
        object.__setattr__(
            self,
            "decision_fingerprint",
            _validate_hex_fingerprint(
                self.decision_fingerprint,
                field_path="decision_fingerprint",
            ),
        )
        if self.outcome == PolicyOutcome.APPROVE.value and self.approved_terms is None:
            raise PolicyValidationError(
                "aprovação exige termos aprovados completos",
                code="credit_decision_approved_terms_required",
                field_path="approved_terms",
            )
        if self.outcome == PolicyOutcome.APPROVE_WITH_CHANGES.value and self.approved_terms is None:
            raise PolicyValidationError(
                "aprovação com alterações exige termos ajustados",
                code="credit_decision_adjusted_terms_required",
                field_path="approved_terms",
            )
        expected_fingerprint = _compute_decision_fingerprint(self)
        if self.decision_fingerprint != expected_fingerprint:
            raise PolicyValidationError(
                "fingerprint de decisão inválido",
                code="invalid_credit_decision_fingerprint",
                field_path="decision_fingerprint",
            )

    @classmethod
    def create(
        cls,
        *,
        decision_id: str,
        policy: CreditPolicy,
        catalog: ReasonCodeCatalog,
        decision_input: CreditDecisionInput,
        evaluation: PolicyEvaluationResult,
        channel: str,
        correlation_id: str,
        decided_at: datetime,
    ) -> CreditDecision:
        if not policy.is_executable_in_production:
            raise PolicyValidationError(
                "decisão exige política publicada",
                code="credit_decision_requires_published_policy",
                field_path="policy.status",
            )
        if not catalog.is_referenceable_for_final_decisions:
            raise PolicyValidationError(
                "decisão exige catálogo publicado",
                code="credit_decision_requires_published_catalog",
                field_path="reason_code_catalog_version_id",
            )
        if catalog.tenant_id != policy.tenant_id or catalog.product_type != policy.product_type:
            raise PolicyValidationError(
                "catálogo incompatível com política",
                code="credit_decision_catalog_mismatch",
                field_path="reason_code_catalog_id",
            )
        if (
            catalog.catalog_id != policy.reason_code_catalog_id
            or catalog.catalog_version_id != policy.reason_code_catalog_version_id
        ):
            raise PolicyValidationError(
                "catálogo diferente da proveniência da política",
                code="credit_decision_catalog_provenance_mismatch",
                field_path="reason_code_catalog_version_id",
            )
        if evaluation.evaluation_id != decision_input.proposal_id:
            raise PolicyValidationError(
                "avaliação não pertence à proposta da decisão",
                code="credit_decision_evaluation_mismatch",
                field_path="evaluation_id",
            )
        approved_terms = (
            CreditDecisionApprovedTerms.from_decision_input(decision_input)
            if evaluation.outcome == PolicyOutcome.APPROVE.value
            else None
        )
        if evaluation.outcome == PolicyOutcome.APPROVE_WITH_CHANGES.value:
            approved_terms = CreditDecisionApprovedTerms.adjusted_from_policy_limits(
                decision_input,
                policy.limits,
            )
            if approved_terms is None:
                raise PolicyValidationError(
                    "aprovação com alterações exige termos ajustados",
                    code="credit_decision_adjusted_terms_required",
                    field_path="approved_terms",
                )
        if evaluation.outcome == PolicyOutcome.APPROVE.value and approved_terms is None:
            raise PolicyValidationError(
                "aprovação exige termos aprovados completos",
                code="credit_decision_approved_terms_required",
                field_path="approved_terms",
            )
        validated_decision_id = validate_credit_decision_id(decision_id)
        validated_decided_at = validate_decided_at(decided_at)
        validated_correlation_id = validate_correlation_id(correlation_id)
        input_fingerprint = input_fingerprint_for(decision_input.field_values)
        return cls(
            decision_id=validated_decision_id,
            tenant_id=policy.tenant_id,
            proposal_id=decision_input.proposal_id,
            product_type=policy.product_type,
            channel=channel,
            decided_at=validated_decided_at,
            policy_id=policy.policy_id,
            policy_version_id=policy.policy_version_id,
            policy_revision=policy.revision,
            reason_code_catalog_id=catalog.catalog_id,
            reason_code_catalog_version_id=catalog.catalog_version_id,
            outcome=evaluation.outcome,
            triggered_rule_ids=evaluation.triggered_rule_ids,
            reason_code_refs=evaluation.reason_code_refs,
            factor_refs=evaluation.factor_refs,
            validation_issues=evaluation.validation_issues,
            integration_result_refs=decision_input.integration_result_refs,
            input_fingerprint=input_fingerprint,
            correlation_id=validated_correlation_id,
            approved_terms=approved_terms,
            fallback_action=evaluation.fallback_action,
            required_data_refs=evaluation.required_data_refs,
            decision_fingerprint=_compute_decision_fingerprint_from_parts(
                tenant_id=policy.tenant_id,
                proposal_id=decision_input.proposal_id,
                product_type=policy.product_type,
                channel=channel,
                policy_id=policy.policy_id,
                policy_version_id=policy.policy_version_id,
                policy_revision=policy.revision,
                reason_code_catalog_id=catalog.catalog_id,
                reason_code_catalog_version_id=catalog.catalog_version_id,
                outcome=evaluation.outcome,
                triggered_rule_ids=evaluation.triggered_rule_ids,
                reason_code_refs=evaluation.reason_code_refs,
                factor_refs=evaluation.factor_refs,
                validation_issues=evaluation.validation_issues,
                integration_result_refs=decision_input.integration_result_refs,
                input_fingerprint=input_fingerprint,
                approved_terms=approved_terms,
                fallback_action=evaluation.fallback_action,
                required_data_refs=evaluation.required_data_refs,
            ),
        )


def _compute_decision_fingerprint(decision: CreditDecision) -> str:
    return _compute_decision_fingerprint_from_parts(
        tenant_id=decision.tenant_id,
        proposal_id=decision.proposal_id,
        product_type=decision.product_type,
        channel=decision.channel,
        policy_id=decision.policy_id,
        policy_version_id=decision.policy_version_id,
        policy_revision=decision.policy_revision,
        reason_code_catalog_id=decision.reason_code_catalog_id,
        reason_code_catalog_version_id=decision.reason_code_catalog_version_id,
        outcome=decision.outcome,
        triggered_rule_ids=decision.triggered_rule_ids,
        reason_code_refs=decision.reason_code_refs,
        factor_refs=decision.factor_refs,
        validation_issues=decision.validation_issues,
        integration_result_refs=decision.integration_result_refs,
        input_fingerprint=decision.input_fingerprint,
        approved_terms=decision.approved_terms,
        fallback_action=decision.fallback_action,
        required_data_refs=decision.required_data_refs,
    )


def _compute_decision_fingerprint_from_parts(
    *,
    tenant_id: str,
    proposal_id: str,
    product_type: str,
    channel: str,
    policy_id: str,
    policy_version_id: str,
    policy_revision: int,
    reason_code_catalog_id: str,
    reason_code_catalog_version_id: str,
    outcome: str,
    triggered_rule_ids: tuple[str, ...],
    reason_code_refs: tuple[str, ...],
    factor_refs: tuple[str, ...],
    validation_issues: tuple[PolicyEvaluationIssue, ...],
    integration_result_refs: tuple[str, ...],
    input_fingerprint: str,
    approved_terms: CreditDecisionApprovedTerms | None,
    fallback_action: str | None,
    required_data_refs: tuple[str, ...],
) -> str:
    approved_terms_payload = None
    if approved_terms is not None:
        approved_terms_payload = {
            "approved_amount_units": approved_terms.approved_amount_units,
            "approved_installments": approved_terms.approved_installments,
            "approved_term_days": approved_terms.approved_term_days,
        }
    payload = {
        "factor_refs": sorted(factor_refs),
        "integration_result_refs": sorted(integration_result_refs),
        "input_fingerprint": input_fingerprint,
        "channel": channel,
        "outcome": outcome,
        "policy_id": policy_id,
        "policy_revision": policy_revision,
        "policy_version_id": policy_version_id,
        "product_type": product_type,
        "proposal_id": proposal_id,
        "reason_code_catalog_id": reason_code_catalog_id,
        "reason_code_catalog_version_id": reason_code_catalog_version_id,
        "reason_code_refs": sorted(reason_code_refs),
        "required_data_refs": sorted(required_data_refs),
        "tenant_id": tenant_id,
        "triggered_rule_ids": sorted(triggered_rule_ids),
        "validation_issue_codes": sorted(issue.code for issue in validation_issues),
        "approved_terms": approved_terms_payload,
        "fallback_action": fallback_action,
    }
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(encoded).hexdigest()


def _validate_unique_ids(values: tuple[str, ...], *, field_path: str) -> tuple[str, ...]:
    parsed = tuple(_validate_technical_id(value, field_path=field_path) for value in values)
    if len(set(parsed)) != len(parsed):
        raise PolicyValidationError(
            "identificador duplicado",
            code="duplicate_credit_decision_identifier",
            field_path=field_path,
        )
    return parsed


def _validate_hex_fingerprint(value: str, *, field_path: str) -> str:
    if len(value) != 64 or any(character not in "0123456789abcdef" for character in value):
        raise PolicyValidationError(
            "fingerprint inválido",
            code="invalid_credit_decision_fingerprint",
            field_path=field_path,
        )
    return value
