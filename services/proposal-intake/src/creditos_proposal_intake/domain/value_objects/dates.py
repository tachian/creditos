from __future__ import annotations

import re
from datetime import UTC, date, datetime

from creditos_proposal_intake.domain.errors import ProposalValidationError

_ISO_DATE_PATTERN = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def require_iso_date(value: object, *, field_path: str) -> str:
    if not isinstance(value, str) or _ISO_DATE_PATTERN.fullmatch(value) is None:
        raise ProposalValidationError("data inválida", field_path=field_path)
    try:
        parsed = date.fromisoformat(value)
    except ValueError as error:
        raise ProposalValidationError("data inválida", field_path=field_path) from error
    return parsed.isoformat()


def normalize_iso_datetime(value: object, *, field_path: str) -> str:
    if not isinstance(value, str):
        raise ProposalValidationError("data/hora inválida", field_path=field_path)
    normalized_input = value.replace("Z", "+00:00")
    try:
        parsed = datetime.fromisoformat(normalized_input)
    except ValueError as error:
        raise ProposalValidationError("data/hora inválida", field_path=field_path) from error
    if parsed.tzinfo is None:
        raise ProposalValidationError("timezone obrigatório", field_path=field_path)
    return parsed.astimezone(UTC).isoformat()
