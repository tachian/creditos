from __future__ import annotations

from creditos_automated_review.application.ports import (
    ConsultativeReviewExecutionInput,
    ConsultativeReviewOutput,
)


class MockConsultativeReviewExecutor:
    def __init__(self) -> None:
        self.calls: list[ConsultativeReviewExecutionInput] = []

    def execute(self, command: ConsultativeReviewExecutionInput) -> ConsultativeReviewOutput:
        self.calls.append(command)
        return ConsultativeReviewOutput(
            status="completed",
            finding_refs=("finding_missing_data_review",),
            limitation_refs=("limitation_mock_executor",),
        )
