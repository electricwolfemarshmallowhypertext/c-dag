"""Surrogate governance checks for opaque-model decision traces.

These helpers support audit evidence for extracted or surrogate DAGs.
They do not prove that a surrogate graph is the true causal structure of
an opaque model.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Callable, Mapping, Sequence
from dataclasses import asdict, dataclass
from typing import Any

import numpy as np

Row = Mapping[str, Any]
PredictionFunction = Callable[[Row], float]


SURROGATE_EVIDENCE_BOUNDARY = (
    "validated surrogate governance evidence; not guaranteed true causal reasoning"
)


def _round_nested(value: Any, *, decimals: int = 6) -> Any:
    if isinstance(value, float):
        rounded = round(value, decimals)
        if rounded == 0:
            return 0.0
        return rounded
    if isinstance(value, dict):
        return {key: _round_nested(item, decimals=decimals) for key, item in value.items()}
    if isinstance(value, list):
        return [_round_nested(item, decimals=decimals) for item in value]
    return value


def _require_rows(rows: Sequence[Row]) -> None:
    if not rows:
        raise ValueError("rows must not be empty")


def _encode_values(values: Sequence[Any]) -> np.ndarray:
    encoded: list[float] = []
    categories: dict[str, int] = {}

    for value in values:
        if value is None or value == "":
            encoded.append(np.nan)
            continue
        try:
            encoded.append(float(value))
            continue
        except (TypeError, ValueError):
            key = str(value)
            if key not in categories:
                categories[key] = len(categories)
            encoded.append(float(categories[key]))

    arr = np.asarray(encoded, dtype=float)
    if np.isnan(arr).any():
        fill = float(np.nanmean(arr)) if not np.isnan(arr).all() else 0.0
        arr = np.nan_to_num(arr, nan=fill)
    return arr


def _feature_vector(rows: Sequence[Row], feature_name: str) -> np.ndarray:
    return _encode_values([row.get(feature_name) for row in rows])


def _safe_corr(left: np.ndarray, right: np.ndarray) -> float:
    if left.size != right.size:
        raise ValueError("correlation inputs must have the same length")
    if left.size < 2:
        return 0.0
    if float(np.std(left)) == 0.0 or float(np.std(right)) == 0.0:
        return 0.0
    corr = float(np.corrcoef(left, right)[0, 1])
    if np.isnan(corr):
        return 0.0
    return corr


def _predictions(predict: PredictionFunction, rows: Sequence[Row]) -> np.ndarray:
    return np.asarray([float(predict(row)) for row in rows], dtype=float)


@dataclass(frozen=True)
class SurrogateEdge:
    source: str
    target: str
    weight: float
    evidence: str

    def to_dict(self) -> dict[str, Any]:
        return _round_nested(asdict(self))


@dataclass(frozen=True)
class SurrogateDAG:
    dag_id: str
    target_node: str
    feature_nodes: tuple[str, ...]
    edges: tuple[SurrogateEdge, ...]
    extraction_method: str
    boundary: str = SURROGATE_EVIDENCE_BOUNDARY

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["edges"] = [edge.to_dict() for edge in self.edges]
        return _round_nested(payload)


@dataclass(frozen=True)
class FidelityReport:
    row_count: int
    mean_absolute_error: float
    root_mean_squared_error: float
    max_absolute_error: float
    pearson_correlation: float
    classification_agreement: float
    local_absolute_errors: tuple[float, ...]
    approximation_label: str
    boundary: str = SURROGATE_EVIDENCE_BOUNDARY

    def to_dict(self) -> dict[str, Any]:
        return _round_nested(asdict(self))


@dataclass(frozen=True)
class StabilityReport:
    row_count: int
    fold_count: int
    top_k: int
    mean_top_feature_overlap: float
    stable_features: tuple[str, ...]
    approximation_label: str
    boundary: str = SURROGATE_EVIDENCE_BOUNDARY

    def to_dict(self) -> dict[str, Any]:
        return _round_nested(asdict(self))


@dataclass(frozen=True)
class ProxyFinding:
    feature: str
    sensitive_feature: str
    association: float
    method: str
    flag: str

    def to_dict(self) -> dict[str, Any]:
        return _round_nested(asdict(self))


@dataclass(frozen=True)
class CounterfactualProbe:
    feature: str
    intervention_value: Any
    baseline_value: Any | None = None


@dataclass(frozen=True)
class CounterfactualConsistencyReport:
    probe_count: int
    comparable_effects: int
    sign_agreement_rate: float
    mean_delta_error: float
    approximation_label: str
    boundary: str = SURROGATE_EVIDENCE_BOUNDARY

    def to_dict(self) -> dict[str, Any]:
        return _round_nested(asdict(self))


def construct_surrogate_dag(
    rows: Sequence[Row],
    opaque_predict: PredictionFunction,
    *,
    feature_names: Sequence[str],
    target_node: str = "opaque_model_score",
    dag_id: str = "surrogate_dag",
    min_feature_association: float = 0.05,
    min_edge_association: float = 0.35,
) -> SurrogateDAG:
    """Build a compact surrogate DAG from model-behavior associations."""

    _require_rows(rows)
    if not feature_names:
        raise ValueError("feature_names must not be empty")

    target = _predictions(opaque_predict, rows)
    feature_scores = {
        feature: abs(_safe_corr(_feature_vector(rows, feature), target))
        for feature in feature_names
    }

    edges: list[SurrogateEdge] = []
    for feature, score in sorted(feature_scores.items(), key=lambda item: item[1], reverse=True):
        if score >= min_feature_association:
            edges.append(
                SurrogateEdge(
                    source=feature,
                    target=target_node,
                    weight=float(score),
                    evidence="feature association with opaque model score",
                )
            )

    for left_idx, left in enumerate(feature_names):
        for right in feature_names[left_idx + 1 :]:
            association = abs(_safe_corr(_feature_vector(rows, left), _feature_vector(rows, right)))
            if association < min_edge_association:
                continue
            source, target_feature = (
                (left, right)
                if feature_scores.get(left, 0.0) >= feature_scores.get(right, 0.0)
                else (right, left)
            )
            edges.append(
                SurrogateEdge(
                    source=source,
                    target=target_feature,
                    weight=float(association),
                    evidence="feature association used as candidate surrogate dependency",
                )
            )

    return SurrogateDAG(
        dag_id=dag_id,
        target_node=target_node,
        feature_nodes=tuple(feature_names),
        edges=tuple(edges),
        extraction_method="association-ranked surrogate graph from opaque model scores",
    )


def classify_fidelity(
    *,
    classification_agreement: float,
    mean_absolute_error: float,
) -> str:
    if classification_agreement >= 0.95 and mean_absolute_error <= 0.03:
        return "high_fidelity_surrogate"
    if classification_agreement >= 0.85 and mean_absolute_error <= 0.08:
        return "moderate_fidelity_surrogate"
    return "low_fidelity_surrogate"


def evaluate_surrogate_fidelity(
    rows: Sequence[Row],
    opaque_predict: PredictionFunction,
    surrogate_predict: PredictionFunction,
    *,
    threshold: float = 0.5,
) -> FidelityReport:
    """Compare opaque-model and surrogate predictions globally and locally."""

    _require_rows(rows)
    opaque = _predictions(opaque_predict, rows)
    surrogate = _predictions(surrogate_predict, rows)
    errors = np.abs(opaque - surrogate)
    agreement = np.mean((opaque >= threshold) == (surrogate >= threshold))
    mae = float(np.mean(errors))

    return FidelityReport(
        row_count=len(rows),
        mean_absolute_error=mae,
        root_mean_squared_error=float(np.sqrt(np.mean((opaque - surrogate) ** 2))),
        max_absolute_error=float(np.max(errors)),
        pearson_correlation=_safe_corr(opaque, surrogate),
        classification_agreement=float(agreement),
        local_absolute_errors=tuple(float(value) for value in errors),
        approximation_label=classify_fidelity(
            classification_agreement=float(agreement),
            mean_absolute_error=mae,
        ),
    )


def evaluate_surrogate_stability(
    rows: Sequence[Row],
    opaque_predict: PredictionFunction,
    *,
    feature_names: Sequence[str],
    fold_count: int = 4,
    top_k: int = 3,
) -> StabilityReport:
    """Check whether top surrogate drivers remain stable across folds."""

    _require_rows(rows)
    if fold_count < 2:
        raise ValueError("fold_count must be at least 2")
    if top_k < 1:
        raise ValueError("top_k must be at least 1")

    folds = [list(rows)[idx::fold_count] for idx in range(fold_count)]
    rankings: list[tuple[str, ...]] = []
    for fold in folds:
        if len(fold) < 2:
            continue
        target = _predictions(opaque_predict, fold)
        scores = {
            feature: abs(_safe_corr(_feature_vector(fold, feature), target))
            for feature in feature_names
        }
        rankings.append(
            tuple(
                feature
                for feature, _ in sorted(scores.items(), key=lambda item: item[1], reverse=True)[
                    :top_k
                ]
            )
        )

    if len(rankings) < 2:
        mean_overlap = 0.0
    else:
        overlaps: list[float] = []
        for idx, ranking in enumerate(rankings):
            for other in rankings[idx + 1 :]:
                left = set(ranking)
                right = set(other)
                overlaps.append(len(left & right) / len(left | right) if left | right else 0.0)
        mean_overlap = float(np.mean(overlaps)) if overlaps else 0.0

    top_counts = Counter(feature for ranking in rankings for feature in ranking)
    min_presence = max(1, len(rankings) // 2)
    stable = tuple(
        feature
        for feature, _ in sorted(top_counts.items(), key=lambda item: (-item[1], item[0]))
        if top_counts[feature] >= min_presence
    )
    label = (
        "stable_surrogate_drivers"
        if mean_overlap >= 0.6
        else "unstable_surrogate_drivers"
    )

    return StabilityReport(
        row_count=len(rows),
        fold_count=fold_count,
        top_k=top_k,
        mean_top_feature_overlap=mean_overlap,
        stable_features=stable,
        approximation_label=label,
    )


def detect_proxy_features(
    rows: Sequence[Row],
    *,
    candidate_features: Sequence[str],
    sensitive_features: Sequence[str],
    association_threshold: float = 0.8,
) -> list[ProxyFinding]:
    """Flag candidate features that strongly track sensitive attributes."""

    _require_rows(rows)
    findings: list[ProxyFinding] = []
    for sensitive_feature in sensitive_features:
        sensitive_vector = _feature_vector(rows, sensitive_feature)
        for candidate in candidate_features:
            if candidate == sensitive_feature:
                continue
            association = abs(_safe_corr(_feature_vector(rows, candidate), sensitive_vector))
            if association >= association_threshold:
                findings.append(
                    ProxyFinding(
                        feature=candidate,
                        sensitive_feature=sensitive_feature,
                        association=float(association),
                        method="absolute encoded Pearson association",
                        flag="potential_proxy",
                    )
                )
    return findings


def evaluate_counterfactual_consistency(
    rows: Sequence[Row],
    opaque_predict: PredictionFunction,
    surrogate_predict: PredictionFunction,
    *,
    probes: Sequence[CounterfactualProbe],
    zero_tolerance: float = 1e-9,
) -> CounterfactualConsistencyReport:
    """Compare opaque and surrogate counterfactual effect directions."""

    _require_rows(rows)
    if not probes:
        raise ValueError("probes must not be empty")

    sign_matches = 0
    comparable = 0
    delta_errors: list[float] = []

    for row in rows:
        baseline = dict(row)
        for probe in probes:
            if probe.baseline_value is not None:
                baseline[probe.feature] = probe.baseline_value
            intervention = dict(baseline)
            intervention[probe.feature] = probe.intervention_value

            opaque_delta = float(opaque_predict(intervention) - opaque_predict(baseline))
            surrogate_delta = float(surrogate_predict(intervention) - surrogate_predict(baseline))
            delta_errors.append(abs(opaque_delta - surrogate_delta))

            if abs(opaque_delta) <= zero_tolerance and abs(surrogate_delta) <= zero_tolerance:
                sign_matches += 1
                comparable += 1
                continue
            if abs(opaque_delta) <= zero_tolerance or abs(surrogate_delta) <= zero_tolerance:
                comparable += 1
                continue
            comparable += 1
            if np.sign(opaque_delta) == np.sign(surrogate_delta):
                sign_matches += 1

    agreement = sign_matches / comparable if comparable else 0.0
    mean_delta_error = float(np.mean(delta_errors)) if delta_errors else 0.0
    label = (
        "counterfactual_direction_consistent"
        if agreement >= 0.9
        else "counterfactual_direction_unstable"
    )
    return CounterfactualConsistencyReport(
        probe_count=len(probes),
        comparable_effects=comparable,
        sign_agreement_rate=float(agreement),
        mean_delta_error=mean_delta_error,
        approximation_label=label,
    )


def build_opaque_model_audit_trace(
    *,
    row: Row,
    opaque_predict: PredictionFunction,
    surrogate_predict: PredictionFunction,
    surrogate_dag: SurrogateDAG,
    fidelity_report: FidelityReport,
    proxy_findings: Sequence[ProxyFinding] | None = None,
    decision_threshold: float = 0.5,
) -> dict[str, Any]:
    """Create an audit trace for an opaque model explained by a surrogate DAG."""

    opaque_score = float(opaque_predict(row))
    surrogate_score = float(surrogate_predict(row))
    local_error = abs(opaque_score - surrogate_score)
    top_edges = sorted(surrogate_dag.edges, key=lambda edge: abs(edge.weight), reverse=True)

    trace = {
        "trace_type": "opaque_model_surrogate_trace",
        "evidence_type": "validated_surrogate_governance_evidence",
        "boundary": SURROGATE_EVIDENCE_BOUNDARY,
        "input_row": dict(row),
        "opaque_prediction": opaque_score,
        "surrogate_prediction": surrogate_score,
        "local_absolute_error": float(local_error),
        "decision_threshold": float(decision_threshold),
        "opaque_decision": "positive" if opaque_score >= decision_threshold else "negative",
        "surrogate_decision": "positive" if surrogate_score >= decision_threshold else "negative",
        "approximation_label": fidelity_report.approximation_label,
        "surrogate_dag": surrogate_dag.to_dict(),
        "surrogate_pathway": [edge.to_dict() for edge in top_edges],
        "proxy_findings": [
            finding.to_dict() for finding in (proxy_findings or [])
        ],
        "validation_status": {
            "fidelity_evaluated": True,
            "automatic_truth_claim": False,
            "requires_human_review": True,
        },
    }
    return _round_nested(trace)
