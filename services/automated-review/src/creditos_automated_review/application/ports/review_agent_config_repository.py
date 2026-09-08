from __future__ import annotations

from collections.abc import Callable
from typing import Protocol

from creditos_automated_review.domain.entities import ReviewAgentConfiguration


class ReviewAgentConfigRepository(Protocol):
    def create(
        self,
        config: ReviewAgentConfiguration,
        *,
        before_commit: Callable[[], None] | None = None,
    ) -> None: ...

    def save_existing(
        self,
        config: ReviewAgentConfiguration,
        *,
        expected_revision: int,
        expected_status: str,
        before_commit: Callable[[], None] | None = None,
    ) -> None: ...

    def get(
        self,
        *,
        tenant_id: str,
        review_agent_config_id: str,
        review_agent_config_version_id: str,
    ) -> ReviewAgentConfiguration | None: ...

    def list_published_by_scope(
        self,
        *,
        tenant_id: str,
        product_type: str,
        channel: str,
        review_purpose: str,
    ) -> tuple[ReviewAgentConfiguration, ...]: ...
