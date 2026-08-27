from __future__ import annotations

from dataclasses import replace
from threading import RLock

from creditos_decision.domain.entities import ReasonCodeCatalog
from creditos_decision.domain.errors import PolicyConcurrencyError, PolicyValidationError


class InMemoryReasonCodeCatalogRepository:
    def __init__(self) -> None:
        self._catalogs: dict[tuple[str, str, str], ReasonCodeCatalog] = {}
        self._lock = RLock()

    def save(self, catalog: ReasonCodeCatalog) -> None:
        key = _key(catalog.tenant_id, catalog.catalog_id, catalog.catalog_version_id)
        with self._lock:
            if key in self._catalogs:
                raise PolicyValidationError(
                    "catálogo duplicado",
                    code="duplicate_reason_code_catalog",
                    field_path="catalog_id",
                )
            self._catalogs[key] = catalog

    def save_with_next_version(self, catalog: ReasonCodeCatalog) -> ReasonCodeCatalog:
        with self._lock:
            key = _key(catalog.tenant_id, catalog.catalog_id, catalog.catalog_version_id)
            if key in self._catalogs:
                raise PolicyValidationError(
                    "catálogo duplicado",
                    code="duplicate_reason_code_catalog",
                    field_path="catalog_id",
                )
            catalog_with_next_version = replace(
                catalog,
                version=self.next_version(
                    tenant_id=catalog.tenant_id,
                    catalog_id=catalog.catalog_id,
                ),
            )
            self._catalogs[key] = catalog_with_next_version
            return catalog_with_next_version

    def update(
        self,
        catalog: ReasonCodeCatalog,
        *,
        expected_revision: int | None = None,
    ) -> None:
        key = _key(catalog.tenant_id, catalog.catalog_id, catalog.catalog_version_id)
        with self._lock:
            existing = self._catalogs.get(key)
            if existing is None:
                raise PolicyValidationError(
                    "catálogo não encontrado",
                    code="reason_code_catalog_not_found",
                    field_path="catalog_id",
                )
            if expected_revision is not None and existing.revision != expected_revision:
                raise PolicyConcurrencyError(
                    "revisão concorrente",
                    field_path="revision",
                    details={
                        "expected_revision": expected_revision,
                        "actual_revision": existing.revision,
                    },
                )
            self._catalogs[key] = catalog

    def delete(self, catalog: ReasonCodeCatalog) -> None:
        key = _key(catalog.tenant_id, catalog.catalog_id, catalog.catalog_version_id)
        with self._lock:
            self._catalogs.pop(key, None)

    def delete_if_current(
        self,
        catalog: ReasonCodeCatalog,
        *,
        expected_revision: int,
    ) -> bool:
        key = _key(catalog.tenant_id, catalog.catalog_id, catalog.catalog_version_id)
        with self._lock:
            existing = self._catalogs.get(key)
            if existing is None or existing.revision != expected_revision:
                return False
            self._catalogs.pop(key, None)
            return True

    def restore(self, catalog: ReasonCodeCatalog) -> None:
        key = _key(catalog.tenant_id, catalog.catalog_id, catalog.catalog_version_id)
        with self._lock:
            self._catalogs[key] = catalog

    def restore_if_current(
        self,
        catalog: ReasonCodeCatalog,
        *,
        expected_revision: int,
    ) -> bool:
        key = _key(catalog.tenant_id, catalog.catalog_id, catalog.catalog_version_id)
        with self._lock:
            existing = self._catalogs.get(key)
            if existing is None or existing.revision != expected_revision:
                return False
            self._catalogs[key] = catalog
            return True

    def next_version(self, *, tenant_id: str, catalog_id: str) -> int:
        with self._lock:
            tenant_catalog_versions = (
                catalog.version
                for key, catalog in self._catalogs.items()
                if key[0] == tenant_id and key[1] == catalog_id
            )
            return max(tenant_catalog_versions, default=0) + 1

    def get(
        self,
        *,
        tenant_id: str,
        catalog_id: str,
        catalog_version_id: str,
    ) -> ReasonCodeCatalog | None:
        with self._lock:
            return self._catalogs.get(_key(tenant_id, catalog_id, catalog_version_id))

    def list_by_tenant(self, *, tenant_id: str) -> tuple[ReasonCodeCatalog, ...]:
        with self._lock:
            return tuple(catalog for key, catalog in self._catalogs.items() if key[0] == tenant_id)


def _key(tenant_id: str, catalog_id: str, catalog_version_id: str) -> tuple[str, str, str]:
    return (tenant_id, catalog_id, catalog_version_id)
