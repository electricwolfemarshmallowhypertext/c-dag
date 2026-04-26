from __future__ import annotations

from pathlib import Path
import re

from causal_credit_risk.cli import run_decision


PROJECT_ROOT = Path(__file__).resolve().parents[1]
MODEL_CONFIG_PATH = PROJECT_ROOT / "configs" / "credit_risk_model.v1.json"
POLICY_CONFIG_PATH = PROJECT_ROOT / "configs" / "decision_policy.v1.json"


def test_audit_record_contains_required_fields() -> None:
    audit = run_decision(
        model_config_path=MODEL_CONFIG_PATH,
        policy_config_path=POLICY_CONFIG_PATH,
    )
    payload = audit.to_dict()

    required_fields = {
        "decision_id",
        "model_id",
        "model_version",
        "policy_version",
        "timestamp_utc",
        "input_evidence",
        "inferred_nodes",
        "risk_probability",
        "decision",
        "causal_chain",
        "counterfactuals",
        "validation_status",
    }

    assert required_fields.issubset(payload.keys())
    assert payload["decision"] in {"APPROVE", "REVIEW", "DECLINE"}
    assert payload["validation_status"]["model_valid"] is True
    assert payload["validation_status"]["policy_valid"] is True


def test_audit_json_rounds_floats_to_six_decimals() -> None:
    audit = run_decision(
        model_config_path=MODEL_CONFIG_PATH,
        policy_config_path=POLICY_CONFIG_PATH,
    )
    body = audit.to_json(indent=2)
    for match in re.finditer(r"-?\\d+\\.(\\d+)", body):
        assert len(match.group(1)) <= 6
