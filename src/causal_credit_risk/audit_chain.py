"""Tamper-evident hashing utilities for audit records."""

from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
from typing import Any


def _utc_timestamp() -> str:
    return datetime.now(tz=timezone.utc).isoformat(timespec="seconds")


def canonical_json(payload: Any) -> str:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def compute_audit_hash(
    audit_record: dict[str, Any],
    *,
    previous_hash: str | None = None,
    chain_index: int | None = None,
    tenant_id: str | None = None,
) -> str:
    hash_payload = {
        "audit_record": audit_record,
        "previous_hash": previous_hash,
        "chain_index": chain_index,
    }
    if tenant_id is not None:
        hash_payload["tenant_id"] = tenant_id
    digest = hashlib.sha256(canonical_json(hash_payload).encode("utf-8"))
    return digest.hexdigest()


def build_audit_chain_record(
    audit_record: dict[str, Any],
    *,
    chain_index: int,
    previous_hash: str | None = None,
    timestamp_utc: str | None = None,
    tenant_id: str = "default",
) -> dict[str, Any]:
    audit_hash = compute_audit_hash(
        audit_record,
        previous_hash=previous_hash,
        chain_index=chain_index,
        tenant_id=tenant_id,
    )
    return {
        "chain_index": chain_index,
        "timestamp_utc": timestamp_utc or _utc_timestamp(),
        "previous_hash": previous_hash,
        "audit_hash": audit_hash,
        "tenant_id": tenant_id,
        "audit_record": audit_record,
    }


def verify_audit_hash(record: dict[str, Any]) -> bool:
    required = {"chain_index", "previous_hash", "audit_hash", "audit_record"}
    if not required.issubset(record.keys()):
        return False

    expected = compute_audit_hash(
        record["audit_record"],
        previous_hash=record["previous_hash"],
        chain_index=record["chain_index"],
        tenant_id=record.get("tenant_id"),
    )
    return expected == record["audit_hash"]


def verify_audit_chain(records: list[dict[str, Any]]) -> bool:
    if not records:
        return True

    previous_hash: str | None = None
    previous_index: int | None = None
    previous_tenant: str | None = None
    for idx, record in enumerate(records):
        if not verify_audit_hash(record):
            return False

        current_index = record.get("chain_index")
        if not isinstance(current_index, int):
            return False
        if previous_index is not None and current_index != previous_index + 1:
            return False

        if idx == 0:
            if record.get("previous_hash") not in (None, ""):
                return False
        else:
            if record.get("previous_hash") != previous_hash:
                return False
            if record.get("tenant_id") != previous_tenant:
                return False

        previous_hash = record.get("audit_hash")
        if not isinstance(previous_hash, str):
            return False
        previous_index = current_index
        if record.get("tenant_id") is not None and not isinstance(record.get("tenant_id"), str):
            return False
        previous_tenant = record.get("tenant_id")

    return True
