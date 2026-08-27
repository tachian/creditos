from __future__ import annotations

from typing import Protocol

from creditos_decision.domain.entities import ReasonCodeCatalog


class ReasonCodeCatalogRepository(Protocol):
    def save(self, catalog: ReasonCodeCatalog) -> None: ...

    def save_with_next_version(self, catalog: ReasonCodeCatalog) -> ReasonCodeCatalog: ...

    def update(
        self,
        catalog: ReasonCodeCatalog,
        *,
        expected_revision: int | None = None,
    ) -> None: ...

    def delete(self, catalog: ReasonCodeCatalog) -> None: ...

    def delete_if_current(
        self,
        catalog: ReasonCodeCatalog,
        *,
        expected_revision: int,
    ) -> bool: ...

    def restore(self, catalog: ReasonCodeCatalog) -> None: ...

    def restore_if_current(
        self,
        catalog: ReasonCodeCatalog,
        *,
        expected_revision: int,
    ) -> bool: ...

    def next_version(self, *, tenant_id: str, catalog_id: str) -> int: ...

    def get(
        self,
        *,
        tenant_id: str,
        catalog_id: str,
        catalog_version_id: str,
    ) -> ReasonCodeCatalog | None: ...

    def list_by_tenant(self, *, tenant_id: str) -> tuple[ReasonCodeCatalog, ...]: ...
