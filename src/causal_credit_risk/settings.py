"""Runtime settings for local enterprise seams."""

from __future__ import annotations

from dataclasses import dataclass
import os
from pathlib import Path
from typing import Literal, Mapping


AuthMode = Literal["none", "api_key"]
AuditStoreMode = Literal["none", "file", "sqlite"]
TenancyMode = Literal["single", "tenant_id"]


@dataclass(frozen=True)
class RuntimeSettings:
    auth_mode: AuthMode = "none"
    api_key: str | None = None
    audit_store: AuditStoreMode = "none"
    audit_store_path: str = "outputs/audit_store"
    tenancy_mode: TenancyMode = "single"
    audit_retention_days: int = 365
    log_level: str = "info"

    @classmethod
    def from_env(cls, env: Mapping[str, str] | None = None) -> "RuntimeSettings":
        source = env if env is not None else os.environ

        auth_mode_raw = source.get("AUTH_MODE", "none").strip().lower()
        if auth_mode_raw not in {"none", "api_key"}:
            raise ValueError("AUTH_MODE must be one of: none, api_key")
        auth_mode: AuthMode = "api_key" if auth_mode_raw == "api_key" else "none"

        audit_store_raw = source.get("AUDIT_STORE", "none").strip().lower()
        if audit_store_raw not in {"none", "file", "sqlite"}:
            raise ValueError("AUDIT_STORE must be one of: none, file, sqlite")
        audit_store: AuditStoreMode = (
            "file" if audit_store_raw == "file" else "sqlite" if audit_store_raw == "sqlite" else "none"
        )

        tenancy_mode_raw = source.get("TENANCY_MODE", "single").strip().lower()
        if tenancy_mode_raw not in {"single", "tenant_id"}:
            raise ValueError("TENANCY_MODE must be one of: single, tenant_id")
        tenancy_mode: TenancyMode = "tenant_id" if tenancy_mode_raw == "tenant_id" else "single"

        retention_raw = source.get("AUDIT_RETENTION_DAYS", "365").strip()
        try:
            retention = int(retention_raw)
        except ValueError as exc:
            raise ValueError("AUDIT_RETENTION_DAYS must be an integer") from exc
        if retention < 1:
            raise ValueError("AUDIT_RETENTION_DAYS must be >= 1")

        api_key = source.get("API_KEY")
        if api_key is not None:
            api_key = api_key.strip() or None

        log_level = source.get("LOG_LEVEL", "info").strip().lower() or "info"

        return cls(
            auth_mode=auth_mode,
            api_key=api_key,
            audit_store=audit_store,
            audit_store_path=source.get("AUDIT_STORE_PATH", "outputs/audit_store").strip()
            or "outputs/audit_store",
            tenancy_mode=tenancy_mode,
            audit_retention_days=retention,
            log_level=log_level,
        )


def project_root() -> Path:
    return Path(__file__).resolve().parents[2]
