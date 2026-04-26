"""Model loading and validation for discrete causal DAGs.

WARNING:
This is a demo explainability model runtime and not production credit policy.
"""

from __future__ import annotations

from collections import deque
from pathlib import Path
from typing import Mapping

import numpy as np

from causal_credit_risk.schemas import ModelConfig, StateRef


class ModelValidationError(ValueError):
    """Raised when the configured DAG or CPDs are invalid."""


class CausalDAGModel:
    """Validated discrete DAG model with CPDs loaded from external config."""

    def __init__(self, config: ModelConfig) -> None:
        self.config = config
        self.nodes = {node.node_id: node for node in config.nodes}
        self.cpds = config.cpds
        self.cpd_arrays: dict[str, np.ndarray] = {}
        self.topological_order: tuple[str, ...] = ()
        self._validate()

    @classmethod
    def from_json(cls, path: str | Path) -> "CausalDAGModel":
        return cls(ModelConfig.from_json(path))

    def _validate(self) -> None:
        if not self.nodes:
            raise ModelValidationError("Model must define at least one node")

        if len(self.nodes) != len(self.config.nodes):
            raise ModelValidationError("Duplicate node_id values detected")

        node_ids = set(self.nodes)
        missing_cpds = node_ids.difference(self.cpds)
        extra_cpds = set(self.cpds).difference(node_ids)
        if missing_cpds or extra_cpds:
            raise ModelValidationError(
                f"CPD mismatch. missing={sorted(missing_cpds)}, extra={sorted(extra_cpds)}"
            )

        for node in self.config.nodes:
            if node.node_type not in {"observed", "inferred", "outcome"}:
                raise ModelValidationError(
                    f"Node {node.node_id} has invalid node_type: {node.node_type}"
                )
            if not node.states:
                raise ModelValidationError(f"Node {node.node_id} must define states")
            if len(set(node.states)) != len(node.states):
                raise ModelValidationError(f"Node {node.node_id} has duplicate states")

            for parent in node.parents:
                if parent not in node_ids:
                    raise ModelValidationError(
                        f"Node {node.node_id} references unknown parent {parent}"
                    )
            if node.node_id in node.parents:
                raise ModelValidationError(f"Node {node.node_id} cannot be its own parent")

            cpd = self.cpds[node.node_id]
            if tuple(cpd.parents) != tuple(node.parents):
                raise ModelValidationError(
                    f"CPD parent order mismatch for {node.node_id}. "
                    f"node.parents={node.parents}, cpd.parents={cpd.parents}"
                )
            if tuple(cpd.outcomes) != tuple(node.states):
                raise ModelValidationError(
                    f"CPD outcomes mismatch for {node.node_id}. "
                    f"node.states={node.states}, cpd.outcomes={cpd.outcomes}"
                )

            expected_shape = (
                len(node.states),
                *[len(self.nodes[parent].states) for parent in node.parents],
            )
            table = np.asarray(cpd.table, dtype=float)
            if table.shape != expected_shape:
                raise ModelValidationError(
                    f"CPD shape mismatch for {node.node_id}. "
                    f"expected={expected_shape}, got={table.shape}"
                )
            if np.any((table < 0.0) | (table > 1.0)):
                raise ModelValidationError(
                    f"CPD values for {node.node_id} must be within [0, 1]"
                )

            sums = table.sum(axis=0)
            if not np.allclose(sums, 1.0, atol=1e-9):
                raise ModelValidationError(
                    f"CPD probabilities for {node.node_id} must sum to 1 on outcome axis; got={sums}"
                )

            self.cpd_arrays[node.node_id] = table

        self.topological_order = self._topological_sort()

    def _topological_sort(self) -> tuple[str, ...]:
        in_degree = {node_id: 0 for node_id in self.nodes}
        children: dict[str, list[str]] = {node_id: [] for node_id in self.nodes}

        for node_id, node in self.nodes.items():
            for parent in node.parents:
                in_degree[node_id] += 1
                children[parent].append(node_id)

        queue = deque(sorted(node_id for node_id, degree in in_degree.items() if degree == 0))
        order: list[str] = []
        while queue:
            current = queue.popleft()
            order.append(current)
            for child in sorted(children[current]):
                in_degree[child] -= 1
                if in_degree[child] == 0:
                    queue.append(child)

        if len(order) != len(self.nodes):
            raise ModelValidationError("DAG validation failed: cycle detected")
        return tuple(order)

    def get_state_index(self, node_id: str, state: StateRef) -> int:
        if node_id not in self.nodes:
            raise KeyError(f"Unknown node_id: {node_id}")

        states = self.nodes[node_id].states
        if isinstance(state, int):
            if state < 0 or state >= len(states):
                raise ValueError(f"State index out of range for {node_id}: {state}")
            return state

        if state not in states:
            raise ValueError(f"Unknown state for {node_id}: {state}")
        return states.index(state)

    def get_state_name(self, node_id: str, state_index: int) -> str:
        if node_id not in self.nodes:
            raise KeyError(f"Unknown node_id: {node_id}")
        states = self.nodes[node_id].states
        if state_index < 0 or state_index >= len(states):
            raise ValueError(f"State index out of range for {node_id}: {state_index}")
        return states[state_index]

    def normalize_evidence(
        self, evidence: Mapping[str, StateRef] | None
    ) -> dict[str, int]:
        normalized: dict[str, int] = {}
        if evidence is None:
            return normalized

        for node_id, state in evidence.items():
            normalized[node_id] = self.get_state_index(node_id, state)
        return normalized

    def denormalize_evidence(self, evidence: Mapping[str, int]) -> dict[str, str]:
        return {
            node_id: self.get_state_name(node_id, state_idx)
            for node_id, state_idx in evidence.items()
        }
