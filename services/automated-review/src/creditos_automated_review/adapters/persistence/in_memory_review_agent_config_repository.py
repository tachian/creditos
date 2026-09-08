from __future__ import annotations

from threading import RLock

from creditos_automated_review.domain.entities import ReviewAgentConfiguration
from creditos_automated_review.domain.errors import (
    AutomatedReviewConfigNotFoundError,
    AutomatedReviewConflictError,
)


class InMemoryReviewAgentConfigRepository:
    def __init__(self) -> None:
        self._configs: dict[tuple[str, str, str], ReviewAgentConfiguration] = {}
        self._lock = RLock()

    def create(self, config: ReviewAgentConfiguration) -> None:
        with self._lock:
            key = self._key(config)
            if key in self._configs:
                raise AutomatedReviewConflictError(
                    "versão de configuração já existe",
                    code="automated_review_config_version_exists",
                    field_path="review_agent_config_version_id",
                )
            self._configs[key] = config

    def save_existing(
        self,
        config: ReviewAgentConfiguration,
        *,
        expected_revision: int,
        expected_status: str,
    ) -> None:
        with self._lock:
            key = self._key(config)
            current = self._configs.get(key)
            if current is None:
                raise AutomatedReviewConfigNotFoundError()
            if current.revision != expected_revision or current.status != expected_status:
                raise AutomatedReviewConflictError(
                    "configuração alterada concorrentemente",
                    code="automated_review_config_revision_conflict",
                    field_path="revision",
                )
            self._configs[key] = config

    def get(
        self,
        *,
        tenant_id: str,
        review_agent_config_id: str,
        review_agent_config_version_id: str,
    ) -> ReviewAgentConfiguration | None:
        with self._lock:
            return self._configs.get(
                (tenant_id, review_agent_config_id, review_agent_config_version_id)
            )

    def list_published_by_scope(
        self,
        *,
        tenant_id: str,
        product_type: str,
        channel: str,
        review_purpose: str,
    ) -> tuple[ReviewAgentConfiguration, ...]:
        with self._lock:
            return tuple(
                config
                for config in self._configs.values()
                if config.tenant_id == tenant_id
                and config.product_type == product_type
                and channel in config.scope.channels
                and review_purpose in config.scope.review_purposes
                and config.is_referenceable_for_review
            )

    def _key(self, config: ReviewAgentConfiguration) -> tuple[str, str, str]:
        return (
            config.tenant_id,
            config.review_agent_config_id,
            config.review_agent_config_version_id,
        )
