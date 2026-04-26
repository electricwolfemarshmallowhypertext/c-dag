"""Deterministic replay utilities for previously saved audit records."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from causal_credit_risk.io_utils import read_json_file
from causal_credit_risk.model import CausalDAGModel
from causal_credit_risk.schemas import PolicyConfig


class ReplayValidationError(ValueError):
    """Raised when replay input or replay contracts are invalid."""


def _require_field(payload: dict[str, Any], field: str) -> Any:
    if field not in payload:
        raise ReplayValidationError(f"Replay audit is missing required field: {field}")
    return payload[field]


def replay_from_audit_file(
    *,
    audit_path: str | Path,
    model_config_path: str | Path,
    policy_config_path: str | Path,
) -> dict[str, Any]:
    original = read_json_file(audit_path)
    return replay_from_audit_payload(
        audit_payload=original,
        model_config_path=model_config_path,
        policy_config_path=policy_config_path,
    )


def replay_from_audit_payload(
    *,
    audit_payload: dict[str, Any] | Any,
    model_config_path: str | Path,
    policy_config_path: str | Path,
) -> dict[str, Any]:
    from causal_credit_risk.cli import run_decision

    if not isinstance(audit_payload, dict):
        raise ReplayValidationError("Replay audit payload must be a JSON object")
    original = dict(audit_payload)

    original_model_id = _require_field(original, "model_id")
    original_model_version = _require_field(original, "model_version")
    original_policy_version = _require_field(original, "policy_version")

    model = CausalDAGModel.from_json(model_config_path)
    policy = PolicyConfig.from_json(policy_config_path)

    if original_model_id != model.config.model_id:
        raise ReplayValidationError(
            f"Replay model_id mismatch: audit={original_model_id}, active={model.config.model_id}"
        )
    if original_model_version != model.config.model_version:
        raise ReplayValidationError(
            "Replay model_version mismatch: "
            + f"audit={original_model_version}, active={model.config.model_version}"
        )
    if original_policy_version != policy.policy_version:
        raise ReplayValidationError(
            f"Replay policy_version mismatch: audit={original_policy_version}, active={policy.policy_version}"
        )

    baseline_evidence = original.get("input_evidence", {})
    if not isinstance(baseline_evidence, dict):
        raise ReplayValidationError("Replay input_evidence must be a JSON object")
    tenant_id = str(original.get("tenant_id", "default"))

    counterfactuals = original.get("counterfactuals", [])
    if not isinstance(counterfactuals, list):
        raise ReplayValidationError("Replay counterfactuals must be a JSON array")

    intervention_scenarios = []
    for item in counterfactuals:
        if not isinstance(item, dict):
            raise ReplayValidationError("Replay counterfactual entries must be JSON objects")
        if "intervention_evidence" not in item:
            continue
        intervention = item["intervention_evidence"]
        if not isinstance(intervention, dict):
            raise ReplayValidationError("intervention_evidence must be a JSON object")
        intervention_scenarios.append(intervention)

    replayed = run_decision(
        model_config_path=model_config_path,
        policy_config_path=policy_config_path,
        evidence=baseline_evidence,
        intervention_scenarios=intervention_scenarios,
        tenant_id=tenant_id,
    ).to_dict()

    return {
        "original_decision_id": original.get("decision_id"),
        "replayed_decision_id": replayed.get("decision_id"),
        "tenant_id": replayed.get("tenant_id", tenant_id),
        "model_id": replayed.get("model_id"),
        "model_version": replayed.get("model_version"),
        "policy_version": replayed.get("policy_version"),
        "input_evidence": replayed.get("input_evidence"),
        "original_risk_probability": original.get("risk_probability"),
        "replayed_risk_probability": replayed.get("risk_probability"),
        "risk_probability_match": original.get("risk_probability")
        == replayed.get("risk_probability"),
        "original_decision": original.get("decision"),
        "replayed_decision": replayed.get("decision"),
        "decision_match": original.get("decision") == replayed.get("decision"),
    }
