from __future__ import annotations

from creditos_proposal_intake.domain.errors import ProposalValidationError

MAX_MONEY_CENTS = 1_000_000_000_000


def require_money_cents(
    value: object,
    *,
    field_path: str,
    allow_zero: bool = False,
) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise ProposalValidationError(
            "valor monetário deve ser inteiro em centavos",
            field_path=field_path,
            details={"expected": "integer_cents"},
        )
    minimum = 0 if allow_zero else 1
    if value < minimum or value > MAX_MONEY_CENTS:
        raise ProposalValidationError(
            "valor monetário fora dos limites operacionais",
            field_path=field_path,
            details={"minimum": minimum, "maximum": MAX_MONEY_CENTS},
        )
    return value
