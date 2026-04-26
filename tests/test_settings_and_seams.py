from __future__ import annotations

from pathlib import Path
import tempfile

import pytest

from causal_credit_risk.audit_store import SQLiteAuditStore
from causal_credit_risk.auth import ApiKeyAuthProvider, AuthError, NoAuthProvider
from causal_credit_risk.settings import RuntimeSettings
from causal_credit_risk.tenancy import SingleTenantResolver, TenantIdResolver, TenancyError


def test_runtime_settings_defaults() -> None:
    settings = RuntimeSettings.from_env({})
    assert settings.auth_mode == "none"
    assert settings.audit_store == "none"
    assert settings.tenancy_mode == "single"
    assert settings.audit_retention_days == 365


def test_auth_providers() -> None:
    no_auth = NoAuthProvider()
    no_auth.authorize(None)

    provider = ApiKeyAuthProvider("secret")
    provider.authorize("secret")
    with pytest.raises(AuthError):
        provider.authorize("wrong")
    with pytest.raises(ValueError):
        ApiKeyAuthProvider("")


def test_tenant_resolvers() -> None:
    single = SingleTenantResolver()
    assert single.resolve(None) == "default"

    resolver = TenantIdResolver()
    assert resolver.resolve({"tenant_id": "t1"}) == "t1"
    with pytest.raises(TenancyError):
        resolver.resolve({})


def test_sqlite_audit_store_insert_read_and_list() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        db_path = Path(tmp) / "audit.db"
        store = SQLiteAuditStore(db_path)

        audit_payload = {
            "decision_id": "d-1",
            "tenant_id": "tenant-a",
            "model_id": "m",
            "model_version": "1",
            "policy_version": "1",
            "decision": "DECLINE",
            "risk_probability": 0.9,
            "timestamp_utc": "2026-04-26T00:00:00+00:00",
        }
        store.save_audit(audit_payload)
        loaded = store.get_audit("d-1", tenant_id="tenant-a")
        assert loaded is not None
        assert loaded["decision_id"] == "d-1"

        listed = store.list_audits(tenant_id="tenant-a")
        assert len(listed) == 1

        chain_payload = {
            "tenant_id": "tenant-a",
            "audit_hash": "h1",
            "previous_hash": None,
            "chain_index": 0,
            "timestamp_utc": "2026-04-26T00:00:00+00:00",
            "audit_record": audit_payload,
        }
        store.save_chain_record(chain_payload)
        chain_rows = store.list_chain_records(tenant_id="tenant-a")
        assert len(chain_rows) == 1
        assert chain_rows[0]["audit_hash"] == "h1"
