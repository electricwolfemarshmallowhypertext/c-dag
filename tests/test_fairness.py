from __future__ import annotations

from causal_credit_risk.fairness import compute_fairness_report


def test_fairness_report_basic_subgroup_metrics() -> None:
    rows = [
        {"segment": "A", "decision": "APPROVE", "risk_probability": 0.2},
        {"segment": "A", "decision": "DECLINE", "risk_probability": 0.8},
        {"segment": "B", "decision": "REVIEW", "risk_probability": 0.5},
        {"segment": "B", "decision": "DECLINE", "risk_probability": 0.7},
    ]
    report = compute_fairness_report(rows, subgroup_column="segment", min_sample_size=1)
    assert report["rows_received"] == 4
    assert report["rows_analyzed"] == 4
    assert report["subgroups"]["A"]["count"] == 2
    assert report["subgroups"]["B"]["count"] == 2
    assert report["subgroups"]["A"]["approve_rate"] == 0.5
    assert report["subgroups"]["B"]["decline_rate"] == 0.5
    assert report["max_min_subgroup_delta"]["mean_risk_probability_delta"] >= 0.0


def test_fairness_report_small_sample_warning() -> None:
    rows = [
        {"segment": "A", "decision": "APPROVE", "risk_probability": 0.2},
        {"segment": "B", "decision": "DECLINE", "risk_probability": 0.8},
    ]
    report = compute_fairness_report(rows, subgroup_column="segment", min_sample_size=3)
    assert len(report["warnings"]) >= 2
    assert "small sample size" in " ".join(report["warnings"])
