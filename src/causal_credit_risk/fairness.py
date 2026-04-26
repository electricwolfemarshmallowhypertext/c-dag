"""Lightweight subgroup fairness diagnostics for batch decision outputs.

This module provides diagnostics and does not certify fairness.
"""

from __future__ import annotations

from collections import defaultdict
from typing import Any


def _extract_decision_and_risk(row: dict[str, Any]) -> tuple[str | None, float | None]:
    if "decision" in row and "risk_probability" in row:
        decision = row.get("decision")
        risk = row.get("risk_probability")
    elif isinstance(row.get("audit"), dict):
        audit = row["audit"]
        decision = audit.get("decision")
        risk = audit.get("risk_probability")
    else:
        return None, None

    if not isinstance(decision, str):
        return None, None
    try:
        risk_value = float(risk)
    except (TypeError, ValueError):
        return None, None
    return decision, risk_value


def compute_fairness_report(
    rows: list[dict[str, Any]],
    *,
    subgroup_column: str = "segment",
    min_sample_size: int = 5,
    tenant_id: str | None = None,
) -> dict[str, Any]:
    if not subgroup_column.strip():
        raise ValueError("subgroup_column must be a non-empty string")
    if rows and not any(subgroup_column in row for row in rows):
        raise ValueError(f"Missing subgroup column in rows: {subgroup_column}")

    grouped_counts: dict[str, dict[str, int]] = defaultdict(
        lambda: {"count": 0, "approve": 0, "review": 0, "decline": 0}
    )
    grouped_risks: dict[str, list[float]] = defaultdict(list)
    skipped_rows = 0

    for row in rows:
        subgroup = str(row.get(subgroup_column, "__unspecified__"))
        decision, risk_probability = _extract_decision_and_risk(row)
        if decision is None or risk_probability is None:
            skipped_rows += 1
            continue

        counts = grouped_counts[subgroup]
        counts["count"] += 1
        if decision == "APPROVE":
            counts["approve"] += 1
        elif decision == "REVIEW":
            counts["review"] += 1
        elif decision == "DECLINE":
            counts["decline"] += 1
        else:
            skipped_rows += 1
            counts["count"] -= 1
            continue
        grouped_risks[subgroup].append(risk_probability)

    subgroup_metrics: dict[str, dict[str, float | int]] = {}
    warnings: list[str] = []
    for subgroup, counts in grouped_counts.items():
        if counts["count"] == 0:
            continue
        total = counts["count"]
        mean_risk = sum(grouped_risks[subgroup]) / total
        subgroup_metrics[subgroup] = {
            "count": total,
            "approve_rate": counts["approve"] / total,
            "review_rate": counts["review"] / total,
            "decline_rate": counts["decline"] / total,
            "mean_risk_probability": mean_risk,
        }
        if total < min_sample_size:
            warnings.append(
                f"Subgroup '{subgroup}' has small sample size ({total} < {min_sample_size})."
            )

    mean_risks = [float(item["mean_risk_probability"]) for item in subgroup_metrics.values()]
    approve_rates = [float(item["approve_rate"]) for item in subgroup_metrics.values()]
    decline_rates = [float(item["decline_rate"]) for item in subgroup_metrics.values()]

    deltas = {
        "mean_risk_probability_delta": max(mean_risks) - min(mean_risks) if mean_risks else 0.0,
        "approve_rate_delta": max(approve_rates) - min(approve_rates) if approve_rates else 0.0,
        "decline_rate_delta": max(decline_rates) - min(decline_rates) if decline_rates else 0.0,
    }

    if tenant_id is None:
        tenant_candidates = {
            str(row.get("tenant_id")).strip()
            for row in rows
            if row.get("tenant_id") is not None and str(row.get("tenant_id")).strip()
        }
        if len(tenant_candidates) == 1:
            tenant_id = next(iter(tenant_candidates))
        elif len(tenant_candidates) > 1:
            tenant_id = "mixed"
        else:
            tenant_id = "default"

    return {
        "tenant_id": tenant_id,
        "subgroup_column": subgroup_column,
        "rows_received": len(rows),
        "rows_analyzed": sum(int(item["count"]) for item in subgroup_metrics.values()),
        "rows_skipped": skipped_rows,
        "subgroups": subgroup_metrics,
        "max_min_subgroup_delta": deltas,
        "warnings": warnings,
        "disclaimer": "Fairness diagnostics only; not fairness certification.",
    }
