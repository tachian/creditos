from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from types import MappingProxyType
from typing import Any


@dataclass(frozen=True, slots=True)
class CanonicalProposal:
    tenant_id: str
    idempotency_key: str
    schema_version: str
    external_proposal_id: str
    person_type: str
    product_type: str
    channel: str
    borrower_document_type: str
    requested_amount_cents: int
    requested_terms: MappingProxyType[str, Any]
    product_data: MappingProxyType[str, Any]
    participants: tuple[MappingProxyType[str, Any], ...] = ()
    risk_context: MappingProxyType[str, Any] = field(default_factory=lambda: MappingProxyType({}))
    decision_options: MappingProxyType[str, Any] = field(
        default_factory=lambda: MappingProxyType({})
    )
    provided_data_discarded: bool = False
    consents_discarded: bool = False
    callback_profile_ref: str | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "requested_terms", _freeze_value(self.requested_terms))
        object.__setattr__(self, "product_data", _freeze_value(self.product_data))
        object.__setattr__(
            self,
            "participants",
            tuple(_freeze_value(participant) for participant in self.participants),
        )
        object.__setattr__(self, "risk_context", _freeze_value(self.risk_context))
        object.__setattr__(self, "decision_options", _freeze_value(self.decision_options))


def _freeze_value(value: Any) -> Any:
    if isinstance(value, Mapping):
        return _freeze_mapping(value)
    if isinstance(value, Sequence) and not isinstance(value, str | bytes | bytearray):
        return tuple(_freeze_value(item) for item in value)
    return value


def _freeze_mapping(value: Mapping[str, Any]) -> MappingProxyType[str, Any]:
    frozen: dict[str, Any] = {}
    for key, item in value.items():
        frozen[key] = _freeze_value(item)
    return MappingProxyType(frozen)
