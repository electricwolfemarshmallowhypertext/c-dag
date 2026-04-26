from __future__ import annotations

import json
from pathlib import Path

import pytest

from causal_credit_risk.model import CausalDAGModel, ModelValidationError


PROJECT_ROOT = Path(__file__).resolve().parents[1]
MODEL_CONFIG_PATH = PROJECT_ROOT / "configs" / "credit_risk_model.v1.json"


def test_valid_model_cpds_pass_validation() -> None:
    model = CausalDAGModel.from_json(MODEL_CONFIG_PATH)
    assert model.config.model_id == "credit_risk_causal_dag"
    assert set(model.cpd_arrays) == set(model.nodes)


def test_invalid_cpd_fails_validation() -> None:
    payload = json.loads(MODEL_CONFIG_PATH.read_text(encoding="utf-8"))
    payload["cpds"]["income"]["table"][0][0] = 1.2

    bad_config = PROJECT_ROOT / "tests" / "__invalid_model.json"
    bad_config.write_text(json.dumps(payload), encoding="utf-8")
    try:
        with pytest.raises(ModelValidationError):
            CausalDAGModel.from_json(bad_config)
    finally:
        bad_config.unlink(missing_ok=True)
