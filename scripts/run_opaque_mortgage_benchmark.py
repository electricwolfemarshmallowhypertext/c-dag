"""Run an opaque-model surrogate benchmark on normalized mortgage rows.

WARNING:
This benchmark measures governance evidence for an opaque-model surrogate.
It does not prove true causal structure, production predictive performance,
credit eligibility fitness, or legal/regulatory certification.
"""

from __future__ import annotations

import argparse
import csv
from datetime import datetime, timezone
import json
from pathlib import Path
import sys
from typing import Any

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from causal_credit_risk.surrogate import (
    CounterfactualProbe,
    build_opaque_model_audit_trace,
    construct_surrogate_dag,
    detect_proxy_features,
    evaluate_counterfactual_consistency,
    evaluate_surrogate_fidelity,
    evaluate_surrogate_stability,
)
from public_mortgage_validation_common import (
    map_cltv_risk,
    map_default_loss_risk,
    map_delinquency_history_risk,
    map_dti_risk,
    map_fico_risk,
    map_loan_age_risk,
    map_loan_purpose_risk,
    map_ltv_risk,
    map_modification_risk,
    map_occupancy_risk,
    map_property_type_risk,
)


ALL_MAPPED_FEATURES: tuple[str, ...] = (
    "ltv_risk",
    "cltv_risk",
    "dti_risk",
    "fico_risk",
    "loan_age_risk",
    "delinquency_history_risk",
    "occupancy_risk",
    "loan_purpose_risk",
    "property_type_risk",
    "modification_risk",
    "default_loss_risk",
)

BENCHMARK_FEATURES: tuple[str, ...] = (
    "ltv_risk",
    "cltv_risk",
    "dti_risk",
    "fico_risk",
    "loan_age_risk",
    "occupancy_risk",
    "loan_purpose_risk",
    "property_type_risk",
)

EXCLUDED_LEAKAGE_FEATURES: tuple[str, ...] = (
    "delinquency_history_risk",
    "modification_risk",
    "default_loss_risk",
)

ENRICHERS = {
    "ltv_risk": map_ltv_risk,
    "cltv_risk": map_cltv_risk,
    "dti_risk": map_dti_risk,
    "fico_risk": map_fico_risk,
    "loan_age_risk": map_loan_age_risk,
    "delinquency_history_risk": map_delinquency_history_risk,
    "occupancy_risk": map_occupancy_risk,
    "loan_purpose_risk": map_loan_purpose_risk,
    "property_type_risk": map_property_type_risk,
    "modification_risk": map_modification_risk,
    "default_loss_risk": map_default_loss_risk,
}


def _utc_now() -> str:
    return datetime.now(tz=timezone.utc).isoformat(timespec="seconds")


def _progress(message: str) -> None:
    print(f"[progress] {message}", file=sys.stderr, flush=True)


def _round(value: Any) -> Any:
    if isinstance(value, float):
        return round(value, 6)
    if isinstance(value, dict):
        return {key: _round(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_round(item) for item in value]
    return value


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as fh:
        reader = csv.DictReader(fh)
        if reader.fieldnames is None:
            raise ValueError(f"Missing CSV header: {path}")
        return [dict(row) for row in reader]


def _load_rows(paths: list[Path], max_rows: int | None) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for path in paths:
        for row in _read_csv(path):
            if row.get("risk") not in {"high_risk", "low_risk"}:
                continue
            enriched = dict(row)
            for feature, mapper in ENRICHERS.items():
                if not str(enriched.get(feature, "")).strip():
                    enriched[feature] = mapper(enriched)[0]
            rows.append(enriched)
            if max_rows is not None and len(rows) >= max_rows:
                return rows
    return rows


def _label(row: dict[str, str]) -> int:
    return 1 if row.get("risk") == "high_risk" else 0


def _split_rows(rows: list[dict[str, str]], test_fraction: float) -> tuple[list[dict[str, str]], list[dict[str, str]]]:
    ordered = sorted(
        rows,
        key=lambda row: (
            str(row.get("source_dataset", "")),
            str(row.get("loan_age_months", "")),
            str(row.get("source_record_id", "")),
        ),
    )
    split_idx = int(len(ordered) * (1.0 - test_fraction))
    split_idx = max(1, min(split_idx, len(ordered) - 1))
    return ordered[:split_idx], ordered[split_idx:]


def _brier_score(y_true: list[int], y_score: list[float]) -> float:
    if not y_true:
        return 0.0
    return float(np.mean([(score - label) ** 2 for label, score in zip(y_true, y_score)]))


def _roc_auc(y_true: list[int], y_score: list[float]) -> float | None:
    n = len(y_true)
    n_pos = sum(y_true)
    n_neg = n - n_pos
    if n == 0 or n_pos == 0 or n_neg == 0:
        return None
    ranked = sorted(zip(y_score, y_true), key=lambda item: item[0])
    rank_sum_pos = 0.0
    i = 0
    rank = 1
    while i < n:
        j = i
        score = ranked[i][0]
        while j < n and ranked[j][0] == score:
            j += 1
        avg_rank = (rank + rank + (j - i) - 1) / 2.0
        rank_sum_pos += avg_rank * sum(label for _, label in ranked[i:j])
        rank += j - i
        i = j
    return float((rank_sum_pos - (n_pos * (n_pos + 1) / 2.0)) / (n_pos * n_neg))


def _pr_auc(y_true: list[int], y_score: list[float]) -> float | None:
    n_pos = sum(y_true)
    if n_pos == 0:
        return None
    pairs = sorted(zip(y_score, y_true), key=lambda item: item[0], reverse=True)
    tp = 0
    fp = 0
    prev_recall = 0.0
    area = 0.0
    for _, label in pairs:
        if label:
            tp += 1
        else:
            fp += 1
        recall = tp / n_pos
        precision = tp / (tp + fp)
        area += (recall - prev_recall) * precision
        prev_recall = recall
    return float(area)


def _calibration_buckets(y_true: list[int], y_score: list[float], bucket_count: int = 5) -> list[dict[str, Any]]:
    buckets: list[dict[str, Any]] = []
    for idx in range(bucket_count):
        low = idx / bucket_count
        high = (idx + 1) / bucket_count
        selected = [
            (label, score)
            for label, score in zip(y_true, y_score)
            if (score >= low and (score < high or idx == bucket_count - 1))
        ]
        if not selected:
            buckets.append({"bucket": f"{low:.1f}-{high:.1f}", "count": 0, "mean_score": None, "event_rate": None})
            continue
        labels = [label for label, _ in selected]
        scores = [score for _, score in selected]
        buckets.append(
            {
                "bucket": f"{low:.1f}-{high:.1f}",
                "count": len(selected),
                "mean_score": float(np.mean(scores)),
                "event_rate": float(np.mean(labels)),
            }
        )
    return buckets


def _metrics(rows: list[dict[str, str]], scores: list[float]) -> dict[str, Any]:
    y_true = [_label(row) for row in rows]
    positives = int(sum(y_true))
    return {
        "rows": len(rows),
        "positives": positives,
        "prevalence": (positives / len(rows)) if rows else 0.0,
        "auc": _roc_auc(y_true, scores),
        "pr_auc": _pr_auc(y_true, scores),
        "brier_score": _brier_score(y_true, scores),
        "calibration_buckets": _calibration_buckets(y_true, scores),
    }


def _build_stump_ensemble(rows: list[dict[str, str]], feature_names: tuple[str, ...], max_stumps: int) -> list[dict[str, Any]]:
    labels = np.asarray([_label(row) for row in rows], dtype=float)
    base_rate = float((labels.sum() + 1.0) / (len(labels) + 2.0))
    candidates: list[dict[str, Any]] = []

    for feature in feature_names:
        values = sorted({str(row.get(feature, "")) for row in rows if str(row.get(feature, "")).strip()})
        for value in values:
            left_labels = [label for row, label in zip(rows, labels) if str(row.get(feature, "")) == value]
            right_labels = [label for row, label in zip(rows, labels) if str(row.get(feature, "")) != value]
            if not left_labels or not right_labels:
                continue
            left_rate = float((sum(left_labels) + 1.0) / (len(left_labels) + 2.0))
            right_rate = float((sum(right_labels) + 1.0) / (len(right_labels) + 2.0))
            predictions = np.asarray(
                [left_rate if str(row.get(feature, "")) == value else right_rate for row in rows],
                dtype=float,
            )
            baseline = np.full_like(predictions, base_rate)
            improvement = float(np.mean((labels - baseline) ** 2) - np.mean((labels - predictions) ** 2))
            candidates.append(
                {
                    "feature": feature,
                    "value": value,
                    "match_rate": left_rate,
                    "other_rate": right_rate,
                    "improvement": improvement,
                }
            )

    selected = sorted(candidates, key=lambda item: item["improvement"], reverse=True)[:max_stumps]
    if not selected:
        selected = [{"feature": feature_names[0], "value": "", "match_rate": base_rate, "other_rate": base_rate, "improvement": 0.0}]
    return selected


class OpaqueStumpEnsemble:
    def __init__(self, stumps: list[dict[str, Any]]) -> None:
        self.stumps = stumps

    def predict(self, row: dict[str, Any]) -> float:
        scores = [
            stump["match_rate"] if str(row.get(stump["feature"], "")) == stump["value"] else stump["other_rate"]
            for stump in self.stumps
        ]
        return float(max(0.0, min(1.0, np.mean(scores))))


class LinearSurrogate:
    def __init__(self, feature_names: tuple[str, ...], categories: dict[str, list[str]], weights: np.ndarray) -> None:
        self.feature_names = feature_names
        self.categories = categories
        self.weights = weights

    @staticmethod
    def _matrix(rows: list[dict[str, Any]], feature_names: tuple[str, ...], categories: dict[str, list[str]]) -> np.ndarray:
        matrix: list[list[float]] = []
        for row in rows:
            values = [1.0]
            for feature in feature_names:
                token = str(row.get(feature, ""))
                values.extend(1.0 if token == category else 0.0 for category in categories[feature])
            matrix.append(values)
        return np.asarray(matrix, dtype=float)

    @classmethod
    def fit(cls, rows: list[dict[str, Any]], feature_names: tuple[str, ...], targets: list[float]) -> "LinearSurrogate":
        categories = {
            feature: sorted({str(row.get(feature, "")) for row in rows if str(row.get(feature, "")).strip()})
            for feature in feature_names
        }
        x = cls._matrix(rows, feature_names, categories)
        y = np.asarray(targets, dtype=float)
        weights = np.linalg.lstsq(x, y, rcond=None)[0]
        return cls(feature_names, categories, weights)

    def predict(self, row: dict[str, Any]) -> float:
        x = self._matrix([row], self.feature_names, self.categories)
        return float(max(0.0, min(1.0, x.dot(self.weights)[0])))


def _write_report(path: Path, summary: dict[str, Any]) -> None:
    metrics = summary["opaque_model_metrics"]
    fidelity = summary["surrogate_fidelity"]
    lines = [
        "# Opaque Mortgage Benchmark Report",
        "",
        f"Generated: {summary['generated_at_utc']}",
        "",
        "## Scope",
        "",
        "Real opaque-model benchmark on normalized public mortgage rows.",
        "This is validated surrogate governance evidence, not automatic causal truth.",
        "",
        "## Data",
        "",
        f"- rows_loaded: {summary['rows_loaded']}",
        f"- train_rows: {summary['train_rows']}",
        f"- test_rows: {summary['test_rows']}",
        f"- features: `{', '.join(summary['features'])}`",
        f"- excluded leakage features: `{', '.join(summary['excluded_leakage_features'])}`",
        "",
        "## Opaque model outcome metrics",
        "",
        f"- positives: {metrics['positives']}",
        f"- prevalence: {metrics['prevalence']:.6f}",
        f"- AUC: {metrics['auc']}",
        f"- PR-AUC: {metrics['pr_auc']}",
        f"- Brier: {metrics['brier_score']:.6f}",
        "",
        "## Surrogate governance metrics",
        "",
        f"- approximation_label: {fidelity['approximation_label']}",
        f"- mean_absolute_error: {fidelity['mean_absolute_error']}",
        f"- root_mean_squared_error: {fidelity['root_mean_squared_error']}",
        f"- classification_agreement: {fidelity['classification_agreement']}",
        f"- stability_label: {summary['surrogate_stability']['approximation_label']}",
        f"- counterfactual_consistency: {summary['counterfactual_consistency']['approximation_label']}",
        f"- proxy_findings: {len(summary['proxy_findings'])}",
        "",
        "## Boundary",
        "",
        "The benchmark checks whether a surrogate can approximate and audit an opaque model's behavior.",
        "It does not prove the extracted graph is the true causal graph.",
    ]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run opaque-model surrogate benchmark on normalized mortgage rows.")
    parser.add_argument("--input", action="append", required=True, help="Normalized mortgage CSV input. May be repeated.")
    parser.add_argument(
        "--output-dir",
        default=str(ROOT / "validation" / "outputs" / "opaque_mortgage_benchmark"),
        help="Output directory for benchmark artifacts.",
    )
    parser.add_argument("--max-rows", type=int, default=100000)
    parser.add_argument("--test-fraction", type=float, default=0.3)
    parser.add_argument("--max-stumps", type=int, default=24)
    return parser


def main() -> int:
    args = build_parser().parse_args()
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    _progress("loading normalized mortgage rows")
    rows = _load_rows([Path(path) for path in args.input], args.max_rows)
    if len(rows) < 4:
        raise ValueError("At least four labeled rows are required for opaque benchmark")

    train_rows, test_rows = _split_rows(rows, args.test_fraction)
    _progress("training deterministic opaque stump ensemble")
    opaque_model = OpaqueStumpEnsemble(_build_stump_ensemble(train_rows, BENCHMARK_FEATURES, args.max_stumps))
    train_opaque_scores = [opaque_model.predict(row) for row in train_rows]
    surrogate = LinearSurrogate.fit(train_rows, BENCHMARK_FEATURES, train_opaque_scores)

    _progress("scoring holdout rows")
    opaque_scores = [opaque_model.predict(row) for row in test_rows]
    opaque_metrics = _metrics(test_rows, opaque_scores)

    _progress("running surrogate diagnostics")
    fidelity_report = evaluate_surrogate_fidelity(test_rows, opaque_model.predict, surrogate.predict)
    fidelity = fidelity_report.to_dict()
    fidelity["local_absolute_error_count"] = len(fidelity.get("local_absolute_errors", []))
    fidelity["local_absolute_errors_sample"] = fidelity.get("local_absolute_errors", [])[:20]
    fidelity.pop("local_absolute_errors", None)
    stability = evaluate_surrogate_stability(
        test_rows,
        opaque_model.predict,
        feature_names=BENCHMARK_FEATURES,
        fold_count=4,
        top_k=4,
    ).to_dict()
    proxies = [
        finding.to_dict()
        for finding in detect_proxy_features(
            test_rows,
            candidate_features=BENCHMARK_FEATURES,
            sensitive_features=[feature for feature in ("race", "sex", "segment") if any(row.get(feature) for row in test_rows)],
            association_threshold=0.8,
        )
    ]
    consistency = evaluate_counterfactual_consistency(
        test_rows[: min(len(test_rows), 500)],
        opaque_model.predict,
        surrogate.predict,
        probes=[
            CounterfactualProbe("ltv_risk", "elevated"),
            CounterfactualProbe("dti_risk", "elevated"),
            CounterfactualProbe("fico_risk", "elevated"),
            CounterfactualProbe("occupancy_risk", "elevated"),
        ],
    ).to_dict()
    dag = construct_surrogate_dag(
        test_rows,
        opaque_model.predict,
        feature_names=BENCHMARK_FEATURES,
        dag_id="opaque_mortgage_surrogate_dag",
    ).to_dict()
    surrogate_dag = construct_surrogate_dag(
        test_rows,
        opaque_model.predict,
        feature_names=BENCHMARK_FEATURES,
        dag_id="opaque_mortgage_surrogate_dag",
    )
    audit_trace = build_opaque_model_audit_trace(
        row=test_rows[0],
        opaque_predict=opaque_model.predict,
        surrogate_predict=surrogate.predict,
        surrogate_dag=surrogate_dag,
        fidelity_report=fidelity_report,
        proxy_findings=[],
    )

    summary = _round(
        {
            "status": "completed",
            "generated_at_utc": _utc_now(),
            "rows_loaded": len(rows),
            "train_rows": len(train_rows),
            "test_rows": len(test_rows),
            "mapped_features": list(ALL_MAPPED_FEATURES),
            "features": list(BENCHMARK_FEATURES),
            "excluded_leakage_features": list(EXCLUDED_LEAKAGE_FEATURES),
            "opaque_model_type": "deterministic_stump_ensemble",
            "opaque_model_metrics": opaque_metrics,
            "surrogate_fidelity": fidelity,
            "surrogate_stability": stability,
            "counterfactual_consistency": consistency,
            "proxy_findings": proxies,
            "surrogate_dag": dag,
            "sample_audit_trace": audit_trace,
            "boundary": "validated surrogate governance evidence; not guaranteed true causal reasoning",
        }
    )

    summary_path = output_dir / "opaque_mortgage_benchmark_summary.json"
    report_path = output_dir / "opaque_mortgage_benchmark_report.generated.md"
    summary_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    _write_report(report_path, summary)
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
