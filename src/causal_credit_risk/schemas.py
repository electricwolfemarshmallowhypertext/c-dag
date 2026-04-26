"""Typed schemas for causal model, policy, and audit artifacts.

WARNING:
This module supports explainability demos only.
It is not a complete regulated credit decision framework.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
import json
from pathlib import Path
from typing import Any, Literal, Mapping

from causal_credit_risk.io_utils import read_json_file

NodeType = Literal["observed", "inferred", "outcome"]
DecisionLabel = Literal["APPROVE", "REVIEW", "DECLINE"]
StateRef = int | str


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
    if isinstance(value, tuple):
        return tuple(_round_nested(item, decimals=decimals) for item in value)
    return value


@dataclass(frozen=True)
class NodeDefinition:
    node_id: str
    human_label: str
    states: tuple[str, ...]
    parents: tuple[str, ...]
    mechanism_description: str
    node_type: NodeType

    @classmethod
    def from_dict(cls, raw: Mapping[str, Any]) -> "NodeDefinition":
        return cls(
            node_id=str(raw["node_id"]),
            human_label=str(raw["human_label"]),
            states=tuple(str(state) for state in raw["states"]),
            parents=tuple(str(parent) for parent in raw.get("parents", [])),
            mechanism_description=str(raw["mechanism_description"]),
            node_type=str(raw["node_type"]),  # type: ignore[arg-type]
        )


@dataclass(frozen=True)
class CpdDefinition:
    node_id: str
    parents: tuple[str, ...]
    outcomes: tuple[str, ...]
    table: Any

    @classmethod
    def from_dict(cls, node_id: str, raw: Mapping[str, Any]) -> "CpdDefinition":
        return cls(
            node_id=node_id,
            parents=tuple(str(parent) for parent in raw.get("parents", [])),
            outcomes=tuple(str(outcome) for outcome in raw["outcomes"]),
            table=raw["table"],
        )


@dataclass(frozen=True)
class ModelConfig:
    model_id: str
    model_version: str
    description: str
    nodes: tuple[NodeDefinition, ...]
    cpds: dict[str, CpdDefinition]

    @classmethod
    def from_json(cls, path: str | Path) -> "ModelConfig":
        payload = read_json_file(path)

        nodes = tuple(NodeDefinition.from_dict(item) for item in payload["nodes"])
        cpds: dict[str, CpdDefinition] = {}
        for node_id, cpd_payload in payload["cpds"].items():
            if node_id in cpds:
                raise ValueError(f"Duplicate CPD entry for node: {node_id}")
            cpds[node_id] = CpdDefinition.from_dict(node_id, cpd_payload)

        return cls(
            model_id=str(payload["model_id"]),
            model_version=str(payload["model_version"]),
            description=str(payload.get("description", "")),
            nodes=nodes,
            cpds=cpds,
        )


@dataclass(frozen=True)
class PolicyConfig:
    policy_id: str
    policy_version: str
    decline_threshold: float
    manual_review_lower: float
    manual_review_upper: float
    risk_outcome_node: str
    high_risk_state: str

    @classmethod
    def from_json(cls, path: str | Path) -> "PolicyConfig":
        payload = read_json_file(path)
        return cls(
            policy_id=str(payload["policy_id"]),
            policy_version=str(payload["policy_version"]),
            decline_threshold=float(payload["decline_threshold"]),
            manual_review_lower=float(payload["manual_review_lower"]),
            manual_review_upper=float(payload["manual_review_upper"]),
            risk_outcome_node=str(payload["risk_outcome_node"]),
            high_risk_state=str(payload["high_risk_state"]),
        )


@dataclass(frozen=True)
class CounterfactualResult:
    baseline_evidence: dict[str, str]
    intervention_evidence: dict[str, str]
    before_probability: float
    after_probability: float
    delta: float

    def to_dict(self) -> dict[str, Any]:
        return _round_nested(asdict(self))


@dataclass(frozen=True)
class AuditRecord:
    decision_id: str
    tenant_id: str
    model_id: str
    model_version: str
    policy_version: str
    timestamp_utc: str
    input_evidence: dict[str, str]
    inferred_nodes: dict[str, dict[str, float]]
    risk_probability: float
    decision: DecisionLabel
    causal_chain: list[dict[str, Any]]
    counterfactuals: list[dict[str, Any]]
    validation_status: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return _round_nested(asdict(self))

    def to_json(self, *, indent: int = 2) -> str:
        return json.dumps(self.to_dict(), indent=indent, sort_keys=False)
