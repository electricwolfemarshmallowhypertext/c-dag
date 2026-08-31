from __future__ import annotations

from typing import Any, Mapping

from causal_credit_risk.surrogate import (
    CounterfactualProbe,
    build_opaque_model_audit_trace,
    construct_surrogate_dag,
    detect_proxy_features,
    evaluate_counterfactual_consistency,
    evaluate_surrogate_fidelity,
    evaluate_surrogate_stability,
)


Row = Mapping[str, Any]


def _rows() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for idx in range(80):
        leverage = idx % 4
        fico_band = idx % 5
        delinquency = 1 if idx % 7 == 0 else 0
        protected = "A" if idx % 2 == 0 else "B"
        zip_proxy = "100" if protected == "A" else "900"
        rows.append(
            {
                "leverage": leverage,
                "fico_band": fico_band,
                "delinquency": delinquency,
                "protected_class": protected,
                "zip_proxy": zip_proxy,
            }
        )
    return rows


def _opaque_predict(row: Row) -> float:
    return min(
        1.0,
        0.12
        + 0.11 * float(row["leverage"])
        + 0.05 * float(row["fico_band"])
        + 0.22 * float(row["delinquency"]),
    )


def _surrogate_predict(row: Row) -> float:
    return min(
        1.0,
        0.13
        + 0.108 * float(row["leverage"])
        + 0.048 * float(row["fico_band"])
        + 0.21 * float(row["delinquency"]),
    )


def test_construct_surrogate_dag_from_opaque_predictions() -> None:
    dag = construct_surrogate_dag(
        _rows(),
        _opaque_predict,
        feature_names=["leverage", "fico_band", "delinquency"],
        min_feature_association=0.01,
    )

    assert dag.target_node == "opaque_model_score"
    assert dag.boundary.startswith("validated surrogate governance evidence")
    assert {edge.target for edge in dag.edges} >= {"opaque_model_score"}
    assert any(edge.source == "leverage" for edge in dag.edges)


def test_surrogate_fidelity_reports_global_and_local_agreement() -> None:
    report = evaluate_surrogate_fidelity(_rows(), _opaque_predict, _surrogate_predict)

    assert report.row_count == 80
    assert report.mean_absolute_error < 0.03
    assert report.classification_agreement >= 0.95
    assert len(report.local_absolute_errors) == 80
    assert report.approximation_label == "high_fidelity_surrogate"


def test_surrogate_stability_flags_stable_drivers() -> None:
    report = evaluate_surrogate_stability(
        _rows(),
        _opaque_predict,
        feature_names=["leverage", "fico_band", "delinquency"],
        fold_count=4,
        top_k=2,
    )

    assert report.row_count == 80
    assert report.mean_top_feature_overlap >= 0.5
    assert report.stable_features
    assert report.boundary.endswith("guaranteed true causal reasoning")


def test_proxy_detection_flags_strong_sensitive_feature_association() -> None:
    findings = detect_proxy_features(
        _rows(),
        candidate_features=["leverage", "zip_proxy"],
        sensitive_features=["protected_class"],
        association_threshold=0.9,
    )

    assert len(findings) == 1
    assert findings[0].feature == "zip_proxy"
    assert findings[0].sensitive_feature == "protected_class"
    assert findings[0].flag == "potential_proxy"


def test_counterfactual_consistency_checks_effect_direction() -> None:
    report = evaluate_counterfactual_consistency(
        _rows(),
        _opaque_predict,
        _surrogate_predict,
        probes=[CounterfactualProbe(feature="leverage", intervention_value=3)],
    )

    assert report.probe_count == 1
    assert report.sign_agreement_rate >= 0.95
    assert report.approximation_label == "counterfactual_direction_consistent"


def test_opaque_model_audit_trace_uses_surrogate_boundary_language() -> None:
    rows = _rows()
    dag = construct_surrogate_dag(
        rows,
        _opaque_predict,
        feature_names=["leverage", "fico_band", "delinquency"],
        min_feature_association=0.01,
    )
    fidelity = evaluate_surrogate_fidelity(rows, _opaque_predict, _surrogate_predict)
    proxies = detect_proxy_features(
        rows,
        candidate_features=["zip_proxy"],
        sensitive_features=["protected_class"],
        association_threshold=0.9,
    )

    trace = build_opaque_model_audit_trace(
        row=rows[0],
        opaque_predict=_opaque_predict,
        surrogate_predict=_surrogate_predict,
        surrogate_dag=dag,
        fidelity_report=fidelity,
        proxy_findings=proxies,
    )

    assert trace["trace_type"] == "opaque_model_surrogate_trace"
    assert trace["evidence_type"] == "validated_surrogate_governance_evidence"
    assert trace["validation_status"]["automatic_truth_claim"] is False
    assert trace["validation_status"]["requires_human_review"] is True
    assert trace["proxy_findings"][0]["flag"] == "potential_proxy"
