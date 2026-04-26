"""Audit record assembly for regulator-facing explainability traces.

WARNING:
This audit schema is a demo artifact and not a substitute for compliance processes.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from datetime import datetime, timezone
import uuid

import numpy as np

from causal_credit_risk.inference import ExactInferenceEngine
from causal_credit_risk.model import CausalDAGModel
from causal_credit_risk.schemas import AuditRecord, CounterfactualResult, DecisionLabel, PolicyConfig


def _utc_timestamp() -> str:
    return datetime.now(tz=timezone.utc).isoformat(timespec="seconds")


def _ancestor_set(model: CausalDAGModel, node_id: str) -> set[str]:
    ancestors: set[str] = set()
    frontier = [node_id]
    while frontier:
        current = frontier.pop()
        for parent in model.nodes[current].parents:
            if parent not in ancestors:
                ancestors.add(parent)
                frontier.append(parent)
    return ancestors


def build_causal_chain(
    model: CausalDAGModel,
    engine: ExactInferenceEngine,
    *,
    input_evidence: Mapping[str, str | int],
    outcome_node_id: str,
) -> list[dict[str, object]]:
    evidence_idx = model.normalize_evidence(input_evidence)
    ancestors = _ancestor_set(model, outcome_node_id)
    include_nodes = ancestors.union({outcome_node_id})
    chain: list[dict[str, object]] = []

    for node_id in model.topological_order:
        if node_id not in include_nodes:
            continue
        node = model.nodes[node_id]
        if node_id in evidence_idx:
            chain.append(
                {
                    "node_id": node_id,
                    "human_label": node.human_label,
                    "node_type": node.node_type,
                    "source": "observed",
                    "state": model.get_state_name(node_id, evidence_idx[node_id]),
                }
            )
            continue

        distribution = engine.query_distribution(node_id, evidence=input_evidence)
        likely_idx = int(np.argmax(distribution))
        chain.append(
            {
                "node_id": node_id,
                "human_label": node.human_label,
                "node_type": node.node_type,
                "source": "inferred",
                "most_likely_state": model.get_state_name(node_id, likely_idx),
                "p_adverse_state": float(distribution[0]),
            }
        )

    return chain


def create_audit_record(
    *,
    model: CausalDAGModel,
    policy_config: PolicyConfig,
    input_evidence: Mapping[str, str | int],
    inferred_nodes: Mapping[str, Mapping[str, float]],
    risk_probability: float,
    decision: DecisionLabel,
    causal_chain: Iterable[Mapping[str, object]],
    counterfactuals: Iterable[CounterfactualResult],
    validation_status: Mapping[str, object] | None = None,
    decision_id: str | None = None,
    timestamp_utc: str | None = None,
    tenant_id: str = "default",
) -> AuditRecord:
    evidence_idx = model.normalize_evidence(input_evidence)
    validation = (
        dict(validation_status)
        if validation_status is not None
        else {"model_valid": True, "policy_valid": True, "errors": []}
    )

    return AuditRecord(
        decision_id=decision_id or str(uuid.uuid4()),
        tenant_id=tenant_id,
        model_id=model.config.model_id,
        model_version=model.config.model_version,
        policy_version=policy_config.policy_version,
        timestamp_utc=timestamp_utc or _utc_timestamp(),
        input_evidence=model.denormalize_evidence(evidence_idx),
        inferred_nodes={
            node_id: {state: float(prob) for state, prob in state_probs.items()}
            for node_id, state_probs in inferred_nodes.items()
        },
        risk_probability=float(risk_probability),
        decision=decision,
        causal_chain=[dict(item) for item in causal_chain],
        counterfactuals=[item.to_dict() for item in counterfactuals],
        validation_status=validation,
    )
