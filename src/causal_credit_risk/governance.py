"""Governance evidence artifact helpers."""

from __future__ import annotations

import hashlib
from pathlib import Path
from datetime import datetime, timezone
from typing import Any, Mapping

from causal_credit_risk.audit_chain import build_audit_chain_record, canonical_json, compute_audit_hash
from causal_credit_risk.io_utils import read_json_file
from causal_credit_risk.model import CausalDAGModel
from causal_credit_risk.replay import replay_from_audit_payload
from causal_credit_risk.schemas import PolicyConfig

ARTIFACT_TYPE = "cdag_governance_artifact"
ARTIFACT_VERSION = "1.0.0"
VALID_REVIEW_STATUSES = {"pending", "approved", "rejected", "escalated"}

BOUNDARY_METADATA = {
    "intended_use": "Governance explainability and audit evidence review.",
    "not_production_lending": True,
    "not_regulatory_certification": True,
    "not_legal_advice": True,
    "not_credit_eligibility_decision": True,
    "boundary_statement": (
        "This artifact supports review workflows; it does not certify compliance, "
        "provide legal advice, or authorize production credit decisions."
    ),
}

REQUIRED_ARTIFACT_FIELDS = {
    "artifact_type",
    "artifact_version",
    "decision_id",
    "tenant_id",
    "model_id",
    "model_version",
    "policy_version",
    "input_evidence",
    "inferred_nodes",
    "risk_probability",
    "decision",
    "causal_chain",
    "counterfactuals",
    "replay_hash",
    "audit_chain_hash",
    "audit_chain",
    "validation_status",
    "timestamp_utc",
    "boundary_metadata",
}


def governance_hash_payload(artifact: Mapping[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in artifact.items() if key != "replay_hash"}


def compute_governance_replay_hash(artifact: Mapping[str, Any]) -> str:
    payload = governance_hash_payload(artifact)
    digest = hashlib.sha256(canonical_json(payload).encode("utf-8"))
    return digest.hexdigest()


def audit_payload_from_governance_artifact(artifact: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "decision_id": artifact.get("decision_id"),
        "tenant_id": artifact.get("tenant_id", "default"),
        "model_id": artifact.get("model_id"),
        "model_version": artifact.get("model_version"),
        "policy_version": artifact.get("policy_version"),
        "timestamp_utc": artifact.get("timestamp_utc"),
        "input_evidence": artifact.get("input_evidence", {}),
        "inferred_nodes": artifact.get("inferred_nodes", {}),
        "risk_probability": artifact.get("risk_probability"),
        "decision": artifact.get("decision"),
        "causal_chain": artifact.get("causal_chain", []),
        "counterfactuals": artifact.get("counterfactuals", []),
        "validation_status": artifact.get("validation_status", {}),
    }


def _human_review_fields(human_review: Mapping[str, Any] | None) -> dict[str, Any]:
    if human_review is None:
        return {}
    review = dict(human_review)
    status = review.get("review_status")
    if status is not None and status not in VALID_REVIEW_STATUSES:
        raise ValueError(
            "review_status must be one of: "
            + ", ".join(sorted(VALID_REVIEW_STATUSES))
        )
    allowed = {"reviewer_id", "review_status", "review_notes", "reviewed_at"}
    return {key: review[key] for key in allowed if key in review}


def _utc_timestamp() -> str:
    return datetime.now(tz=timezone.utc).isoformat(timespec="seconds")


def _model_lifecycle(
    audit: Mapping[str, Any],
    *,
    deployment_version: str = "local-reference",
    created_timestamp: str | None = None,
    superseded_version: str | None = None,
    change_reason: str | None = None,
) -> dict[str, Any]:
    return {
        "model_version": audit.get("model_version"),
        "policy_version": audit.get("policy_version"),
        "deployment_version": deployment_version,
        "created_timestamp": created_timestamp or audit.get("timestamp_utc"),
        "superseded_version": superseded_version,
        "change_reason": change_reason,
    }


def build_governance_artifact(
    audit_record: Mapping[str, Any],
    *,
    audit_chain_record: Mapping[str, Any] | None = None,
    chain_index: int = 0,
    previous_hash: str | None = None,
    tenant_id: str | None = None,
    human_review: Mapping[str, Any] | None = None,
    control_references: list[Mapping[str, Any]] | None = None,
    deployment_version: str = "local-reference",
    created_timestamp: str | None = None,
    superseded_version: str | None = None,
    change_reason: str | None = None,
) -> dict[str, Any]:
    audit = dict(audit_record)
    effective_tenant_id = str(tenant_id or audit.get("tenant_id", "default"))
    chain = (
        dict(audit_chain_record)
        if audit_chain_record is not None
        else build_audit_chain_record(
            audit,
            chain_index=chain_index,
            previous_hash=previous_hash,
            tenant_id=effective_tenant_id,
        )
    )

    artifact: dict[str, Any] = {
        "artifact_type": ARTIFACT_TYPE,
        "artifact_version": ARTIFACT_VERSION,
        "decision_id": audit.get("decision_id"),
        "tenant_id": effective_tenant_id,
        "model_id": audit.get("model_id"),
        "model_version": audit.get("model_version"),
        "policy_version": audit.get("policy_version"),
        "input_evidence": audit.get("input_evidence", {}),
        "inferred_nodes": audit.get("inferred_nodes", {}),
        "risk_probability": audit.get("risk_probability"),
        "decision": audit.get("decision"),
        "causal_chain": audit.get("causal_chain", []),
        "counterfactuals": audit.get("counterfactuals", []),
        "replay_hash": "",
        "audit_chain_hash": chain.get("audit_hash"),
        "audit_chain": {
            "chain_index": chain.get("chain_index"),
            "previous_hash": chain.get("previous_hash"),
            "tenant_id": chain.get("tenant_id", effective_tenant_id),
        },
        "validation_status": audit.get("validation_status", {}),
        "timestamp_utc": audit.get("timestamp_utc"),
        "boundary_metadata": dict(BOUNDARY_METADATA),
        "model_lifecycle": _model_lifecycle(
            audit,
            deployment_version=deployment_version,
            created_timestamp=created_timestamp,
            superseded_version=superseded_version,
            change_reason=change_reason,
        ),
    }
    if control_references is not None:
        artifact["control_references"] = [dict(item) for item in control_references]
    artifact.update(_human_review_fields(human_review))
    artifact["replay_hash"] = compute_governance_replay_hash(artifact)
    validate_governance_artifact(artifact)
    return artifact


def apply_review_event(
    artifact: Mapping[str, Any],
    *,
    reviewer_id: str,
    review_status: str,
    review_notes: str | None = None,
    reviewed_at: str | None = None,
) -> dict[str, Any]:
    if review_status not in VALID_REVIEW_STATUSES:
        raise ValueError(
            "review_status must be one of: "
            + ", ".join(sorted(VALID_REVIEW_STATUSES))
        )
    updated = dict(artifact)
    event = {
        "reviewer_id": reviewer_id,
        "review_status": review_status,
        "review_notes": review_notes,
        "reviewed_at": reviewed_at or _utc_timestamp(),
    }
    history = list(updated.get("review_history", []))
    history.append(event)
    updated["reviewer_id"] = reviewer_id
    updated["review_status"] = review_status
    updated["review_notes"] = review_notes
    updated["reviewed_at"] = event["reviewed_at"]
    updated["review_history"] = history
    updated["replay_hash"] = compute_governance_replay_hash(updated)
    validate_governance_artifact(updated)
    return updated


def validate_governance_artifact(artifact: Mapping[str, Any]) -> None:
    missing = sorted(REQUIRED_ARTIFACT_FIELDS.difference(artifact.keys()))
    if missing:
        raise ValueError("Governance artifact missing required fields: " + ", ".join(missing))
    if artifact.get("artifact_type") != ARTIFACT_TYPE:
        raise ValueError("Governance artifact has invalid artifact_type")
    if artifact.get("decision") not in {"APPROVE", "REVIEW", "DECLINE"}:
        raise ValueError("Governance artifact has invalid decision")
    status = artifact.get("review_status")
    if status is not None and status not in VALID_REVIEW_STATUSES:
        raise ValueError("Governance artifact has invalid review_status")
    boundary = artifact.get("boundary_metadata")
    if not isinstance(boundary, dict):
        raise ValueError("Governance artifact boundary_metadata must be an object")
    lifecycle = artifact.get("model_lifecycle")
    if lifecycle is not None and not isinstance(lifecycle, dict):
        raise ValueError("Governance artifact model_lifecycle must be an object")
    history = artifact.get("review_history")
    if history is not None and not isinstance(history, list):
        raise ValueError("Governance artifact review_history must be an array")
    for key in (
        "not_production_lending",
        "not_regulatory_certification",
        "not_legal_advice",
        "not_credit_eligibility_decision",
    ):
        if boundary.get(key) is not True:
            raise ValueError(f"Governance artifact boundary_metadata.{key} must be true")


def replay_governance_artifact_payload(
    *,
    artifact: Mapping[str, Any],
    model_config_path: str | Path,
    policy_config_path: str | Path,
) -> dict[str, Any]:
    validate_governance_artifact(artifact)
    model = CausalDAGModel.from_json(model_config_path)
    policy = PolicyConfig.from_json(policy_config_path)

    model_version_match = artifact.get("model_version") == model.config.model_version
    policy_version_match = artifact.get("policy_version") == policy.policy_version
    hash_match = compute_governance_replay_hash(artifact) == artifact.get("replay_hash")

    audit_payload = audit_payload_from_governance_artifact(artifact)
    audit_hash = compute_audit_hash(
        audit_payload,
        previous_hash=artifact.get("audit_chain", {}).get("previous_hash"),
        chain_index=artifact.get("audit_chain", {}).get("chain_index"),
        tenant_id=artifact.get("audit_chain", {}).get("tenant_id"),
    )
    audit_chain_hash_match = audit_hash == artifact.get("audit_chain_hash")

    replay_report: dict[str, Any] = {}
    risk_probability_match = False
    decision_match = False
    replay_error: str | None = None
    if model_version_match and policy_version_match:
        try:
            replay_report = replay_from_audit_payload(
                audit_payload=audit_payload,
                model_config_path=model_config_path,
                policy_config_path=policy_config_path,
            )
            risk_probability_match = bool(replay_report.get("risk_probability_match"))
            decision_match = bool(replay_report.get("decision_match"))
        except Exception as exc:  # pragma: no cover - defensive report path
            replay_error = str(exc)

    validation_status = {
        "artifact_schema_valid": True,
        "replay_verified": (
            model_version_match
            and policy_version_match
            and hash_match
            and audit_chain_hash_match
            and risk_probability_match
            and decision_match
        ),
        "source_validation_status": artifact.get("validation_status", {}),
    }
    result = {
        "decision_id": artifact.get("decision_id"),
        "tenant_id": artifact.get("tenant_id", "default"),
        "replay_match": bool(validation_status["replay_verified"]),
        "model_version_match": bool(model_version_match),
        "policy_version_match": bool(policy_version_match),
        "hash_match": bool(hash_match and audit_chain_hash_match),
        "replay_hash_match": bool(hash_match),
        "audit_chain_hash_match": bool(audit_chain_hash_match),
        "risk_probability_match": bool(risk_probability_match),
        "decision_match": bool(decision_match),
        "validation_status": validation_status,
        "version_lineage": artifact.get("model_lifecycle", {}),
    }
    if replay_error is not None:
        result["replay_error"] = replay_error
    if replay_report:
        result["replay_report"] = replay_report
    return result


def replay_governance_artifact_file(
    *,
    artifact_path: str | Path,
    model_config_path: str | Path,
    policy_config_path: str | Path,
) -> dict[str, Any]:
    artifact = read_json_file(artifact_path)
    if not isinstance(artifact, dict):
        raise ValueError("Governance artifact must be a JSON object")
    return replay_governance_artifact_payload(
        artifact=artifact,
        model_config_path=model_config_path,
        policy_config_path=policy_config_path,
    )
