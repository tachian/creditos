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
            output_items=(
                {
                    "item_ref": "finding_missing_data_review",
                    "item_type": "missing_data",
                    "severity": "medium",
                    "reason_ref": "reason_missing_data_review",
                    "confidence": 80,
                },
                {
                    "item_ref": "limitation_mock_executor",
                    "item_type": "limitation",
                    "severity": "low",
                    "reason_ref": "reason_mock_executor",
                },
            ),
        )
