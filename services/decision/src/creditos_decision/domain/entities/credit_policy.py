from __future__ import annotations

import hashlib
from dataclasses import dataclass, replace
from datetime import UTC, datetime

from creditos_decision.domain.errors import PolicyImmutableError, PolicyValidationError
from creditos_decision.domain.value_objects.policy import (
    PolicyApplicability,
    PolicyChangelogEntry,
    PolicyCriterion,
    PolicyFallbackAction,
    PolicyLimit,
    PolicyRule,
    parse_policy_status,
    parse_product_type,
    validate_policy_id,
    validate_policy_version_id,
    validate_subject_id,
    validate_tenant_id,
)
from creditos_decision.domain.value_objects.reason_codes import (
    validate_reason_code_catalog_id,
    validate_reason_code_catalog_version_id,
)


@dataclass(frozen=True, slots=True)
class CreditPolicy:
    policy_id: str
    policy_version_id: str
    tenant_id: str
    owner_subject_id: str
    product_type: str
    reason_code_catalog_id: str
    reason_code_catalog_version_id: str
    status: str
    version: int
    revision: int
    applicability: PolicyApplicability
    rules: tuple[PolicyRule, ...]
    criteria: tuple[PolicyCriterion, ...]
    limits: tuple[PolicyLimit, ...]
    fallback_action: PolicyFallbackAction
    changelog: tuple[PolicyChangelogEntry, ...]
    created_at: datetime
    updated_at: datetime
    _governed_fingerprint: str = ""

    def __post_init__(self) -> None:
        if self.version < 1:
            raise PolicyValidationError(
                "versão inválida",
                code="invalid_policy_version",
                field_path="version",
            )
        if self.revision < 1:
            raise PolicyValidationError(
                "revisão inválida",
                code="invalid_policy_revision",
                field_path="revision",
            )
        if not isinstance(self.applicability, PolicyApplicability):
            raise PolicyValidationError(
                "aplicabilidade inválida",
                code="invalid_policy_applicability",
                field_path="applicability",
            )
        if not isinstance(self.fallback_action, PolicyFallbackAction):
            raise PolicyValidationError(
                "fallback de política inválido",
                code="invalid_policy_fallback_action",
                field_path="fallback_action",
            )
        rules = tuple(self.rules)
        criteria = tuple(self.criteria)
        limits = tuple(self.limits)
        changelog = tuple(self.changelog)
        _require_non_empty_tuple(rules, field_path="rules")
        _require_non_empty_tuple(criteria, field_path="criteria")
        _require_non_empty_tuple(limits, field_path="limits")
        _require_non_empty_tuple(changelog, field_path="changelog")
        _require_items(rules, PolicyRule, field_path="rules")
        _require_items(criteria, PolicyCriterion, field_path="criteria")
        _require_items(limits, PolicyLimit, field_path="limits")
        _require_items(changelog, PolicyChangelogEntry, field_path="changelog")
        _validate_changelog_chain(changelog, revision=self.revision)
        _validate_aware_utc_datetime(self.created_at, field_path="created_at")
        _validate_aware_utc_datetime(self.updated_at, field_path="updated_at")
        parsed_status = parse_policy_status(self.status)
        parsed_owner_subject_id = validate_subject_id(
            self.owner_subject_id,
            field_path="owner_subject_id",
        )
        parsed_product_type = parse_product_type(self.product_type)
        parsed_reason_code_catalog_id = validate_reason_code_catalog_id(self.reason_code_catalog_id)
        parsed_reason_code_catalog_version_id = validate_reason_code_catalog_version_id(
            self.reason_code_catalog_version_id
        )
        fingerprint = _compute_governed_fingerprint(
            status=parsed_status,
            owner_subject_id=parsed_owner_subject_id,
            product_type=parsed_product_type,
            reason_code_catalog_id=parsed_reason_code_catalog_id,
            reason_code_catalog_version_id=parsed_reason_code_catalog_version_id,
            applicability=self.applicability,
            rules=rules,
            criteria=criteria,
            limits=limits,
            fallback_action=self.fallback_action,
        )
        if parsed_status != "draft" and (
            not self._governed_fingerprint or self._governed_fingerprint != fingerprint
        ):
            raise PolicyImmutableError("política não pode ser alterada")
        object.__setattr__(self, "policy_id", validate_policy_id(self.policy_id))
        object.__setattr__(
            self,
            "policy_version_id",
            validate_policy_version_id(self.policy_version_id),
        )
        object.__setattr__(self, "tenant_id", validate_tenant_id(self.tenant_id))
        object.__setattr__(self, "owner_subject_id", parsed_owner_subject_id)
        object.__setattr__(self, "product_type", parsed_product_type)
        object.__setattr__(self, "reason_code_catalog_id", parsed_reason_code_catalog_id)
        object.__setattr__(
            self,
            "reason_code_catalog_version_id",
            parsed_reason_code_catalog_version_id,
        )
        object.__setattr__(self, "status", parsed_status)
        object.__setattr__(self, "rules", rules)
        object.__setattr__(self, "criteria", criteria)
        object.__setattr__(self, "limits", limits)
        object.__setattr__(self, "fallback_action", self.fallback_action)
        object.__setattr__(self, "changelog", changelog)
        object.__setattr__(self, "_governed_fingerprint", fingerprint)

    @classmethod
    def create_draft(
        cls,
        *,
        policy_id: str,
        policy_version_id: str,
        tenant_id: str,
        owner_subject_id: str,
        product_type: str,
        reason_code_catalog_id: str,
        reason_code_catalog_version_id: str,
        applicability: PolicyApplicability,
        rules: tuple[PolicyRule, ...],
        criteria: tuple[PolicyCriterion, ...],
        limits: tuple[PolicyLimit, ...],
        now: datetime,
        actor_subject_id: str,
        correlation_id: str,
        change_summary: str,
        version: int = 1,
        fallback_action: PolicyFallbackAction | None = None,
    ) -> CreditPolicy:
        revision = 1
        changelog = (
            PolicyChangelogEntry.create(
                change_type="created",
                actor_subject_id=actor_subject_id,
                changed_at=now,
                change_summary=change_summary,
                correlation_id=correlation_id,
                previous_revision=None,
                resulting_revision=revision,
            ),
        )
        return cls.restore(
            policy_id=policy_id,
            policy_version_id=policy_version_id,
            tenant_id=tenant_id,
            owner_subject_id=owner_subject_id,
            product_type=product_type,
            reason_code_catalog_id=reason_code_catalog_id,
            reason_code_catalog_version_id=reason_code_catalog_version_id,
            status="draft",
            version=version,
            revision=revision,
            applicability=applicability,
            rules=rules,
            criteria=criteria,
            limits=limits,
            fallback_action=fallback_action,
            changelog=changelog,
            created_at=now,
            updated_at=now,
        )

    @classmethod
    def restore(
        cls,
        *,
        policy_id: str,
        policy_version_id: str,
        tenant_id: str,
        owner_subject_id: str,
        product_type: str,
        reason_code_catalog_id: str,
        reason_code_catalog_version_id: str,
        status: str,
        version: int,
        revision: int,
        applicability: PolicyApplicability,
        rules: tuple[PolicyRule, ...],
        criteria: tuple[PolicyCriterion, ...],
        limits: tuple[PolicyLimit, ...],
        changelog: tuple[PolicyChangelogEntry, ...],
        created_at: datetime,
        updated_at: datetime,
        fallback_action: PolicyFallbackAction | None = None,
    ) -> CreditPolicy:
        if version < 1:
            raise PolicyValidationError(
                "versão inválida",
                code="invalid_policy_version",
                field_path="version",
            )
        if revision < 1:
            raise PolicyValidationError(
                "revisão inválida",
                code="invalid_policy_revision",
                field_path="revision",
            )
        if not isinstance(applicability, PolicyApplicability):
            raise PolicyValidationError(
                "aplicabilidade inválida",
                code="invalid_policy_applicability",
                field_path="applicability",
            )
        parsed_fallback_action = fallback_action or PolicyFallbackAction.create()
        if not isinstance(parsed_fallback_action, PolicyFallbackAction):
            raise PolicyValidationError(
                "fallback de política inválido",
                code="invalid_policy_fallback_action",
                field_path="fallback_action",
            )
        _require_non_empty_tuple(rules, field_path="rules")
        _require_non_empty_tuple(criteria, field_path="criteria")
        _require_non_empty_tuple(limits, field_path="limits")
        _require_non_empty_tuple(changelog, field_path="changelog")
        _require_items(rules, PolicyRule, field_path="rules")
        _require_items(criteria, PolicyCriterion, field_path="criteria")
        _require_items(limits, PolicyLimit, field_path="limits")
        _require_items(changelog, PolicyChangelogEntry, field_path="changelog")
        _validate_changelog_chain(changelog, revision=revision)
        _validate_aware_utc_datetime(created_at, field_path="created_at")
        _validate_aware_utc_datetime(updated_at, field_path="updated_at")
        parsed_status = parse_policy_status(status)
        parsed_owner_subject_id = validate_subject_id(
            owner_subject_id,
            field_path="owner_subject_id",
        )
        parsed_product_type = parse_product_type(product_type)
        parsed_reason_code_catalog_id = validate_reason_code_catalog_id(reason_code_catalog_id)
        parsed_reason_code_catalog_version_id = validate_reason_code_catalog_version_id(
            reason_code_catalog_version_id
        )
        return cls(
            policy_id=validate_policy_id(policy_id),
            policy_version_id=validate_policy_version_id(policy_version_id),
            tenant_id=validate_tenant_id(tenant_id),
            owner_subject_id=parsed_owner_subject_id,
            product_type=parsed_product_type,
            reason_code_catalog_id=parsed_reason_code_catalog_id,
            reason_code_catalog_version_id=parsed_reason_code_catalog_version_id,
            status=parsed_status,
            version=version,
            revision=revision,
            applicability=applicability,
            rules=tuple(rules),
            criteria=tuple(criteria),
            limits=tuple(limits),
            fallback_action=parsed_fallback_action,
            changelog=tuple(changelog),
            created_at=created_at,
            updated_at=updated_at,
            _governed_fingerprint=_compute_governed_fingerprint(
                status=parsed_status,
                owner_subject_id=parsed_owner_subject_id,
                product_type=parsed_product_type,
                reason_code_catalog_id=parsed_reason_code_catalog_id,
                reason_code_catalog_version_id=parsed_reason_code_catalog_version_id,
                applicability=applicability,
                rules=tuple(rules),
                criteria=tuple(criteria),
                limits=tuple(limits),
                fallback_action=parsed_fallback_action,
            ),
        )

    @property
    def is_executable_in_production(self) -> bool:
        return self.status == "published"

    def update_draft(
        self,
        *,
        rules: tuple[PolicyRule, ...],
        criteria: tuple[PolicyCriterion, ...],
        limits: tuple[PolicyLimit, ...],
        applicability: PolicyApplicability,
        now: datetime,
        actor_subject_id: str,
        correlation_id: str,
        change_summary: str,
        reason_code_catalog_id: str,
        reason_code_catalog_version_id: str,
        owner_subject_id: str | None = None,
        product_type: str | None = None,
        fallback_action: PolicyFallbackAction | None = None,
    ) -> CreditPolicy:
        if self.status != "draft":
            raise PolicyImmutableError("política não pode ser alterada")
        _require_non_empty_tuple(rules, field_path="rules")
        _require_non_empty_tuple(criteria, field_path="criteria")
        _require_non_empty_tuple(limits, field_path="limits")
        _require_items(rules, PolicyRule, field_path="rules")
        _require_items(criteria, PolicyCriterion, field_path="criteria")
        _require_items(limits, PolicyLimit, field_path="limits")
        if not isinstance(applicability, PolicyApplicability):
            raise PolicyValidationError(
                "aplicabilidade inválida",
                code="invalid_policy_applicability",
                field_path="applicability",
            )
        parsed_fallback_action = fallback_action or self.fallback_action
        if not isinstance(parsed_fallback_action, PolicyFallbackAction):
            raise PolicyValidationError(
                "fallback de política inválido",
                code="invalid_policy_fallback_action",
                field_path="fallback_action",
            )
        _validate_aware_utc_datetime(now, field_path="updated_at")
        next_revision = self.revision + 1
        changelog_entry = PolicyChangelogEntry.create(
            change_type="updated",
            actor_subject_id=actor_subject_id,
            changed_at=now,
            change_summary=change_summary,
            correlation_id=correlation_id,
            previous_revision=self.revision,
            resulting_revision=next_revision,
        )
        return replace(
            self,
            revision=next_revision,
            owner_subject_id=owner_subject_id or self.owner_subject_id,
            product_type=product_type or self.product_type,
            reason_code_catalog_id=reason_code_catalog_id,
            reason_code_catalog_version_id=reason_code_catalog_version_id,
            applicability=applicability,
            rules=tuple(rules),
            criteria=tuple(criteria),
            limits=tuple(limits),
            fallback_action=parsed_fallback_action,
            changelog=(*self.changelog, changelog_entry),
            updated_at=now,
        )

    def publish(
        self,
        *,
        now: datetime,
        actor_subject_id: str,
        correlation_id: str,
        change_summary: str,
    ) -> CreditPolicy:
        if self.status != "draft":
            raise PolicyImmutableError("política não pode ser alterada")
        if self.applicability.starts_at is None:
            raise PolicyValidationError(
                "vigência inicial obrigatória",
                code="missing_policy_effective_start",
                field_path="applicability.starts_at",
            )
        _validate_aware_utc_datetime(now, field_path="updated_at")
        if self.applicability.ends_at is not None and self.applicability.ends_at <= now:
            raise PolicyValidationError(
                "vigência expirada",
                code="expired_policy_effective_window",
                field_path="applicability.ends_at",
            )
        next_revision = self.revision + 1
        changelog_entry = PolicyChangelogEntry.create(
            change_type="published",
            actor_subject_id=actor_subject_id,
            changed_at=now,
            change_summary=change_summary,
            correlation_id=correlation_id,
            previous_revision=self.revision,
            resulting_revision=next_revision,
        )
        return CreditPolicy.restore(
            policy_id=self.policy_id,
            policy_version_id=self.policy_version_id,
            tenant_id=self.tenant_id,
            owner_subject_id=self.owner_subject_id,
            product_type=self.product_type,
            reason_code_catalog_id=self.reason_code_catalog_id,
            reason_code_catalog_version_id=self.reason_code_catalog_version_id,
            status="published",
            version=self.version,
            revision=next_revision,
            applicability=self.applicability,
            rules=self.rules,
            criteria=self.criteria,
            limits=self.limits,
            fallback_action=self.fallback_action,
            changelog=(*self.changelog, changelog_entry),
            created_at=self.created_at,
            updated_at=now,
        )

    def create_new_version(
        self,
        *,
        policy_version_id: str,
        version: int,
        rules: tuple[PolicyRule, ...],
        criteria: tuple[PolicyCriterion, ...],
        limits: tuple[PolicyLimit, ...],
        applicability: PolicyApplicability,
        reason_code_catalog_id: str,
        reason_code_catalog_version_id: str,
        now: datetime,
        actor_subject_id: str,
        correlation_id: str,
        change_summary: str,
        owner_subject_id: str | None = None,
        product_type: str | None = None,
        fallback_action: PolicyFallbackAction | None = None,
    ) -> CreditPolicy:
        if self.status != "published":
            raise PolicyValidationError(
                "nova versão exige política publicada",
                code="policy_version_requires_published_source",
                field_path="status",
            )
        if policy_version_id == self.policy_version_id:
            raise PolicyValidationError(
                "nova versão exige identificador diferente",
                code="policy_version_id_must_change",
                field_path="policy_version_id",
            )
        changelog = (
            PolicyChangelogEntry.create(
                change_type="versioned",
                actor_subject_id=actor_subject_id,
                changed_at=now,
                change_summary=change_summary,
                correlation_id=correlation_id,
                previous_revision=None,
                resulting_revision=1,
            ),
        )
        return CreditPolicy.restore(
            policy_id=self.policy_id,
            policy_version_id=policy_version_id,
            tenant_id=self.tenant_id,
            owner_subject_id=owner_subject_id or self.owner_subject_id,
            product_type=product_type or self.product_type,
            reason_code_catalog_id=reason_code_catalog_id,
            reason_code_catalog_version_id=reason_code_catalog_version_id,
            status="draft",
            version=version,
            revision=1,
            applicability=applicability,
            rules=rules,
            criteria=criteria,
            limits=limits,
            fallback_action=fallback_action or self.fallback_action,
            changelog=changelog,
            created_at=now,
            updated_at=now,
        )


def _require_non_empty_tuple(value: tuple[object, ...], *, field_path: str) -> None:
    if not value:
        raise PolicyValidationError(
            "coleção obrigatória vazia",
            code="empty_policy_collection",
            field_path=field_path,
        )


def _require_items(
    value: tuple[object, ...],
    expected_type: type[object],
    *,
    field_path: str,
) -> None:
    if any(not isinstance(item, expected_type) for item in value):
        raise PolicyValidationError(
            "item de coleção inválido",
            code="invalid_policy_collection_item",
            field_path=field_path,
        )


def _validate_changelog_chain(
    changelog: tuple[PolicyChangelogEntry, ...],
    *,
    revision: int,
) -> None:
    previous_resulting_revision: int | None = None
    for expected_revision, entry in enumerate(changelog, start=1):
        if entry.previous_revision != previous_resulting_revision:
            _raise_inconsistent_changelog()
        if entry.resulting_revision != expected_revision:
            _raise_inconsistent_changelog()
        if entry.resulting_revision != 1 and entry.change_type not in {"updated", "published"}:
            _raise_inconsistent_changelog()
        if entry.resulting_revision == 1 and entry.change_type not in {"created", "versioned"}:
            _raise_inconsistent_changelog()
        previous_resulting_revision = entry.resulting_revision
    if previous_resulting_revision != revision:
        _raise_inconsistent_changelog()


def _raise_inconsistent_changelog() -> None:
    raise PolicyValidationError(
        "changelog inconsistente",
        code="inconsistent_policy_changelog",
        field_path="changelog",
    )


def _compute_governed_fingerprint(
    *,
    status: str,
    owner_subject_id: str,
    product_type: str,
    reason_code_catalog_id: str,
    reason_code_catalog_version_id: str,
    applicability: PolicyApplicability,
    rules: tuple[PolicyRule, ...],
    criteria: tuple[PolicyCriterion, ...],
    limits: tuple[PolicyLimit, ...],
    fallback_action: PolicyFallbackAction,
) -> str:
    governed_snapshot = repr(
        (
            status,
            owner_subject_id,
            product_type,
            reason_code_catalog_id,
            reason_code_catalog_version_id,
            applicability,
            rules,
            criteria,
            limits,
            fallback_action,
        )
    )
    return hashlib.sha256(governed_snapshot.encode("utf-8")).hexdigest()


def _validate_aware_utc_datetime(value: datetime, *, field_path: str) -> None:
    if value.tzinfo is None or value.utcoffset() is None:
        raise PolicyValidationError(
            "datetime deve conter timezone",
            code="naive_datetime",
            field_path=field_path,
        )
    if value.utcoffset() != UTC.utcoffset(value):
        raise PolicyValidationError(
            "datetime deve estar em UTC",
            code="non_utc_datetime",
            field_path=field_path,
        )
