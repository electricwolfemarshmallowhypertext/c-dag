"""Run public holdout validation on institutional mortgage performance data.

WARNING:
This is public holdout validation on institutional mortgage performance data.
It is not production validation, not credit eligibility decisioning, and not regulatory compliance proof.
"""

from __future__ import annotations

import argparse
import csv
from datetime import datetime, timezone
import json
from pathlib import Path
import sys
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from causal_credit_risk.audit_chain import build_audit_chain_record, verify_audit_chain
from causal_credit_risk.batch import run_batch_csv
from causal_credit_risk.cli import run_decision
from causal_credit_risk.cpd_estimation import build_draft_model_config
from causal_credit_risk.inference import ExactInferenceEngine
from causal_credit_risk.model import CausalDAGModel
from causal_credit_risk.policy import DecisionPolicy, validate_policy_against_model
from causal_credit_risk.replay import replay_from_audit_payload
from causal_credit_risk.schemas import PolicyConfig


REQUIRED_COLUMNS: tuple[str, ...] = (
    "source_dataset",
    "source_record_id",
    "tenure",
    "utilization",
    "income",
    "dsc",
    "risk",
    "segment",
)

MORTGAGE_PERFORMANCE_DATASETS: set[str] = {
    "freddie_mac_sf_loan_level",
    "fannie_mae_sf_performance",
    "fhfa_pudb",
}


def _utc_now() -> str:
    return datetime.now(tz=timezone.utc).isoformat(timespec="seconds")


def _progress(message: str) -> None:
    print(f"[progress] {message}", file=sys.stderr, flush=True)


def _to_int(value: str | None) -> int | None:
    if value is None:
        return None
    token = str(value).strip()
    if token == "":
        return None
    try:
        return int(float(token))
    except ValueError:
        return None


def _read_csv_rows(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as fh:
        reader = csv.DictReader(fh)
        if reader.fieldnames is None:
            raise ValueError(f"Missing header row in CSV: {path}")
        return [dict(row) for row in reader]


def _write_csv(path: Path, fieldnames: list[str], rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow({key: row.get(key, "") for key in fieldnames})


def _filter_valid_rows(rows: list[dict[str, str]]) -> tuple[list[dict[str, str]], int]:
    valid: list[dict[str, str]] = []
    rejected = 0
    for row in rows:
        missing = [col for col in REQUIRED_COLUMNS if not str(row.get(col, "")).strip()]
        if missing:
            rejected += 1
            continue
        if row["risk"] not in {"high_risk", "low_risk"}:
            rejected += 1
            continue
        valid.append(row)
    return valid, rejected


def _fannie_sort_key(row: dict[str, str], original_index: int) -> tuple[int, str, int]:
    age = _to_int(row.get("loan_age_months"))
    age_key = age if age is not None else -999999
    return (age_key, str(row.get("source_record_id", "")), original_index)


def _age_bucket(age: int | None) -> str:
    if age is None:
        return "unknown"
    if age < 12:
        return "0-11"
    if age < 24:
        return "12-23"
    if age < 36:
        return "24-35"
    if age < 60:
        return "36-59"
    if age < 120:
        return "60-119"
    return "120+"


def _profile_rows(rows: list[dict[str, str]]) -> dict[str, Any]:
    profile: dict[str, Any] = {"rows": len(rows), "by_source": {}, "by_age_bucket": {}}
    for row in rows:
        src = row.get("source_dataset", "unknown")
        src_entry = profile["by_source"].setdefault(src, {"rows": 0, "high_risk": 0})
        src_entry["rows"] += 1
        if row.get("risk") == "high_risk":
            src_entry["high_risk"] += 1

        bucket = _age_bucket(_to_int(row.get("loan_age_months")))
        bucket_entry = profile["by_age_bucket"].setdefault(bucket, {"rows": 0, "high_risk": 0})
        bucket_entry["rows"] += 1
        if row.get("risk") == "high_risk":
            bucket_entry["high_risk"] += 1

    for section in ("by_source", "by_age_bucket"):
        for key, value in profile[section].items():
            rows_n = int(value["rows"])
            value["prevalence"] = (value["high_risk"] / rows_n) if rows_n else 0.0
    return profile


def _split_holdout_rows(
    rows: list[dict[str, str]],
    train_fraction: float,
    matured_min_loan_age: int,
) -> tuple[list[dict[str, str]], list[dict[str, str]], dict[str, Any]]:
    freddie_rows = [row for row in rows if row.get("source_dataset") == "freddie_mac_sf_loan_level"]
    fannie_rows = [row for row in rows if row.get("source_dataset") == "fannie_mae_sf_performance"]
    other_rows = [
        row
        for row in rows
        if row.get("source_dataset") not in {"freddie_mac_sf_loan_level", "fannie_mae_sf_performance"}
    ]

    freddie_mature_test: list[dict[str, str]] = []
    freddie_train: list[dict[str, str]] = []
    for row in freddie_rows:
        age = _to_int(row.get("loan_age_months"))
        if age is not None and age >= matured_min_loan_age:
            freddie_mature_test.append(row)
        else:
            freddie_train.append(row)

    if freddie_mature_test:
        train_rows = freddie_train + fannie_rows + other_rows
        test_rows = freddie_mature_test
        split_meta = {
            "strategy": "matured_freddie_holdout_by_loan_age_proxy",
            "matured_min_loan_age": matured_min_loan_age,
            "notes": (
                "Training uses earlier/mixed rows (Freddie age proxy below threshold plus all Fannie). "
                "Holdout uses matured Freddie rows at or above threshold as later-performance proxy."
            ),
            "freddie_total_rows": len(freddie_rows),
            "freddie_train_rows": len(freddie_train),
            "freddie_test_rows": len(freddie_mature_test),
            "fannie_train_rows": len(fannie_rows),
            "other_train_rows": len(other_rows),
        }
        return train_rows, test_rows, split_meta

    indexed_fannie = list(enumerate(fannie_rows))
    indexed_fannie.sort(key=lambda item: _fannie_sort_key(item[1], item[0]))
    ordered_fannie = [row for _, row in indexed_fannie]
    split_idx = int(len(ordered_fannie) * train_fraction)
    if len(ordered_fannie) >= 2:
        split_idx = max(1, min(split_idx, len(ordered_fannie) - 1))
    else:
        split_idx = len(ordered_fannie)

    train_rows = freddie_rows + ordered_fannie[:split_idx] + other_rows
    test_rows = ordered_fannie[split_idx:]
    split_meta = {
        "strategy": "fallback_fannie_proxy_split",
        "train_fraction": train_fraction,
        "matured_min_loan_age": matured_min_loan_age,
        "notes": (
            "No matured Freddie test cohort was available. "
            "Fallback split uses Fannie loan_age_months proxy for deterministic holdout."
        ),
        "freddie_train_rows": len(freddie_rows),
        "fannie_total_rows": len(ordered_fannie),
        "fannie_train_rows": split_idx,
        "fannie_test_rows": len(ordered_fannie) - split_idx,
        "other_train_rows": len(other_rows),
    }
    return train_rows, test_rows, split_meta


def _brier_score(y_true: list[int], y_score: list[float]) -> float:
    if not y_true:
        return 0.0
    total = 0.0
    for label, score in zip(y_true, y_score):
        total += (score - float(label)) ** 2
    return total / len(y_true)


def _roc_auc(y_true: list[int], y_score: list[float]) -> float | None:
    n = len(y_true)
    if n == 0:
        return None
    n_pos = sum(y_true)
    n_neg = n - n_pos
    if n_pos == 0 or n_neg == 0:
        return None

    ranked = sorted(zip(y_score, y_true), key=lambda item: item[0])
    rank_sum_pos = 0.0
    i = 0
    rank = 1
    while i < n:
        j = i
        score_val = ranked[i][0]
        while j < n and ranked[j][0] == score_val:
            j += 1
        avg_rank = (rank + (rank + (j - i) - 1)) / 2.0
        pos_in_tie = sum(label for _, label in ranked[i:j])
        rank_sum_pos += avg_rank * pos_in_tie
        rank += (j - i)
        i = j

    auc = (rank_sum_pos - (n_pos * (n_pos + 1) / 2.0)) / (n_pos * n_neg)
    return float(auc)


def _pr_auc(y_true: list[int], y_score: list[float]) -> float | None:
    n_pos = sum(y_true)
    if n_pos == 0:
        return None
    pairs = sorted(zip(y_score, y_true), key=lambda item: item[0], reverse=True)
    tp = 0
    fp = 0
    prev_recall = 0.0
    ap = 0.0
    for _, label in pairs:
        if label == 1:
            tp += 1
        else:
            fp += 1
        recall = tp / n_pos
        precision = tp / (tp + fp)
        ap += (recall - prev_recall) * precision
        prev_recall = recall
    return float(ap)


def _calibration_buckets(y_true: list[int], y_score: list[float], bucket_count: int = 10) -> list[dict[str, Any]]:
    buckets: list[dict[str, Any]] = []
    for idx in range(bucket_count):
        start = idx / bucket_count
        end = (idx + 1) / bucket_count
        members: list[tuple[int, float]] = []
        for label, score in zip(y_true, y_score):
            in_bucket = score >= start and (score < end or (idx == bucket_count - 1 and score <= end))
            if in_bucket:
                members.append((label, score))
        count = len(members)
        if count == 0:
            avg_pred = None
            obs_rate = None
        else:
            avg_pred = sum(score for _, score in members) / count
            obs_rate = sum(label for label, _ in members) / count
        buckets.append(
            {
                "bucket": idx + 1,
                "range_start": start,
                "range_end": end,
                "count": count,
                "avg_pred": avg_pred,
                "observed_rate": obs_rate,
            }
        )
    return buckets


def _binary_confusion(y_true: list[int], y_score: list[float], threshold: float) -> dict[str, int]:
    tp = fp = tn = fn = 0
    for label, score in zip(y_true, y_score):
        pred_pos = score >= threshold
        if pred_pos and label == 1:
            tp += 1
        elif pred_pos and label == 0:
            fp += 1
        elif (not pred_pos) and label == 0:
            tn += 1
        else:
            fn += 1
    return {"tp": tp, "fp": fp, "tn": tn, "fn": fn}


def _decision_distribution(decisions: list[str]) -> dict[str, int]:
    counts = {"APPROVE": 0, "REVIEW": 0, "DECLINE": 0}
    for decision in decisions:
        if decision in counts:
            counts[decision] += 1
        else:
            counts[decision] = counts.get(decision, 0) + 1
    return counts


def _parse_features(raw: str) -> list[str]:
    features = []
    for token in raw.split(","):
        feature = token.strip()
        if feature and feature not in features:
            features.append(feature)
    if not features:
        raise ValueError("At least one evidence feature must be provided.")
    return features


def _score_rows(
    *,
    engine: ExactInferenceEngine,
    policy: DecisionPolicy,
    policy_config: PolicyConfig,
    rows: list[dict[str, str]],
    evidence_features: list[str],
) -> tuple[list[int], list[float], list[str], list[dict[str, Any]]]:
    y_true: list[int] = []
    y_score: list[float] = []
    decisions: list[str] = []
    scored_rows: list[dict[str, Any]] = []
    for row in rows:
        evidence = {feature: row[feature] for feature in evidence_features}
        score = engine.query_probability(
            policy_config.risk_outcome_node,
            policy_config.high_risk_state,
            evidence=evidence,
        )
        decision = policy.decide(score)
        label = 1 if row["risk"] == "high_risk" else 0
        y_true.append(label)
        y_score.append(score)
        decisions.append(decision)
        scored_rows.append(
            {
                "tenant_id": row.get("tenant_id", "default") or "default",
                "tenure": row["tenure"],
                "utilization": row["utilization"],
                "actual_risk": row["risk"],
                "predicted_probability": round(score, 6),
                "decision": decision,
            }
        )
    return y_true, y_score, decisions, scored_rows


def _build_metrics(
    *,
    y_true: list[int],
    y_score: list[float],
    decisions: list[str],
    policy_config: PolicyConfig,
) -> tuple[dict[str, Any], dict[str, int]]:
    decision_distribution = _decision_distribution(decisions)
    auc = _roc_auc(y_true, y_score)
    pr_auc = _pr_auc(y_true, y_score)
    brier = _brier_score(y_true, y_score)
    calibration = _calibration_buckets(y_true, y_score, bucket_count=10)
    confusion_decline = _binary_confusion(y_true, y_score, threshold=policy_config.decline_threshold)
    confusion_review_or_higher = _binary_confusion(y_true, y_score, threshold=policy_config.manual_review_lower)

    action_matrix = {
        "high_risk_actual": {"APPROVE": 0, "REVIEW": 0, "DECLINE": 0},
        "low_risk_actual": {"APPROVE": 0, "REVIEW": 0, "DECLINE": 0},
    }
    for label, decision in zip(y_true, decisions):
        key = "high_risk_actual" if label == 1 else "low_risk_actual"
        action_matrix[key][decision] += 1

    metrics = {
        "auc": auc,
        "pr_auc": pr_auc,
        "brier_score": brier,
        "calibration_buckets": calibration,
        "confusion_at_decline_threshold": {
            "threshold": policy_config.decline_threshold,
            **confusion_decline,
        },
        "confusion_at_manual_review_lower": {
            "threshold": policy_config.manual_review_lower,
            **confusion_review_or_higher,
        },
        "policy_action_confusion": action_matrix,
    }
    return metrics, decision_distribution


def _f1_at_threshold(y_true: list[int], y_score: list[float], threshold: float) -> float:
    tp = fp = fn = 0
    for label, score in zip(y_true, y_score):
        if score >= threshold:
            if label == 1:
                tp += 1
            else:
                fp += 1
        elif label == 1:
            fn += 1
    precision = tp / (tp + fp) if (tp + fp) else 0.0
    recall = tp / (tp + fn) if (tp + fn) else 0.0
    if precision + recall == 0.0:
        return 0.0
    return 2.0 * precision * recall / (precision + recall)


def _calibrate_policy_from_train(
    *,
    train_rows: list[dict[str, str]],
    engine: ExactInferenceEngine,
    base_policy: PolicyConfig,
    evidence_features: list[str],
    review_target_fraction: float = 0.15,
) -> PolicyConfig:
    if not 0.0 <= review_target_fraction < 1.0:
        raise ValueError("review_target_fraction must be in [0, 1).")
    y_true: list[int] = []
    y_score: list[float] = []
    for row in train_rows:
        evidence = {feature: row[feature] for feature in evidence_features}
        score = engine.query_probability(
            base_policy.risk_outcome_node,
            base_policy.high_risk_state,
            evidence=evidence,
        )
        y_score.append(score)
        y_true.append(1 if row["risk"] == "high_risk" else 0)

    rounded_scores = [round(score, 12) for score in y_score]
    unique_thresholds = sorted(set(rounded_scores))
    if not unique_thresholds:
        raise ValueError("No train scores available for policy calibration.")

    best_threshold = unique_thresholds[0]
    best_f1 = -1.0
    for threshold in unique_thresholds:
        f1 = _f1_at_threshold(y_true, rounded_scores, threshold)
        if f1 > best_f1:
            best_f1 = f1
            best_threshold = threshold

    lower_candidates = [value for value in unique_thresholds if value < best_threshold]
    if lower_candidates:
        best_lower = lower_candidates[0]
        best_distance = float("inf")
        for candidate in lower_candidates:
            review_count = sum(1 for score in rounded_scores if candidate <= score < best_threshold)
            review_fraction = review_count / len(rounded_scores)
            distance = abs(review_fraction - review_target_fraction)
            if distance < best_distance or (
                distance == best_distance and candidate > best_lower
            ):
                best_distance = distance
                best_lower = candidate
        manual_lower = best_lower
    else:
        manual_lower = best_threshold

    return PolicyConfig(
        policy_id=base_policy.policy_id,
        policy_version=f"{base_policy.policy_version}.holdout_calibrated",
        decline_threshold=float(best_threshold),
        manual_review_lower=float(manual_lower),
        manual_review_upper=float(best_threshold),
        risk_outcome_node=base_policy.risk_outcome_node,
        high_risk_state=base_policy.high_risk_state,
    )


def _write_report(
    *,
    report_path: Path,
    split_meta: dict[str, Any],
    train_rows: int,
    test_rows: int,
    rejected_rows: int,
    outcome_prevalence_train: float,
    outcome_prevalence_test: float,
    baseline_features: list[str],
    calibrated_features: list[str],
    policy_before: PolicyConfig,
    policy_after: PolicyConfig,
    decision_distribution_before: dict[str, int],
    decision_distribution_after: dict[str, int],
    metrics_before: dict[str, Any],
    metrics_after: dict[str, Any],
    replay_success_rate: float,
    audit_chain_valid: bool,
    evidence_pack_mode: str,
    evidence_pack_rows: int | None,
    data_profile: dict[str, Any],
    guardrails: dict[str, Any],
) -> None:
    lines = [
        "# Holdout Validation Report",
        "",
        f"Generated: {_utc_now()}",
        "",
        "## Scope",
        "",
        "Public holdout validation on institutional mortgage performance data.",
        "Not production validation. Not consumer credit eligibility. Not regulatory compliance proof.",
        "",
        "## Pipeline validation vs outcome validation",
        "",
        "- Pipeline validation: script execution, deterministic split, batch scoring, replay checks, and audit-chain verification.",
        "- Outcome validation: event-label metrics (AUC, PR-AUC, Brier, calibration, confusion) on held-out rows.",
        "",
        "## Train/Test split",
        "",
        json.dumps(split_meta, indent=2),
        "",
        "## Row counts",
        "",
        f"- train_rows: {train_rows}",
        f"- test_rows: {test_rows}",
        f"- rejected_rows: {rejected_rows}",
        "",
        "## Outcome prevalence",
        "",
        f"- train_high_risk_prevalence: {outcome_prevalence_train:.6f}",
        f"- test_high_risk_prevalence: {outcome_prevalence_test:.6f}",
        "",
        "## Scoring setup",
        "",
        f"- baseline_features: {', '.join(baseline_features)}",
        f"- calibrated_features: {', '.join(calibrated_features)}",
        "",
        "### Policy thresholds (before)",
        "",
        f"- decline_threshold: {policy_before.decline_threshold:.12f}",
        f"- manual_review_lower: {policy_before.manual_review_lower:.12f}",
        f"- manual_review_upper: {policy_before.manual_review_upper:.12f}",
        "",
        "### Policy thresholds (after calibration)",
        "",
        f"- decline_threshold: {policy_after.decline_threshold:.12f}",
        f"- manual_review_lower: {policy_after.manual_review_lower:.12f}",
        f"- manual_review_upper: {policy_after.manual_review_upper:.12f}",
        "",
        "## Data profile",
        "",
        json.dumps(data_profile, indent=2),
        "",
        "## Decision distribution (before)",
        "",
        json.dumps(decision_distribution_before, indent=2),
        "",
        "## Decision distribution (after)",
        "",
        json.dumps(decision_distribution_after, indent=2),
        "",
        "## Holdout metrics (before)",
        "",
        json.dumps(metrics_before, indent=2),
        "",
        "## Holdout metrics (after)",
        "",
        json.dumps(metrics_after, indent=2),
        "",
        "## Replay and audit integrity",
        "",
        f"- replay_success_rate: {replay_success_rate:.6f}",
        f"- audit_chain_verification: {str(audit_chain_valid).lower()}",
        "",
        "## Minimum viable validation guardrails",
        "",
        json.dumps(guardrails, indent=2),
        "",
        "## Evidence pack",
        "",
        f"- mode: {evidence_pack_mode}",
    ]
    if evidence_pack_rows is not None:
        lines.append(f"- sampled_rows: {evidence_pack_rows}")
    lines.extend(
        [
            "",
            "## Limitations",
            "",
            "- Holdout split may use deterministic source/time proxies when exact quarter labels are unavailable.",
            "- Public institutional datasets are proxy mappings into simplified causal states.",
            "- This workflow supports governance testing and outcome validation signals, not production approval.",
        ]
    )
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text("\n".join(lines), encoding="utf-8")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run public holdout validation for institutional mortgage performance data.")
    parser.add_argument(
        "--input",
        action="append",
        default=[],
        help="Normalized mortgage CSV input. Repeat for multiple files.",
    )
    parser.add_argument(
        "--train-input",
        action="append",
        default=[],
        help="Explicit training normalized CSV input. Repeat for multiple files.",
    )
    parser.add_argument(
        "--test-input",
        action="append",
        default=[],
        help="Explicit holdout test normalized CSV input. Repeat for multiple files.",
    )
    parser.add_argument(
        "--model-config",
        default=str(ROOT / "configs" / "public_mortgage_model.v1.json"),
        help="Base model config for CPD estimation.",
    )
    parser.add_argument(
        "--policy-config",
        default=str(ROOT / "configs" / "public_mortgage_policy.v1.json"),
        help="Policy config for decision thresholds.",
    )
    parser.add_argument(
        "--output-dir",
        default=str(ROOT / "validation" / "outputs" / "holdout_validation"),
        help="Output directory for holdout artifacts.",
    )
    parser.add_argument(
        "--train-fraction",
        type=float,
        default=0.8,
        help="Training fraction for deterministic split when explicit train/test files are not provided.",
    )
    parser.add_argument(
        "--matured-min-loan-age",
        type=int,
        default=24,
        help="Minimum loan_age_months proxy for matured holdout cohort selection.",
    )
    parser.add_argument(
        "--min-test-positives",
        type=int,
        default=100,
        help="Minimum positive events required before outcome validation is considered adequately powered.",
    )
    parser.add_argument(
        "--baseline-evidence-features",
        default="tenure,utilization",
        help="Comma-separated baseline evidence features for before metrics.",
    )
    parser.add_argument(
        "--evidence-features",
        default="tenure,utilization,income,dsc",
        help="Comma-separated evidence features for calibrated after metrics.",
    )
    parser.add_argument(
        "--review-target-fraction",
        type=float,
        default=0.15,
        help="Target fraction of train rows to route to REVIEW during policy calibration.",
    )
    parser.add_argument("--max-audits", type=int, default=100, help="Maximum holdout audits for replay checks.")
    parser.add_argument("--subgroup-column", default="segment", help="Subgroup column for fairness outputs in batch CSV.")
    parser.add_argument("--skip-evidence-pack", action="store_true", help="Skip evidence-pack export.")
    parser.add_argument(
        "--evidence-pack-max-rows",
        type=int,
        default=1000,
        help="Maximum rows for sampled evidence pack when not skipped.",
    )
    return parser


def main() -> int:
    args = build_parser().parse_args()
    if args.train_fraction <= 0 or args.train_fraction >= 1:
        raise ValueError("--train-fraction must be between 0 and 1 (exclusive)")
    if args.matured_min_loan_age < 0:
        raise ValueError("--matured-min-loan-age must be non-negative")
    if args.min_test_positives < 1:
        raise ValueError("--min-test-positives must be a positive integer")
    if not 0.0 <= args.review_target_fraction < 1.0:
        raise ValueError("--review-target-fraction must be in [0, 1).")

    baseline_features = _parse_features(args.baseline_evidence_features)
    evidence_features = _parse_features(args.evidence_features)

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    explicit_split = bool(args.train_input or args.test_input)
    if explicit_split and (not args.train_input or not args.test_input):
        raise ValueError("When using explicit split, provide both --train-input and --test-input.")

    _progress("loading mortgage inputs")
    if explicit_split:
        raw_train_rows: list[dict[str, str]] = []
        raw_test_rows: list[dict[str, str]] = []
        for path in args.train_input:
            raw_train_rows.extend(_read_csv_rows(Path(path)))
        for path in args.test_input:
            raw_test_rows.extend(_read_csv_rows(Path(path)))
        split_meta: dict[str, Any] = {
            "strategy": "explicit_train_test_inputs",
            "train_files": args.train_input,
            "test_files": args.test_input,
            "notes": "Explicit file split provided by operator.",
        }
    else:
        if not args.input:
            raise ValueError("Provide --input files or explicit --train-input/--test-input files.")
        all_rows: list[dict[str, str]] = []
        for path in args.input:
            all_rows.extend(_read_csv_rows(Path(path)))
        raw_train_rows, raw_test_rows, split_meta = _split_holdout_rows(
            all_rows,
            args.train_fraction,
            args.matured_min_loan_age,
        )
        split_meta["input_files"] = args.input

    perf_train = [row for row in raw_train_rows if row.get("source_dataset", "") in MORTGAGE_PERFORMANCE_DATASETS]
    perf_test = [row for row in raw_test_rows if row.get("source_dataset", "") in MORTGAGE_PERFORMANCE_DATASETS]
    train_rows, rejected_train = _filter_valid_rows(perf_train)
    test_rows, rejected_test = _filter_valid_rows(perf_test)
    rejected_rows = rejected_train + rejected_test

    if not train_rows:
        raise ValueError("No valid training rows available after filtering.")
    if not test_rows:
        raise ValueError("No valid holdout test rows available after filtering.")

    _progress("estimating CPDs on training rows")
    cpd_rows = [
        {
            "tenure": row["tenure"],
            "utilization": row["utilization"],
            "income": row["income"],
            "dsc": row["dsc"],
            "risk": row["risk"],
        }
        for row in train_rows
    ]
    source_ref = ";".join(sorted({row["source_dataset"] for row in train_rows}))
    draft_payload = build_draft_model_config(
        base_model_config_path=args.model_config,
        rows=cpd_rows,
        source_dataset_reference=source_ref,
        notes="Draft CPD estimate for holdout validation from training rows.",
    )
    draft_model_path = output_dir / "draft_model_config.holdout.json"
    draft_model_path.write_text(json.dumps(draft_payload, indent=2), encoding="utf-8")

    model = CausalDAGModel.from_json(draft_model_path)
    base_policy_config = PolicyConfig.from_json(args.policy_config)
    base_policy = DecisionPolicy(base_policy_config)
    validate_policy_against_model(model, base_policy)
    engine = ExactInferenceEngine(model)

    model_node_ids = set(model.nodes.keys())
    unknown_baseline = [feature for feature in baseline_features if feature not in model_node_ids]
    unknown_features = [feature for feature in evidence_features if feature not in model_node_ids]
    if unknown_baseline:
        raise ValueError(
            "Unknown baseline evidence feature(s): " + ", ".join(sorted(unknown_baseline))
        )
    if unknown_features:
        raise ValueError("Unknown evidence feature(s): " + ", ".join(sorted(unknown_features)))

    _progress("scoring holdout rows (before)")
    y_true_before, y_score_before, decisions_before, _ = _score_rows(
        engine=engine,
        policy=base_policy,
        policy_config=base_policy_config,
        rows=test_rows,
        evidence_features=baseline_features,
    )
    metrics_before, decision_distribution_before = _build_metrics(
        y_true=y_true_before,
        y_score=y_score_before,
        decisions=decisions_before,
        policy_config=base_policy_config,
    )

    _progress("calibrating policy from train rows")
    calibrated_policy_config = _calibrate_policy_from_train(
        train_rows=train_rows,
        engine=engine,
        base_policy=base_policy_config,
        evidence_features=evidence_features,
        review_target_fraction=args.review_target_fraction,
    )
    calibrated_policy_path = output_dir / "calibrated_policy.holdout.json"
    calibrated_policy_path.write_text(
        json.dumps(
            {
                "policy_id": calibrated_policy_config.policy_id,
                "policy_version": calibrated_policy_config.policy_version,
                "decline_threshold": calibrated_policy_config.decline_threshold,
                "manual_review_lower": calibrated_policy_config.manual_review_lower,
                "manual_review_upper": calibrated_policy_config.manual_review_upper,
                "risk_outcome_node": calibrated_policy_config.risk_outcome_node,
                "high_risk_state": calibrated_policy_config.high_risk_state,
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    calibrated_policy = DecisionPolicy(calibrated_policy_config)
    validate_policy_against_model(model, calibrated_policy)

    _progress("scoring holdout rows (after)")
    y_true, y_score, decisions, scored_rows = _score_rows(
        engine=engine,
        policy=calibrated_policy,
        policy_config=calibrated_policy_config,
        rows=test_rows,
        evidence_features=evidence_features,
    )
    for row, source in zip(scored_rows, test_rows):
        row[args.subgroup_column] = source.get(args.subgroup_column, "unspecified")
    metrics, decision_distribution = _build_metrics(
        y_true=y_true,
        y_score=y_score,
        decisions=decisions,
        policy_config=calibrated_policy_config,
    )

    _progress("running replay checks")
    replay_success = 0
    replay_checked = 0
    chain_records: list[dict[str, Any]] = []
    prev_hash: str | None = None
    for idx, row in enumerate(test_rows[: max(args.max_audits, 0)]):
        evidence = {feature: row[feature] for feature in evidence_features}
        audit = run_decision(
            model_config_path=draft_model_path,
            policy_config_path=calibrated_policy_path,
            evidence=evidence,
            tenant_id=row.get("tenant_id", "default") or "default",
        ).to_dict()
        replay_checked += 1
        replay = replay_from_audit_payload(
            audit_payload=audit,
            model_config_path=draft_model_path,
            policy_config_path=calibrated_policy_path,
        )
        if replay.get("risk_probability_match") and replay.get("decision_match"):
            replay_success += 1
        chain = build_audit_chain_record(
            audit,
            chain_index=idx,
            previous_hash=prev_hash,
            tenant_id=str(audit.get("tenant_id", "default")),
        )
        chain_records.append(chain)
        prev_hash = str(chain["audit_hash"])

    replay_success_rate = (replay_success / replay_checked) if replay_checked else 0.0
    audit_chain_valid = verify_audit_chain(chain_records) if chain_records else True

    audit_chain_path = output_dir / "audit_chain.json"
    audit_chain_path.write_text(json.dumps(chain_records, indent=2), encoding="utf-8")

    _progress("writing holdout batch outputs")
    batch_input = output_dir / "test_batch_input.csv"
    _write_csv(batch_input, ["tenant_id", "tenure", "utilization", args.subgroup_column], scored_rows)
    batch_output = output_dir / "test_batch_output.csv"
    batch_summary = run_batch_csv(
        model_config_path=draft_model_path,
        policy_config_path=calibrated_policy_path,
        csv_input_path=batch_input,
        csv_output_path=batch_output,
        subgroup_column=args.subgroup_column,
    )

    evidence_pack_mode = "skipped" if args.skip_evidence_pack else "sampled"
    evidence_pack_rows: int | None = None
    evidence_pack_metadata: dict[str, Any] | None = None
    if not args.skip_evidence_pack:
        sample_count = min(args.evidence_pack_max_rows, len(scored_rows))
        evidence_pack_rows = sample_count
        sample_path = output_dir / "test_batch_input.sampled.csv"
        _write_csv(
            sample_path,
            ["tenant_id", "tenure", "utilization", args.subgroup_column],
            scored_rows[:sample_count],
        )
        from export_evidence_pack import export_evidence_pack

        evidence_pack_metadata = export_evidence_pack(
            input_csv=sample_path,
            output_dir=output_dir / "evidence_pack",
            model_config_path=draft_model_path,
            policy_config_path=calibrated_policy_path,
            max_rows=sample_count,
        )

    prevalence_train = (sum(1 for row in train_rows if row["risk"] == "high_risk") / len(train_rows)) if train_rows else 0.0
    prevalence_test = (sum(y_true) / len(y_true)) if y_true else 0.0
    test_positive_count = int(sum(y_true))
    unique_decisions = sorted(set(decisions))
    guardrail_messages: list[str] = []
    underpowered = test_positive_count < args.min_test_positives
    policy_uninformative = len(unique_decisions) == 1
    if underpowered:
        guardrail_messages.append(
            f"Underpowered outcome evaluation: test positives {test_positive_count} < required minimum {args.min_test_positives}."
        )
    if policy_uninformative:
        guardrail_messages.append(
            f"Policy thresholds uninformative on holdout: all decisions were {unique_decisions[0]}."
        )
    guardrails = {
        "min_test_positives": args.min_test_positives,
        "test_positive_count": test_positive_count,
        "underpowered": underpowered,
        "single_decision_class": policy_uninformative,
        "decision_classes_observed": unique_decisions,
        "messages": guardrail_messages,
    }
    data_profile = {
        "train": _profile_rows(train_rows),
        "test": _profile_rows(test_rows),
    }

    report_path = output_dir / "holdout_validation_report.generated.md"
    _progress("writing report")
    _write_report(
        report_path=report_path,
        split_meta=split_meta,
        train_rows=len(train_rows),
        test_rows=len(test_rows),
        rejected_rows=rejected_rows,
        outcome_prevalence_train=prevalence_train,
        outcome_prevalence_test=prevalence_test,
        baseline_features=baseline_features,
        calibrated_features=evidence_features,
        policy_before=base_policy_config,
        policy_after=calibrated_policy_config,
        decision_distribution_before=decision_distribution_before,
        decision_distribution_after=decision_distribution,
        metrics_before=metrics_before,
        metrics_after=metrics,
        replay_success_rate=replay_success_rate,
        audit_chain_valid=audit_chain_valid,
        evidence_pack_mode=evidence_pack_mode,
        evidence_pack_rows=evidence_pack_rows,
        data_profile=data_profile,
        guardrails=guardrails,
    )

    summary = {
        "status": "completed",
        "generated_at_utc": _utc_now(),
        "output_dir": str(output_dir),
        "split": split_meta,
        "baseline_features": baseline_features,
        "calibrated_features": evidence_features,
        "train_rows": len(train_rows),
        "test_rows": len(test_rows),
        "rejected_rows": rejected_rows,
        "outcome_prevalence_train": prevalence_train,
        "outcome_prevalence_test": prevalence_test,
        "test_positive_count": test_positive_count,
        "decision_distribution_before": decision_distribution_before,
        "decision_distribution_after": decision_distribution,
        "decision_distribution": decision_distribution,
        "metrics_before": metrics_before,
        "metrics_after": metrics,
        "metrics": metrics,
        "policy_before": {
            "policy_id": base_policy_config.policy_id,
            "policy_version": base_policy_config.policy_version,
            "decline_threshold": base_policy_config.decline_threshold,
            "manual_review_lower": base_policy_config.manual_review_lower,
            "manual_review_upper": base_policy_config.manual_review_upper,
        },
        "policy_after": {
            "policy_id": calibrated_policy_config.policy_id,
            "policy_version": calibrated_policy_config.policy_version,
            "decline_threshold": calibrated_policy_config.decline_threshold,
            "manual_review_lower": calibrated_policy_config.manual_review_lower,
            "manual_review_upper": calibrated_policy_config.manual_review_upper,
        },
        "data_profile": data_profile,
        "guardrails": guardrails,
        "replay_success_rate": replay_success_rate,
        "audit_chain_valid": audit_chain_valid,
        "batch_summary": batch_summary,
        "evidence_pack_mode": evidence_pack_mode,
        "evidence_pack_rows": evidence_pack_rows,
        "evidence_pack": evidence_pack_metadata,
        "draft_model_config": str(draft_model_path),
        "calibrated_policy_config": str(calibrated_policy_path),
        "audit_chain_path": str(audit_chain_path),
        "report_path": str(report_path),
        "non_production_disclaimer": (
            "Public holdout validation on institutional mortgage performance data. "
            "Not production validation, not consumer credit eligibility, and not regulatory compliance proof."
        ),
    }
    summary_path = output_dir / "holdout_validation_summary.json"
    summary_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
