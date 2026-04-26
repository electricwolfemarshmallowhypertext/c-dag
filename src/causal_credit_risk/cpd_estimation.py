"""Draft CPD estimation utilities from categorical CSV rows."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np

from causal_credit_risk.interfaces import CPDEstimator
from causal_credit_risk.io_utils import read_json_file
from causal_credit_risk.model import CausalDAGModel


ESTIMATOR_VERSION = "0.1.0"


def _utc_now() -> str:
    return datetime.now(tz=timezone.utc).isoformat(timespec="seconds")


class CsvCPDEstimator(CPDEstimator):
    def __init__(self, model: CausalDAGModel) -> None:
        self.model = model

    def estimate(self, rows: Sequence[Mapping[str, str]]) -> dict[str, Any]:
        cpds_out: dict[str, Any] = {}
        estimated_nodes: list[str] = []
        skipped_nodes: list[str] = []

        for node_id in self.model.topological_order:
            node = self.model.nodes[node_id]
            required_columns = {node_id, *node.parents}
            if not rows or not all(required_columns.issubset(set(row.keys())) for row in rows):
                cpds_out[node_id] = {
                    "parents": list(node.parents),
                    "outcomes": list(node.states),
                    "table": np.asarray(self.model.cpd_arrays[node_id]).tolist(),
                    "estimation_status": "copied_from_source_config",
                }
                skipped_nodes.append(node_id)
                continue

            shape = (
                len(node.states),
                *[len(self.model.nodes[parent].states) for parent in node.parents],
            )
            counts = np.ones(shape, dtype=float)

            for row in rows:
                try:
                    outcome_idx = self.model.get_state_index(node_id, str(row[node_id]).strip())
                    parent_idxs = tuple(
                        self.model.get_state_index(parent, str(row[parent]).strip())
                        for parent in node.parents
                    )
                except Exception:
                    continue
                counts[(outcome_idx,) + parent_idxs] += 1.0

            totals = counts.sum(axis=0, keepdims=True)
            table = counts / totals
            cpds_out[node_id] = {
                "parents": list(node.parents),
                "outcomes": list(node.states),
                "table": table.tolist(),
                "estimation_status": "estimated_from_csv",
            }
            estimated_nodes.append(node_id)

        return {
            "cpds": cpds_out,
            "estimated_nodes": estimated_nodes,
            "skipped_nodes": skipped_nodes,
            "estimator_version": ESTIMATOR_VERSION,
        }


def build_draft_model_config(
    *,
    base_model_config_path: str | Path,
    rows: Sequence[Mapping[str, str]],
    source_dataset_reference: str,
    notes: str | None = None,
) -> dict[str, Any]:
    base_payload = read_json_file(base_model_config_path)
    model = CausalDAGModel.from_json(base_model_config_path)
    estimator = CsvCPDEstimator(model)
    estimation = estimator.estimate(rows)

    output = dict(base_payload)
    output["cpds"] = estimation["cpds"]
    output["estimation_metadata"] = {
        "generated_at_utc": _utc_now(),
        "source_dataset_reference": source_dataset_reference,
        "estimator_version": estimation["estimator_version"],
        "approval_status": "draft",
        "notes": notes
        or "Draft CPD estimate. Requires expert/model-risk review before any operational use.",
        "estimated_nodes": estimation["estimated_nodes"],
        "skipped_nodes": estimation["skipped_nodes"],
    }
    return output
