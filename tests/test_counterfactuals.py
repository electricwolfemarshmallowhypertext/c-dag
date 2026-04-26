from __future__ import annotations

from pathlib import Path

import numpy as np

from causal_credit_risk.counterfactuals import intervention_counterfactual
from causal_credit_risk.inference import ExactInferenceEngine
from causal_credit_risk.model import CausalDAGModel


PROJECT_ROOT = Path(__file__).resolve().parents[1]
MODEL_CONFIG_PATH = PROJECT_ROOT / "configs" / "credit_risk_model.v1.json"


def test_counterfactual_deltas_match_expected_values() -> None:
    model = CausalDAGModel.from_json(MODEL_CONFIG_PATH)
    engine = ExactInferenceEngine(model)
    baseline = {"tenure": "short", "utilization": "high"}

    long_tenure = intervention_counterfactual(
        engine,
        outcome_node_id="risk",
        outcome_state="high_risk",
        baseline_evidence=baseline,
        intervention_evidence={"tenure": "long"},
    )
    low_utilization = intervention_counterfactual(
        engine,
        outcome_node_id="risk",
        outcome_state="high_risk",
        baseline_evidence=baseline,
        intervention_evidence={"utilization": "low"},
    )
    both_improved = intervention_counterfactual(
        engine,
        outcome_node_id="risk",
        outcome_state="high_risk",
        baseline_evidence=baseline,
        intervention_evidence={"tenure": "long", "utilization": "low"},
    )

    assert np.isclose(long_tenure.before_probability, 0.849375, atol=1e-9)
    assert np.isclose(long_tenure.after_probability, 0.7435, atol=1e-9)
    assert np.isclose(long_tenure.delta, -0.105875, atol=1e-9)

    assert np.isclose(low_utilization.after_probability, 0.60625, atol=1e-9)
    assert np.isclose(low_utilization.delta, -0.243125, atol=1e-9)

    assert np.isclose(both_improved.after_probability, 0.455, atol=1e-9)
    assert np.isclose(both_improved.delta, -0.394375, atol=1e-9)
