from __future__ import annotations

from collections.abc import Callable
from threading import RLock

from creditos_automated_review.domain.entities import AutomatedReviewExecutionResult
from creditos_automated_review.domain.errors import AutomatedReviewConflictError


class InMemoryReviewExecutionRepository:
    def __init__(self) -> None:
        self._executions: dict[tuple[str, str], AutomatedReviewExecutionResult] = {}
        self._lock = RLock()

    def create(
        self,
        execution: AutomatedReviewExecutionResult,
        *,
        before_commit: Callable[[], None] | None = None,
    ) -> None:
        with self._lock:
            key = (execution.tenant_id, execution.execution_id)
            if key in self._executions:
                raise AutomatedReviewConflictError(
                    "execução consultiva já existe",
                    code="automated_review_execution_exists",
                    field_path="execution_id",
                )
            if before_commit is not None:
                before_commit()
            self._executions[key] = execution

    def get(
        self,
        *,
        tenant_id: str,
        execution_id: str,
    ) -> AutomatedReviewExecutionResult | None:
        with self._lock:
            return self._executions.get((tenant_id, execution_id))
