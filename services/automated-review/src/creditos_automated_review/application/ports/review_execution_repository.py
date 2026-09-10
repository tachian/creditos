from __future__ import annotations

from collections.abc import Callable
from typing import Protocol

from creditos_automated_review.domain.entities import AutomatedReviewExecutionResult


class ReviewExecutionRepository(Protocol):
    def create(
        self,
        execution: AutomatedReviewExecutionResult,
        *,
        before_commit: Callable[[], None] | None = None,
    ) -> None: ...

    def get(
        self,
        *,
        tenant_id: str,
        execution_id: str,
    ) -> AutomatedReviewExecutionResult | None: ...
