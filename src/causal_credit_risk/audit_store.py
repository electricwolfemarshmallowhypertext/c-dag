"""Local audit persistence implementations."""

from __future__ import annotations

from collections.abc import Mapping
from contextlib import closing
from datetime import datetime, timezone
import json
from pathlib import Path
import sqlite3
from typing import Any

from causal_credit_risk.interfaces import AuditStore
from causal_credit_risk.settings import RuntimeSettings


def _utc_now() -> str:
    return datetime.now(tz=timezone.utc).isoformat(timespec="seconds")


class LocalJsonAuditStore(AuditStore):
    """Append-only JSONL storage for local pilot use."""

    def __init__(self, root_path: str | Path) -> None:
        self.root_path = Path(root_path)
        self.root_path.mkdir(parents=True, exist_ok=True)
        self.audit_path = self.root_path / "audit_records.jsonl"
        self.chain_path = self.root_path / "audit_chain_records.jsonl"

    def save_audit(self, audit_record: Mapping[str, Any]) -> None:
        payload = dict(audit_record)
        payload.setdefault("created_at_utc", _utc_now())
        self._append_json_line(self.audit_path, payload)

    def get_audit(self, decision_id: str, *, tenant_id: str = "default") -> dict[str, Any] | None:
        for row in self._read_json_lines(self.audit_path):
            if row.get("decision_id") == decision_id and row.get("tenant_id", "default") == tenant_id:
                return row
        return None

    def list_audits(self, *, tenant_id: str = "default") -> list[dict[str, Any]]:
        return [
            row
            for row in self._read_json_lines(self.audit_path)
            if row.get("tenant_id", "default") == tenant_id
        ]

    def save_chain_record(self, chain_record: Mapping[str, Any]) -> None:
        payload = dict(chain_record)
        payload.setdefault("created_at_utc", _utc_now())
        self._append_json_line(self.chain_path, payload)

    def list_chain_records(self, *, tenant_id: str = "default") -> list[dict[str, Any]]:
        return [
            row
            for row in self._read_json_lines(self.chain_path)
            if row.get("tenant_id", "default") == tenant_id
        ]

    @staticmethod
    def _append_json_line(path: Path, payload: Mapping[str, Any]) -> None:
        with path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(dict(payload), ensure_ascii=False))
            fh.write("\n")

    @staticmethod
    def _read_json_lines(path: Path) -> list[dict[str, Any]]:
        if not path.exists():
            return []
        rows: list[dict[str, Any]] = []
        with path.open("r", encoding="utf-8") as fh:
            for line in fh:
                stripped = line.strip()
                if not stripped:
                    continue
                rows.append(json.loads(stripped))
        return rows


class SQLiteAuditStore(AuditStore):
    """SQLite-based local audit persistence."""

    def __init__(self, db_path: str | Path) -> None:
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._initialize()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.db_path)
        connection.row_factory = sqlite3.Row
        return connection

    def _initialize(self) -> None:
        with closing(self._connect()) as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS audit_records (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    decision_id TEXT NOT NULL,
                    tenant_id TEXT NOT NULL,
                    model_id TEXT NOT NULL,
                    model_version TEXT NOT NULL,
                    policy_version TEXT NOT NULL,
                    decision TEXT NOT NULL,
                    risk_probability REAL NOT NULL,
                    audit_json TEXT NOT NULL,
                    created_at_utc TEXT NOT NULL
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS audit_chain_records (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    tenant_id TEXT NOT NULL,
                    audit_hash TEXT NOT NULL,
                    previous_hash TEXT,
                    chain_index INTEGER NOT NULL,
                    chain_json TEXT NOT NULL,
                    created_at_utc TEXT NOT NULL
                )
                """
            )
            conn.commit()

    def save_audit(self, audit_record: Mapping[str, Any]) -> None:
        payload = dict(audit_record)
        created_at = str(payload.get("timestamp_utc") or _utc_now())
        tenant_id = str(payload.get("tenant_id", "default"))
        with closing(self._connect()) as conn:
            conn.execute(
                """
                INSERT INTO audit_records (
                    decision_id,
                    tenant_id,
                    model_id,
                    model_version,
                    policy_version,
                    decision,
                    risk_probability,
                    audit_json,
                    created_at_utc
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    str(payload.get("decision_id", "")),
                    tenant_id,
                    str(payload.get("model_id", "")),
                    str(payload.get("model_version", "")),
                    str(payload.get("policy_version", "")),
                    str(payload.get("decision", "")),
                    float(payload.get("risk_probability", 0.0)),
                    json.dumps(payload, ensure_ascii=False),
                    created_at,
                ),
            )
            conn.commit()

    def get_audit(self, decision_id: str, *, tenant_id: str = "default") -> dict[str, Any] | None:
        with closing(self._connect()) as conn:
            row = conn.execute(
                """
                SELECT audit_json FROM audit_records
                WHERE decision_id = ? AND tenant_id = ?
                ORDER BY id DESC LIMIT 1
                """,
                (decision_id, tenant_id),
            ).fetchone()
            if row is None:
                return None
            return json.loads(str(row["audit_json"]))

    def list_audits(self, *, tenant_id: str = "default") -> list[dict[str, Any]]:
        with closing(self._connect()) as conn:
            rows = conn.execute(
                """
                SELECT audit_json FROM audit_records
                WHERE tenant_id = ?
                ORDER BY id ASC
                """,
                (tenant_id,),
            ).fetchall()
        return [json.loads(str(row["audit_json"])) for row in rows]

    def save_chain_record(self, chain_record: Mapping[str, Any]) -> None:
        payload = dict(chain_record)
        created_at = str(payload.get("timestamp_utc") or _utc_now())
        tenant_id = str(payload.get("tenant_id", "default"))
        with closing(self._connect()) as conn:
            conn.execute(
                """
                INSERT INTO audit_chain_records (
                    tenant_id,
                    audit_hash,
                    previous_hash,
                    chain_index,
                    chain_json,
                    created_at_utc
                ) VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    tenant_id,
                    str(payload.get("audit_hash", "")),
                    payload.get("previous_hash"),
                    int(payload.get("chain_index", 0)),
                    json.dumps(payload, ensure_ascii=False),
                    created_at,
                ),
            )
            conn.commit()

    def list_chain_records(self, *, tenant_id: str = "default") -> list[dict[str, Any]]:
        with closing(self._connect()) as conn:
            rows = conn.execute(
                """
                SELECT chain_json FROM audit_chain_records
                WHERE tenant_id = ?
                ORDER BY chain_index ASC, id ASC
                """,
                (tenant_id,),
            ).fetchall()
        return [json.loads(str(row["chain_json"])) for row in rows]


def build_audit_store(settings: RuntimeSettings) -> AuditStore | None:
    if settings.audit_store == "none":
        return None
    if settings.audit_store == "sqlite":
        return SQLiteAuditStore(settings.audit_store_path)
    return LocalJsonAuditStore(settings.audit_store_path)
