"""Decision policy layer for risk-based outcomes.

WARNING:
Policy thresholds here are demo artifacts and not production credit policy.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from causal_credit_risk.schemas import DecisionLabel, PolicyConfig

if TYPE_CHECKING:
    from causal_credit_risk.model import CausalDAGModel


class PolicyValidationError(ValueError):
    """Raised when decision policy thresholds are invalid."""


class DecisionPolicy:
    """Maps risk probability to APPROVE / REVIEW / DECLINE."""

    def __init__(self, config: PolicyConfig) -> None:
        self.config = config
        self._validate()

    def _validate(self) -> None:
        if not 0.0 <= self.config.decline_threshold <= 1.0:
            raise PolicyValidationError("decline_threshold must be in [0, 1]")
        if not 0.0 <= self.config.manual_review_lower <= 1.0:
            raise PolicyValidationError("manual_review_lower must be in [0, 1]")
        if not 0.0 <= self.config.manual_review_upper <= 1.0:
            raise PolicyValidationError("manual_review_upper must be in [0, 1]")
        if self.config.manual_review_lower > self.config.manual_review_upper:
            raise PolicyValidationError(
                "manual_review_lower cannot exceed manual_review_upper"
            )
        if self.config.manual_review_upper > self.config.decline_threshold:
            raise PolicyValidationError(
                "manual_review_upper cannot exceed decline_threshold"
            )

    def decide(self, risk_probability: float) -> DecisionLabel:
        if risk_probability >= self.config.decline_threshold:
            return "DECLINE"
        if self.config.manual_review_lower <= risk_probability < self.config.manual_review_upper:
            return "REVIEW"
        return "APPROVE"


def validate_policy_against_model(
    model: "CausalDAGModel", policy: DecisionPolicy | PolicyConfig
) -> None:
    config = policy.config if isinstance(policy, DecisionPolicy) else policy

    if config.risk_outcome_node not in model.nodes:
        raise PolicyValidationError(
            f"Policy references unknown risk_outcome_node: {config.risk_outcome_node}"
        )

    outcome_node = model.nodes[config.risk_outcome_node]
    if outcome_node.node_type != "outcome":
        raise PolicyValidationError(
            f"Policy risk_outcome_node must be node_type='outcome', got {outcome_node.node_type}"
        )

    if config.high_risk_state not in outcome_node.states:
        raise PolicyValidationError(
            f"Policy high_risk_state '{config.high_risk_state}' is not valid for node {config.risk_outcome_node}"
        )
