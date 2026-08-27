from __future__ import annotations

import hashlib
from dataclasses import dataclass, replace
from datetime import UTC, datetime

from creditos_decision.domain.errors import (
    PolicyImmutableError,
    PolicyValidationError,
    ReasonCodeCatalogVersioningError,
)
from creditos_decision.domain.value_objects.policy import (
    _validate_safe_text,
    parse_product_type,
    validate_correlation_id,
    validate_subject_id,
    validate_tenant_id,
)
from creditos_decision.domain.value_objects.reason_codes import (
    ExplainableFactor,
    ReasonCode,
    parse_reason_code_catalog_change_type,
    parse_reason_code_catalog_status,
    validate_reason_code_catalog_id,
    validate_reason_code_catalog_version_id,
)


@dataclass(frozen=True, slots=True)
class ReasonCodeCatalogChangelogEntry:
    change_type: str
    actor_subject_id: str
    changed_at: datetime
    change_summary: str
    correlation_id: str
    previous_revision: int | None
    resulting_revision: int

    def __post_init__(self) -> None:
        if self.previous_revision is not None and self.previous_revision < 1:
            raise PolicyValidationError(
                "revisão anterior inválida",
                code="invalid_catalog_previous_revision",
                field_path="changelog.previous_revision",
            )
        if self.resulting_revision < 1:
            raise PolicyValidationError(
                "revisão resultante inválida",
                code="invalid_catalog_resulting_revision",
                field_path="changelog.resulting_revision",
            )
        _validate_aware_utc_datetime(self.changed_at, field_path="changelog.changed_at")
        object.__setattr__(
            self,
            "change_type",
            parse_reason_code_catalog_change_type(self.change_type),
        )
        object.__setattr__(
            self,
            "actor_subject_id",
            validate_subject_id(
                self.actor_subject_id,
                field_path="changelog.actor_subject_id",
            ),
        )
        object.__setattr__(self, "correlation_id", validate_correlation_id(self.correlation_id))
        object.__setattr__(
            self,
            "change_summary",
            _validate_safe_text(
                self.change_summary,
                field_path="changelog.change_summary",
            ),
        )

    @classmethod
    def create(
        cls,
        *,
        change_type: str,
        actor_subject_id: str,
        changed_at: datetime,
        change_summary: str,
        correlation_id: str,
        previous_revision: int | None,
        resulting_revision: int,
    ) -> ReasonCodeCatalogChangelogEntry:
        return cls(
            change_type=change_type,
            actor_subject_id=actor_subject_id,
            changed_at=changed_at,
            change_summary=change_summary,
            correlation_id=correlation_id,
            previous_revision=previous_revision,
            resulting_revision=resulting_revision,
        )


@dataclass(frozen=True, slots=True)
class ReasonCodeCatalog:
    catalog_id: str
    catalog_version_id: str
    tenant_id: str
    owner_subject_id: str
    product_type: str
    status: str
    version: int
    revision: int
    reason_codes: tuple[ReasonCode, ...]
    explainable_factors: tuple[ExplainableFactor, ...]
    changelog: tuple[ReasonCodeCatalogChangelogEntry, ...]
    created_at: datetime
    updated_at: datetime
    _governed_fingerprint: str = ""

    def __post_init__(self) -> None:
        if self.version < 1:
            raise PolicyValidationError(
                "versão inválida",
                code="invalid_reason_code_catalog_version",
                field_path="version",
            )
        if self.revision < 1:
            raise PolicyValidationError(
                "revisão inválida",
                code="invalid_reason_code_catalog_revision",
                field_path="revision",
            )
        reason_codes = tuple(self.reason_codes)
        explainable_factors = tuple(self.explainable_factors)
        changelog = tuple(self.changelog)
        _require_non_empty_tuple(reason_codes, field_path="reason_codes")
        _require_non_empty_tuple(explainable_factors, field_path="explainable_factors")
        _require_non_empty_tuple(changelog, field_path="changelog")
        _require_items(reason_codes, ReasonCode, field_path="reason_codes")
        _require_items(
            explainable_factors,
            ExplainableFactor,
            field_path="explainable_factors",
        )
        _require_items(
            changelog,
            ReasonCodeCatalogChangelogEntry,
            field_path="changelog",
        )
        _validate_unique_reason_codes(reason_codes)
        _validate_unique_explainable_factors(explainable_factors)
        known_factor_ids = {factor.factor_id for factor in explainable_factors}
        for reason_code in reason_codes:
            reason_code.validate_factor_refs(known_factor_ids=known_factor_ids)
        _validate_changelog_chain(changelog, revision=self.revision)
        _validate_aware_utc_datetime(self.created_at, field_path="created_at")
        _validate_aware_utc_datetime(self.updated_at, field_path="updated_at")
        parsed_status = parse_reason_code_catalog_status(self.status)
        parsed_owner_subject_id = validate_subject_id(
            self.owner_subject_id,
            field_path="owner_subject_id",
        )
        parsed_product_type = parse_product_type(self.product_type)
        fingerprint = _compute_governed_fingerprint(
            catalog_id=validate_reason_code_catalog_id(self.catalog_id),
            catalog_version_id=validate_reason_code_catalog_version_id(self.catalog_version_id),
            tenant_id=validate_tenant_id(self.tenant_id),
            status=parsed_status,
            version=self.version,
            revision=self.revision,
            owner_subject_id=parsed_owner_subject_id,
            product_type=parsed_product_type,
            reason_codes=reason_codes,
            explainable_factors=explainable_factors,
            changelog=changelog,
            created_at=self.created_at,
            updated_at=self.updated_at,
        )
        if parsed_status != "draft" and (
            not self._governed_fingerprint or self._governed_fingerprint != fingerprint
        ):
            raise PolicyImmutableError("catálogo não pode ser alterado")
        object.__setattr__(self, "catalog_id", validate_reason_code_catalog_id(self.catalog_id))
        object.__setattr__(
            self,
            "catalog_version_id",
            validate_reason_code_catalog_version_id(self.catalog_version_id),
        )
        object.__setattr__(self, "tenant_id", validate_tenant_id(self.tenant_id))
        object.__setattr__(self, "owner_subject_id", parsed_owner_subject_id)
        object.__setattr__(self, "product_type", parsed_product_type)
        object.__setattr__(self, "status", parsed_status)
        object.__setattr__(self, "reason_codes", reason_codes)
        object.__setattr__(self, "explainable_factors", explainable_factors)
        object.__setattr__(self, "changelog", changelog)
        object.__setattr__(self, "_governed_fingerprint", fingerprint)

    @classmethod
    def create_draft(
        cls,
        *,
        catalog_id: str,
        catalog_version_id: str,
        tenant_id: str,
        owner_subject_id: str,
        product_type: str,
        reason_codes: tuple[ReasonCode, ...],
        explainable_factors: tuple[ExplainableFactor, ...],
        now: datetime,
        actor_subject_id: str,
        correlation_id: str,
        change_summary: str,
        version: int = 1,
    ) -> ReasonCodeCatalog:
        revision = 1
        changelog = (
            ReasonCodeCatalogChangelogEntry.create(
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
            catalog_id=catalog_id,
            catalog_version_id=catalog_version_id,
            tenant_id=tenant_id,
            owner_subject_id=owner_subject_id,
            product_type=product_type,
            status="draft",
            version=version,
            revision=revision,
            reason_codes=reason_codes,
            explainable_factors=explainable_factors,
            changelog=changelog,
            created_at=now,
            updated_at=now,
        )

    @classmethod
    def restore(
        cls,
        *,
        catalog_id: str,
        catalog_version_id: str,
        tenant_id: str,
        owner_subject_id: str,
        product_type: str,
        status: str,
        version: int,
        revision: int,
        reason_codes: tuple[ReasonCode, ...],
        explainable_factors: tuple[ExplainableFactor, ...],
        changelog: tuple[ReasonCodeCatalogChangelogEntry, ...],
        created_at: datetime,
        updated_at: datetime,
        governed_fingerprint: str = "",
    ) -> ReasonCodeCatalog:
        parsed_status = parse_reason_code_catalog_status(status)
        parsed_owner_subject_id = validate_subject_id(
            owner_subject_id,
            field_path="owner_subject_id",
        )
        parsed_product_type = parse_product_type(product_type)
        reason_codes = tuple(reason_codes)
        explainable_factors = tuple(explainable_factors)
        return cls(
            catalog_id=validate_reason_code_catalog_id(catalog_id),
            catalog_version_id=validate_reason_code_catalog_version_id(catalog_version_id),
            tenant_id=validate_tenant_id(tenant_id),
            owner_subject_id=parsed_owner_subject_id,
            product_type=parsed_product_type,
            status=parsed_status,
            version=version,
            revision=revision,
            reason_codes=reason_codes,
            explainable_factors=explainable_factors,
            changelog=tuple(changelog),
            created_at=created_at,
            updated_at=updated_at,
            _governed_fingerprint=governed_fingerprint,
        )

    @property
    def is_referenceable_for_policy_draft(self) -> bool:
        return self.status in {"draft", "published"}

    @property
    def is_referenceable_for_final_decisions(self) -> bool:
        return self.status == "published"

    def update_draft(
        self,
        *,
        reason_codes: tuple[ReasonCode, ...],
        explainable_factors: tuple[ExplainableFactor, ...],
        now: datetime,
        actor_subject_id: str,
        correlation_id: str,
        change_summary: str,
        owner_subject_id: str | None = None,
        product_type: str | None = None,
    ) -> ReasonCodeCatalog:
        if self.status != "draft":
            raise PolicyImmutableError("catálogo não pode ser alterado")
        if product_type is not None and product_type != self.product_type:
            raise ReasonCodeCatalogVersioningError("mudança incompatível exige nova versão")
        if _has_incompatible_change(
            current_reason_codes=self.reason_codes,
            next_reason_codes=tuple(reason_codes),
            current_factors=self.explainable_factors,
            next_factors=tuple(explainable_factors),
        ):
            raise ReasonCodeCatalogVersioningError("mudança incompatível exige nova versão")
        return self._next_revision(
            reason_codes=reason_codes,
            explainable_factors=explainable_factors,
            now=now,
            actor_subject_id=actor_subject_id,
            correlation_id=correlation_id,
            change_summary=change_summary,
            change_type="updated",
            owner_subject_id=owner_subject_id,
            product_type=product_type,
            status="draft",
        )

    def publish(
        self,
        *,
        now: datetime,
        actor_subject_id: str,
        correlation_id: str,
        change_summary: str,
    ) -> ReasonCodeCatalog:
        if self.status != "draft":
            raise PolicyImmutableError("catálogo não pode ser alterado")
        return self._next_revision(
            reason_codes=self.reason_codes,
            explainable_factors=self.explainable_factors,
            now=now,
            actor_subject_id=actor_subject_id,
            correlation_id=correlation_id,
            change_summary=change_summary,
            change_type="published",
            status="published",
        )

    def create_new_version(
        self,
        *,
        catalog_version_id: str,
        reason_codes: tuple[ReasonCode, ...],
        explainable_factors: tuple[ExplainableFactor, ...],
        now: datetime,
        actor_subject_id: str,
        correlation_id: str,
        change_summary: str,
        owner_subject_id: str | None = None,
        product_type: str | None = None,
        version: int | None = None,
    ) -> ReasonCodeCatalog:
        if not _has_incompatible_change(
            current_reason_codes=self.reason_codes,
            next_reason_codes=tuple(reason_codes),
            current_factors=self.explainable_factors,
            next_factors=tuple(explainable_factors),
        ):
            raise ReasonCodeCatalogVersioningError(
                "nova versão deve representar mudança incompatível",
                code="reason_code_catalog_version_without_incompatible_change",
            )
        return ReasonCodeCatalog.create_draft(
            catalog_id=self.catalog_id,
            catalog_version_id=catalog_version_id,
            tenant_id=self.tenant_id,
            owner_subject_id=owner_subject_id or self.owner_subject_id,
            product_type=product_type or self.product_type,
            reason_codes=reason_codes,
            explainable_factors=explainable_factors,
            now=now,
            actor_subject_id=actor_subject_id,
            correlation_id=correlation_id,
            change_summary=change_summary,
            version=version or self.version + 1,
        )

    def validate_policy_rules(self, rules: tuple[object, ...]) -> None:
        if not self.is_referenceable_for_policy_draft:
            raise PolicyValidationError(
                "catálogo de reason codes não referenciável",
                code="reason_code_catalog_not_referenceable",
                field_path="reason_code_catalog_version_id",
            )
        by_code = {reason_code.code: reason_code for reason_code in self.reason_codes}
        for rule_index, rule in enumerate(rules):
            outcome = getattr(rule, "outcome", None)
            reason_code_refs = getattr(rule, "reason_code_refs", ())
            for reason_code_ref in reason_code_refs:
                reason_code = by_code.get(reason_code_ref)
                if reason_code is None:
                    raise PolicyValidationError(
                        "reason code inexistente",
                        code="unknown_reason_code",
                        field_path=f"rules[{rule_index}].reason_code_refs",
                    )
                if reason_code.status != "active":
                    raise PolicyValidationError(
                        "reason code não ativo",
                        code="inactive_reason_code",
                        field_path=f"rules[{rule_index}].reason_code_refs",
                    )
                if reason_code.outcome != outcome:
                    raise PolicyValidationError(
                        "reason code incompatível",
                        code="reason_code_outcome_mismatch",
                        field_path=f"rules[{rule_index}].reason_code_refs",
                    )

    def _next_revision(
        self,
        *,
        reason_codes: tuple[ReasonCode, ...],
        explainable_factors: tuple[ExplainableFactor, ...],
        now: datetime,
        actor_subject_id: str,
        correlation_id: str,
        change_summary: str,
        change_type: str,
        status: str,
        owner_subject_id: str | None = None,
        product_type: str | None = None,
    ) -> ReasonCodeCatalog:
        _validate_aware_utc_datetime(now, field_path="updated_at")
        next_revision = self.revision + 1
        changelog_entry = ReasonCodeCatalogChangelogEntry.create(
            change_type=change_type,
            actor_subject_id=actor_subject_id,
            changed_at=now,
            change_summary=change_summary,
            correlation_id=correlation_id,
            previous_revision=self.revision,
            resulting_revision=next_revision,
        )
        parsed_owner_subject_id = owner_subject_id or self.owner_subject_id
        parsed_product_type = product_type or self.product_type
        next_reason_codes = tuple(reason_codes)
        next_explainable_factors = tuple(explainable_factors)
        next_changelog = (*self.changelog, changelog_entry)
        next_updated_at = now
        governed_fingerprint = _compute_governed_fingerprint(
            catalog_id=self.catalog_id,
            catalog_version_id=self.catalog_version_id,
            tenant_id=self.tenant_id,
            status=status,
            version=self.version,
            revision=next_revision,
            owner_subject_id=parsed_owner_subject_id,
            product_type=parsed_product_type,
            reason_codes=next_reason_codes,
            explainable_factors=next_explainable_factors,
            changelog=next_changelog,
            created_at=self.created_at,
            updated_at=next_updated_at,
        )
        return replace(
            self,
            revision=next_revision,
            status=status,
            owner_subject_id=parsed_owner_subject_id,
            product_type=parsed_product_type,
            reason_codes=next_reason_codes,
            explainable_factors=next_explainable_factors,
            changelog=next_changelog,
            updated_at=next_updated_at,
            _governed_fingerprint=governed_fingerprint,
        )

    @property
    def governed_fingerprint(self) -> str:
        return self._governed_fingerprint


def _require_non_empty_tuple(value: tuple[object, ...], *, field_path: str) -> None:
    if not value:
        raise PolicyValidationError(
            "coleção obrigatória vazia",
            code="empty_reason_code_catalog_collection",
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
            code="invalid_reason_code_catalog_collection_item",
            field_path=field_path,
        )


def _validate_unique_reason_codes(reason_codes: tuple[ReasonCode, ...]) -> None:
    reason_code_ids = [reason_code.reason_code_id for reason_code in reason_codes]
    codes = [reason_code.code for reason_code in reason_codes]
    if len(set(reason_code_ids)) != len(reason_code_ids) or len(set(codes)) != len(codes):
        raise PolicyValidationError(
            "reason code duplicado",
            code="duplicate_reason_code",
            field_path="reason_codes",
        )


def _validate_unique_explainable_factors(
    explainable_factors: tuple[ExplainableFactor, ...],
) -> None:
    factor_ids = [factor.factor_id for factor in explainable_factors]
    fields = [factor.field for factor in explainable_factors]
    if len(set(factor_ids)) != len(factor_ids) or len(set(fields)) != len(fields):
        raise PolicyValidationError(
            "fator explicável duplicado",
            code="duplicate_explainable_factor",
            field_path="explainable_factors",
        )


def _has_incompatible_change(
    *,
    current_reason_codes: tuple[ReasonCode, ...],
    next_reason_codes: tuple[ReasonCode, ...],
    current_factors: tuple[ExplainableFactor, ...],
    next_factors: tuple[ExplainableFactor, ...],
) -> bool:
    current_by_code = {reason_code.code: reason_code for reason_code in current_reason_codes}
    next_by_code = {reason_code.code: reason_code for reason_code in next_reason_codes}
    if not set(current_by_code).issubset(set(next_by_code)):
        return True
    for code, current_reason_code in current_by_code.items():
        if not current_reason_code.is_semantically_compatible_with(next_by_code[code]):
            return True
    current_factors_by_id = {factor.factor_id: factor for factor in current_factors}
    next_factors_by_id = {factor.factor_id: factor for factor in next_factors}
    if not set(current_factors_by_id).issubset(set(next_factors_by_id)):
        return True
    for factor_id, current_factor in current_factors_by_id.items():
        next_factor = next_factors_by_id[factor_id]
        if (
            current_factor.field != next_factor.field
            or current_factor.external_description != next_factor.external_description
            or current_factor.required != next_factor.required
            or current_factor.audience != next_factor.audience
        ):
            return True
    return False


def _validate_changelog_chain(
    changelog: tuple[ReasonCodeCatalogChangelogEntry, ...],
    *,
    revision: int,
) -> None:
    previous_resulting_revision: int | None = None
    for expected_revision, entry in enumerate(changelog, start=1):
        if entry.previous_revision != previous_resulting_revision:
            _raise_inconsistent_changelog()
        if entry.resulting_revision != expected_revision:
            _raise_inconsistent_changelog()
        if entry.resulting_revision == 1 and entry.change_type != "created":
            _raise_inconsistent_changelog()
        if entry.resulting_revision != 1 and entry.change_type not in {
            "updated",
            "published",
            "versioned",
        }:
            _raise_inconsistent_changelog()
        previous_resulting_revision = entry.resulting_revision
    if previous_resulting_revision != revision:
        _raise_inconsistent_changelog()


def _raise_inconsistent_changelog() -> None:
    raise PolicyValidationError(
        "changelog inconsistente",
        code="inconsistent_reason_code_catalog_changelog",
        field_path="changelog",
    )


def _compute_governed_fingerprint(
    *,
    catalog_id: str,
    catalog_version_id: str,
    tenant_id: str,
    status: str,
    version: int,
    revision: int,
    owner_subject_id: str,
    product_type: str,
    reason_codes: tuple[ReasonCode, ...],
    explainable_factors: tuple[ExplainableFactor, ...],
    changelog: tuple[ReasonCodeCatalogChangelogEntry, ...],
    created_at: datetime,
    updated_at: datetime,
) -> str:
    governed_snapshot = repr(
        (
            catalog_id,
            catalog_version_id,
            tenant_id,
            status,
            version,
            revision,
            owner_subject_id,
            product_type,
            reason_codes,
            explainable_factors,
            changelog,
            created_at,
            updated_at,
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
