from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import UTC, datetime

from creditos_decision.domain.errors import PolicyImmutableError, PolicyValidationError
from creditos_decision.domain.value_objects.policy import (
    PolicyApplicability,
    PolicyChangelogEntry,
    PolicyCriterion,
    PolicyLimit,
    PolicyRule,
    parse_policy_status,
    parse_product_type,
    validate_policy_id,
    validate_policy_version_id,
    validate_subject_id,
    validate_tenant_id,
)


@dataclass(frozen=True, slots=True)
class CreditPolicy:
    policy_id: str
    policy_version_id: str
    tenant_id: str
    owner_subject_id: str
    product_type: str
    status: str
    version: int
    revision: int
    applicability: PolicyApplicability
    rules: tuple[PolicyRule, ...]
    criteria: tuple[PolicyCriterion, ...]
    limits: tuple[PolicyLimit, ...]
    changelog: tuple[PolicyChangelogEntry, ...]
    created_at: datetime
    updated_at: datetime

    @classmethod
    def create_draft(
        cls,
        *,
        policy_id: str,
        policy_version_id: str,
        tenant_id: str,
        owner_subject_id: str,
        product_type: str,
        applicability: PolicyApplicability,
        rules: tuple[PolicyRule, ...],
        criteria: tuple[PolicyCriterion, ...],
        limits: tuple[PolicyLimit, ...],
        now: datetime,
        actor_subject_id: str,
        correlation_id: str,
        change_summary: str,
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
            status="draft",
            version=1,
            revision=revision,
            applicability=applicability,
            rules=rules,
            criteria=criteria,
            limits=limits,
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
        return cls(
            policy_id=validate_policy_id(policy_id),
            policy_version_id=validate_policy_version_id(policy_version_id),
            tenant_id=validate_tenant_id(tenant_id),
            owner_subject_id=validate_subject_id(
                owner_subject_id,
                field_path="owner_subject_id",
            ),
            product_type=parse_product_type(product_type),
            status=parse_policy_status(status),
            version=version,
            revision=revision,
            applicability=applicability,
            rules=tuple(rules),
            criteria=tuple(criteria),
            limits=tuple(limits),
            changelog=tuple(changelog),
            created_at=created_at,
            updated_at=updated_at,
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
            applicability=applicability,
            rules=tuple(rules),
            criteria=tuple(criteria),
            limits=tuple(limits),
            changelog=(*self.changelog, changelog_entry),
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
        if entry.resulting_revision != 1 and entry.change_type != "updated":
            _raise_inconsistent_changelog()
        if entry.resulting_revision == 1 and entry.change_type != "created":
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
