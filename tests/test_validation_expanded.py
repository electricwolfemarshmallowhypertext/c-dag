from __future__ import annotations

import json
from pathlib import Path
import uuid

import pytest

from causal_credit_risk.model import CausalDAGModel, ModelValidationError
from causal_credit_risk.policy import DecisionPolicy, PolicyValidationError
from causal_credit_risk.schemas import PolicyConfig


PROJECT_ROOT = Path(__file__).resolve().parents[1]
MODEL_CONFIG_PATH = PROJECT_ROOT / "configs" / "credit_risk_model.v1.json"
POLICY_CONFIG_PATH = PROJECT_ROOT / "configs" / "decision_policy.v1.json"


def _write_temp_model(payload: dict) -> Path:
    temp_path = PROJECT_ROOT / "tests" / f"__tmp_model_{uuid.uuid4().hex}.json"
    temp_path.write_text(json.dumps(payload), encoding="utf-8")
    return temp_path


def test_invalid_evidence_unknown_node_raises() -> None:
    model = CausalDAGModel.from_json(MODEL_CONFIG_PATH)
    with pytest.raises(KeyError):
        model.normalize_evidence({"unknown_node": "value"})


def test_invalid_evidence_unknown_state_raises() -> None:
    model = CausalDAGModel.from_json(MODEL_CONFIG_PATH)
    with pytest.raises(ValueError):
        model.normalize_evidence({"tenure": "unknown_state"})


def test_invalid_policy_thresholds_fail_validation() -> None:
    base = json.loads(POLICY_CONFIG_PATH.read_text(encoding="utf-8"))
    invalid = PolicyConfig(
        policy_id=base["policy_id"],
        policy_version=base["policy_version"],
        decline_threshold=0.4,
        manual_review_lower=0.2,
        manual_review_upper=0.6,
        risk_outcome_node=base["risk_outcome_node"],
        high_risk_state=base["high_risk_state"],
    )
    with pytest.raises(PolicyValidationError):
        DecisionPolicy(invalid)


def test_unknown_parent_reference_fails_validation() -> None:
    payload = json.loads(MODEL_CONFIG_PATH.read_text(encoding="utf-8"))
    for node in payload["nodes"]:
        if node["node_id"] == "income":
            node["parents"] = ["not_a_real_node"]
            break
    payload["cpds"]["income"]["parents"] = ["not_a_real_node"]

    bad_path = _write_temp_model(payload)
    try:
        with pytest.raises(ModelValidationError):
            CausalDAGModel.from_json(bad_path)
    finally:
        bad_path.unlink(missing_ok=True)


def test_malformed_cpd_shape_fails_validation() -> None:
    payload = json.loads(MODEL_CONFIG_PATH.read_text(encoding="utf-8"))
    payload["cpds"]["risk"]["table"] = [[0.95, 0.75], [0.05, 0.25]]

    bad_path = _write_temp_model(payload)
    try:
        with pytest.raises(ModelValidationError):
            CausalDAGModel.from_json(bad_path)
    finally:
        bad_path.unlink(missing_ok=True)


def test_malformed_cpd_normalization_fails_validation() -> None:
    payload = json.loads(MODEL_CONFIG_PATH.read_text(encoding="utf-8"))
    payload["cpds"]["tenure"]["table"] = [0.4, 0.7]

    bad_path = _write_temp_model(payload)
    try:
        with pytest.raises(ModelValidationError):
            CausalDAGModel.from_json(bad_path)
    finally:
        bad_path.unlink(missing_ok=True)


def test_cycle_detection_fails_validation() -> None:
    payload = json.loads(MODEL_CONFIG_PATH.read_text(encoding="utf-8"))
    for node in payload["nodes"]:
        if node["node_id"] == "tenure":
            node["parents"] = ["income"]
            break
    payload["cpds"]["tenure"]["parents"] = ["income"]
    payload["cpds"]["tenure"]["table"] = [
        [0.4, 0.3],
        [0.6, 0.7],
    ]

    bad_path = _write_temp_model(payload)
    try:
        with pytest.raises(ModelValidationError, match="cycle detected"):
            CausalDAGModel.from_json(bad_path)
    finally:
        bad_path.unlink(missing_ok=True)
