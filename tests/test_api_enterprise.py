from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from causal_credit_risk.api import create_app
from causal_credit_risk.audit_chain import build_audit_chain_record
from causal_credit_risk.cli import run_decision
from causal_credit_risk.settings import RuntimeSettings


PROJECT_ROOT = Path(__file__).resolve().parents[1]
MODEL_CONFIG_PATH = PROJECT_ROOT / "configs" / "credit_risk_model.v1.json"
POLICY_CONFIG_PATH = PROJECT_ROOT / "configs" / "decision_policy.v1.json"


def _client(settings: RuntimeSettings) -> TestClient:
    app = create_app(
        model_config_path=MODEL_CONFIG_PATH,
        policy_config_path=POLICY_CONFIG_PATH,
        settings=settings,
    )
    return TestClient(app)


def test_api_key_auth_mode() -> None:
    client = _client(
        RuntimeSettings(auth_mode="api_key", api_key="k1", audit_store="none", tenancy_mode="single")
    )
    unauthorized = client.post("/v1/decision", json={"tenure": "short", "utilization": "high"})
    assert unauthorized.status_code == 401

    authorized = client.post(
        "/v1/decision",
        headers={"X-API-Key": "k1"},
        json={"tenure": "short", "utilization": "high"},
    )
    assert authorized.status_code == 200


def test_tenant_mode_requires_tenant_id() -> None:
    client = _client(RuntimeSettings(tenancy_mode="tenant_id", audit_store="none"))
    missing = client.post("/v1/decision", json={"tenure": "short", "utilization": "high"})
    assert missing.status_code == 400
    assert "tenant_id" in missing.json()["detail"]

    ok = client.post(
        "/v1/decision",
        json={"tenant_id": "tenant-a", "tenure": "short", "utilization": "high"},
    )
    assert ok.status_code == 200
    assert ok.json()["tenant_id"] == "tenant-a"


def test_audit_chain_verify_endpoint_success_and_failure() -> None:
    client = _client(RuntimeSettings())
    audit_1 = run_decision(
        model_config_path=MODEL_CONFIG_PATH,
        policy_config_path=POLICY_CONFIG_PATH,
        tenant_id="default",
    ).to_dict()
    r1 = build_audit_chain_record(audit_1, chain_index=0, previous_hash=None, tenant_id="default")
    audit_2 = run_decision(
        model_config_path=MODEL_CONFIG_PATH,
        policy_config_path=POLICY_CONFIG_PATH,
        evidence={"tenure": "long", "utilization": "low"},
        tenant_id="default",
    ).to_dict()
    r2 = build_audit_chain_record(
        audit_2,
        chain_index=1,
        previous_hash=r1["audit_hash"],
        tenant_id="default",
    )

    ok = client.post("/v1/audit-chain/verify", json=[r1, r2])
    assert ok.status_code == 200
    assert ok.json()["valid"] is True

    tampered = [dict(r1), dict(r2)]
    tampered[1]["audit_record"] = dict(tampered[1]["audit_record"])
    tampered[1]["audit_record"]["decision"] = "APPROVE"
    bad = client.post("/v1/audit-chain/verify", json=tampered)
    assert bad.status_code == 200
    assert bad.json()["valid"] is False


def test_fairness_report_endpoint() -> None:
    client = _client(RuntimeSettings())
    response = client.post(
        "/v1/fairness/report",
        json={
            "rows": [
                {"segment": "A", "decision": "APPROVE", "risk_probability": 0.2, "tenant_id": "default"},
                {"segment": "B", "decision": "DECLINE", "risk_probability": 0.8, "tenant_id": "default"},
            ],
            "subgroup_column": "segment",
            "min_sample_size": 2,
        },
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["subgroup_column"] == "segment"
    assert payload["tenant_id"] == "default"
