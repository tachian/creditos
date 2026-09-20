from __future__ import annotations

import hashlib
import json
from collections.abc import Iterable, Mapping
from dataclasses import replace
from datetime import UTC, datetime
from typing import Any

from creditos_audit_evidence.domain.entities.audit_event import AuditEvent
from creditos_audit_evidence.domain.value_objects.audit_integrity import (
    CANONICALIZATION_VERSION,
    GENESIS_PREVIOUS_HASH,
    HASH_ALGORITHM,
)


def canonicalize_audit_event(event: AuditEvent, *, previous_hash: str | None = None) -> str:
    payload = _canonical_event_payload(event, previous_hash=previous_hash or event.previous_hash)
    return json.dumps(payload, ensure_ascii=False, separators=(",", ":"), sort_keys=True)


def calculate_audit_event_hash(event: AuditEvent, *, previous_hash: str | None = None) -> str:
    canonical_payload = canonicalize_audit_event(event, previous_hash=previous_hash)
    return hashlib.sha256(canonical_payload.encode("utf-8")).hexdigest()


def apply_audit_event_integrity(event: AuditEvent, *, previous_hash: str) -> AuditEvent:
    current_hash = calculate_audit_event_hash(event, previous_hash=previous_hash)
    return replace(
        event,
        integrity_scope="tenant",
        integrity_chain_id=event.tenant_id,
        previous_hash=previous_hash,
        current_hash=current_hash,
        hash_algorithm=HASH_ALGORITHM,
        canonicalization_version=CANONICALIZATION_VERSION,
    )


def calculate_checkpoint_digest(
    *,
    tenant_id: str,
    window_started_at: datetime,
    window_ended_at: datetime,
    events: Iterable[AuditEvent],
) -> str:
    ordered_events = tuple(events)
    payload = {
        "canonicalization_version": CANONICALIZATION_VERSION,
        "hash_algorithm": HASH_ALGORITHM,
        "tenant_id": tenant_id,
        "window_started_at": _normalize_datetime(window_started_at),
        "window_ended_at": _normalize_datetime(window_ended_at),
        "event_count": len(ordered_events),
        "event_hashes": [
            {
                "event_id": event.event_id,
                "previous_hash": event.previous_hash,
                "current_hash": event.current_hash,
            }
            for event in ordered_events
        ],
    }
    canonical_payload = json.dumps(
        payload,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    )
    return hashlib.sha256(canonical_payload.encode("utf-8")).hexdigest()


def calculate_checkpoint_id(
    *,
    tenant_id: str,
    window_started_at: datetime,
    window_ended_at: datetime,
    batch_digest: str,
) -> str:
    material = "|".join(
        (
            tenant_id,
            _normalize_datetime(window_started_at),
            _normalize_datetime(window_ended_at),
            batch_digest,
        )
    )
    return f"audit_chk_{hashlib.sha256(material.encode('utf-8')).hexdigest()[:32]}"


def _canonical_event_payload(event: AuditEvent, *, previous_hash: str | None) -> dict[str, Any]:
    return {
        "canonicalization_version": CANONICALIZATION_VERSION,
        "hash_algorithm": HASH_ALGORITHM,
        "integrity_scope": "tenant",
        "integrity_chain_id": event.tenant_id,
        "previous_hash": previous_hash or GENESIS_PREVIOUS_HASH,
        "tenant_id": event.tenant_id,
        "aggregate_type": event.aggregate_type,
        "aggregate_id": event.aggregate_id,
        "event_id": event.event_id,
        "event_type": event.event_type,
        "action": event.action,
        "resource_type": event.resource_type,
        "resource_id": event.resource_id,
        "actor_subject_id": event.actor_subject_id,
        "source_service": event.source_service,
        "source_kind": event.source_kind,
        "result": event.result,
        "occurred_at": _normalize_datetime(event.occurred_at),
        "correlation_id": event.correlation_id,
        "trace_id": event.trace_id,
        "request_id": event.request_id,
        "safe_details": _normalize_mapping(event.safe_details),
        "operational_evidence_refs": [
            {
                "kind": reference.kind,
                "reference": reference.reference,
                "source": reference.source,
            }
            for reference in sorted(
                event.operational_evidence_refs,
                key=lambda item: (item.kind, item.source, item.reference),
            )
        ],
    }


def _normalize_mapping(value: Mapping[str, str]) -> dict[str, str]:
    return {key: value[key] for key in sorted(value)}


def _normalize_datetime(value: datetime) -> str:
    return value.astimezone(UTC).isoformat()
