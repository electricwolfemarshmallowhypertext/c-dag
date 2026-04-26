from __future__ import annotations

from pathlib import Path

from causal_credit_risk.api import create_app


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def test_openapi_contains_expected_paths() -> None:
    app = create_app(
        model_config_path=PROJECT_ROOT / "configs" / "credit_risk_model.v1.json",
        policy_config_path=PROJECT_ROOT / "configs" / "decision_policy.v1.json",
    )
    schema = app.openapi()
    paths = set(schema.get("paths", {}).keys())
    assert "/healthz" in paths
    assert "/readyz" in paths
    assert "/v1/decision" in paths
    assert "/v1/replay" in paths
    assert "/v1/batch" in paths
    assert "/v1/fairness" in paths
    assert "/v1/fairness/report" in paths
    assert "/v1/audit-chain/verify" in paths
