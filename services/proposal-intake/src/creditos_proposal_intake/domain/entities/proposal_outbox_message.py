from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime
from types import MappingProxyType
from typing import Any, Literal

ProposalOutboxStatus = Literal["pending"]


@dataclass(frozen=True, slots=True)
class ProposalOutboxMessage:
    tenant_id: str
    message_id: str
    aggregate_type: str
    aggregate_id: str
    event_type: str
    subject: str
    payload: MappingProxyType[str, Any]
    status: ProposalOutboxStatus
    created_at: datetime
    deduplication_key: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "payload", _freeze_value(self.payload))


def _freeze_value(value: Any) -> Any:
    if isinstance(value, Mapping):
        return MappingProxyType({key: _freeze_value(item) for key, item in value.items()})
    if isinstance(value, Sequence) and not isinstance(value, str | bytes | bytearray):
        return tuple(_freeze_value(item) for item in value)
    return value
