from __future__ import annotations

from pathlib import Path

import numpy as np

from causal_credit_risk.inference import ExactInferenceEngine
from causal_credit_risk.model import CausalDAGModel


PROJECT_ROOT = Path(__file__).resolve().parents[1]
MODEL_CONFIG_PATH = PROJECT_ROOT / "configs" / "credit_risk_model.v1.json"


def test_baseline_high_risk_probability_matches_expected() -> None:
    model = CausalDAGModel.from_json(MODEL_CONFIG_PATH)
    engine = ExactInferenceEngine(model)

    probability = engine.query_probability(
        "risk",
        "high_risk",
        evidence={"tenure": "short", "utilization": "high"},
    )
    assert np.isclose(probability, 0.849375, atol=1e-9)
