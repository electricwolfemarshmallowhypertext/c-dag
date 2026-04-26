"""Exact inference engine for discrete Bayesian/causal DAGs.

WARNING:
This module is for explainability demonstrations, not production credit operations.
"""

from __future__ import annotations

from typing import Iterable, Mapping

import numpy as np

from causal_credit_risk.model import CausalDAGModel
from causal_credit_risk.schemas import StateRef


class ExactInferenceEngine:
    """Performs exact marginal and posterior inference by full enumeration."""

    def __init__(self, model: CausalDAGModel) -> None:
        self.model = model

    def query_distribution(
        self,
        node_id: str,
        *,
        evidence: Mapping[str, StateRef] | None = None,
        interventions: Mapping[str, StateRef] | None = None,
    ) -> np.ndarray:
        evidence_idx = self.model.normalize_evidence(evidence)
        interventions_idx = self.model.normalize_evidence(interventions)

        if node_id in interventions_idx:
            forced_idx = interventions_idx[node_id]
            distribution = np.zeros(len(self.model.nodes[node_id].states), dtype=float)
            distribution[forced_idx] = 1.0
            return distribution

        state_count = len(self.model.nodes[node_id].states)
        probs = np.zeros(state_count, dtype=float)
        for state_idx in range(state_count):
            scoped_evidence = dict(evidence_idx)
            scoped_evidence[node_id] = state_idx
            probs[state_idx] = self._probability_of_evidence(
                scoped_evidence, interventions_idx
            )

        total = float(probs.sum())
        if np.isclose(total, 0.0):
            raise ValueError(
                "Evidence/interventions are inconsistent with model support; zero mass"
            )
        return probs / total

    def query_probability(
        self,
        node_id: str,
        state: StateRef,
        *,
        evidence: Mapping[str, StateRef] | None = None,
        interventions: Mapping[str, StateRef] | None = None,
    ) -> float:
        target_idx = self.model.get_state_index(node_id, state)
        distribution = self.query_distribution(
            node_id, evidence=evidence, interventions=interventions
        )
        return float(distribution[target_idx])

    def infer_node_posteriors(
        self,
        *,
        evidence: Mapping[str, StateRef] | None = None,
        node_types: Iterable[str] = ("inferred",),
    ) -> dict[str, dict[str, float]]:
        requested_types = set(node_types)
        posteriors: dict[str, dict[str, float]] = {}
        for node_id in self.model.topological_order:
            node = self.model.nodes[node_id]
            if node.node_type not in requested_types:
                continue
            distribution = self.query_distribution(node_id, evidence=evidence)
            posteriors[node_id] = {
                node.states[idx]: float(prob)
                for idx, prob in enumerate(distribution.tolist())
            }
        return posteriors

    def _probability_of_evidence(
        self, evidence_idx: dict[str, int], interventions_idx: dict[str, int]
    ) -> float:
        assignments = dict(evidence_idx)
        return self._enumerate_from_index(0, assignments, interventions_idx)

    def _enumerate_from_index(
        self, position: int, assignments: dict[str, int], interventions_idx: dict[str, int]
    ) -> float:
        order = self.model.topological_order
        if position >= len(order):
            return 1.0

        node_id = order[position]
        if node_id in interventions_idx:
            forced_state = interventions_idx[node_id]
            existing = assignments.get(node_id)
            if existing is not None and existing != forced_state:
                return 0.0

            inserted = node_id not in assignments
            assignments[node_id] = forced_state
            result = self._enumerate_from_index(position + 1, assignments, interventions_idx)
            if inserted:
                assignments.pop(node_id, None)
            return result

        if node_id in assignments:
            local_prob = self._local_probability(node_id, assignments[node_id], assignments)
            return local_prob * self._enumerate_from_index(
                position + 1, assignments, interventions_idx
            )

        total = 0.0
        state_count = len(self.model.nodes[node_id].states)
        for state_idx in range(state_count):
            assignments[node_id] = state_idx
            local_prob = self._local_probability(node_id, state_idx, assignments)
            total += local_prob * self._enumerate_from_index(
                position + 1, assignments, interventions_idx
            )
        assignments.pop(node_id, None)
        return total

    def _local_probability(
        self, node_id: str, state_index: int, assignments: Mapping[str, int]
    ) -> float:
        cpd = self.model.cpd_arrays[node_id]
        parents = self.model.nodes[node_id].parents
        if not parents:
            return float(cpd[state_index])

        parent_indices = tuple(assignments[parent] for parent in parents)
        return float(cpd[(state_index,) + parent_indices])
