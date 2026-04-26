from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from causal_credit_risk.api import create_app
from causal_credit_risk.cli import run_decision


PROJECT_ROOT = Path(__file__).resolve().parents[1]
MODEL_CONFIG_PATH = PROJECT_ROOT / "configs" / "credit_risk_model.v1.json"
POLICY_CONFIG_PATH = PROJECT_ROOT / "configs" / "decision_policy.v1.json"


def _client() -> TestClient:
    app = create_app(
        model_config_path=MODEL_CONFIG_PATH,
        policy_config_path=POLICY_CONFIG_PATH,
    )
    return TestClient(app)


def test_healthz_and_readyz() -> None:
    client = _client()
    health = client.get("/healthz")
    assert health.status_code == 200
    assert health.json() == {"status": "ok"}

    ready = client.get("/readyz")
    assert ready.status_code == 200
    payload = ready.json()
    assert payload["status"] == "ready"
    assert payload["model_id"] == "credit_risk_causal_dag"


def test_decision_endpoint_valid_and_invalid_evidence() -> None:
    client = _client()

    ok = client.post("/v1/decision", json={"tenure": "short", "utilization": "high"})
    assert ok.status_code == 200
    payload = ok.json()
    assert payload["risk_probability"] == 0.849375
    assert payload["decision"] == "DECLINE"
    assert "audit_chain" in payload
    assert "audit_hash" in payload["audit_chain"]

    bad = client.post("/v1/decision", json={"tenure": "bad", "utilization": "high"})
    assert bad.status_code == 400
    assert "Unknown state" in bad.json()["detail"]

    malformed = client.post("/v1/decision", json=["not", "an", "object"])
    assert malformed.status_code == 422


def test_replay_endpoint_valid_and_mismatch() -> None:
    client = _client()
    audit = run_decision(
        model_config_path=MODEL_CONFIG_PATH,
        policy_config_path=POLICY_CONFIG_PATH,
    ).to_dict()

    ok = client.post("/v1/replay", json=audit)
    assert ok.status_code == 200
    replay = ok.json()
    assert replay["risk_probability_match"] is True
    assert replay["decision_match"] is True
    assert "audit_chain" in replay

    mismatch = dict(audit)
    mismatch["policy_version"] = "999.0.0"
    bad = client.post("/v1/replay", json=mismatch)
    assert bad.status_code == 400
    assert "policy_version mismatch" in bad.json()["detail"]


def test_batch_endpoint_row_level_results() -> None:
    client = _client()
    response = client.post(
        "/v1/batch",
        json=[
            {"tenure": "short", "utilization": "high", "segment": "A"},
            {"tenure": "invalid_state", "utilization": "low", "segment": "B"},
        ],
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["rows_processed"] == 2
    assert payload["rows_failed"] == 1
    assert payload["results"][0]["status"] == "ok"
    assert "audit_chain" in payload["results"][0]
    assert payload["results"][1]["status"] == "error"

    malformed = client.post("/v1/batch", json={"not": "a list"})
    assert malformed.status_code == 422


def test_fairness_endpoint() -> None:
    client = _client()
    response = client.post(
        "/v1/fairness",
        json={
            "rows": [
                {"segment": "A", "decision": "APPROVE", "risk_probability": 0.2},
                {"segment": "B", "decision": "DECLINE", "risk_probability": 0.8},
            ],
            "subgroup_column": "segment",
            "min_sample_size": 2,
        },
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["subgroup_column"] == "segment"
    assert "audit_chain" in payload
    assert "A" in payload["subgroups"]

    bad = client.post("/v1/fairness", json={"rows": "bad"})
    assert bad.status_code == 400
