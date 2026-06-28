"""Compliance-support package generation and restore helpers."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import shutil
from typing import Any, Mapping

from causal_credit_risk.audit_chain import canonical_json
from causal_credit_risk.controls import (
    control_references_from_mapping,
    load_control_registry,
    map_controls,
)
from causal_credit_risk.governance import (
    compute_governance_replay_hash,
    replay_governance_artifact_payload,
    validate_governance_artifact,
)
from causal_credit_risk.io_utils import read_json_file


PACKAGE_TYPE = "cdag_compliance_evidence_package"
PACKAGE_VERSION = "1.0.0"


def _stable_hash(payload: Any) -> str:
    return hashlib.sha256(canonical_json(payload).encode("utf-8")).hexdigest()


def _write_json(path: Path, payload: Any) -> None:
    path.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _json_file_hash(path: Path) -> str:
    return _stable_hash(read_json_file(path))


def _metadata_from_config(path: str | Path, fields: list[str]) -> dict[str, Any]:
    config = read_json_file(path)
    if not isinstance(config, dict):
        raise ValueError(f"Config must be a JSON object: {path}")
    metadata = {field: config.get(field) for field in fields if field in config}
    metadata["config_file"] = Path(path).name
    return metadata


def _artifact_with_control_references(
    artifact: Mapping[str, Any],
    registry: Mapping[str, Any],
) -> tuple[dict[str, Any], dict[str, Any]]:
    updated = dict(artifact)
    initial_mapping = map_controls(updated, registry=registry)
    updated["control_references"] = control_references_from_mapping(initial_mapping)
    updated["replay_hash"] = compute_governance_replay_hash(updated)
    final_mapping = map_controls(updated, registry=registry)
    updated["control_references"] = control_references_from_mapping(final_mapping)
    updated["replay_hash"] = compute_governance_replay_hash(updated)
    validate_governance_artifact(updated)
    return updated, map_controls(updated, registry=registry)


def _stable_replay_verification(report: Mapping[str, Any]) -> dict[str, Any]:
    stable = dict(report)
    replay_report = stable.get("replay_report")
    if isinstance(replay_report, Mapping):
        stable["replay_report"] = {
            key: value
            for key, value in replay_report.items()
            if key != "replayed_decision_id"
        }
    return stable


def build_compliance_package_payload(
    *,
    governance_artifact: Mapping[str, Any],
    model_config_path: str | Path,
    policy_config_path: str | Path,
    fairness_report: Mapping[str, Any] | None = None,
    control_registry: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    registry = dict(control_registry or load_control_registry())
    artifact, control_mappings = _artifact_with_control_references(governance_artifact, registry)
    replay_verification = _stable_replay_verification(replay_governance_artifact_payload(
        artifact=artifact,
        model_config_path=model_config_path,
        policy_config_path=policy_config_path,
    ))
    audit_chain_verification = {
        "valid": bool(replay_verification.get("audit_chain_hash_match")),
        "records_checked": 1,
        "audit_chain_hash": artifact.get("audit_chain_hash"),
    }
    model_metadata = _metadata_from_config(
        model_config_path,
        ["model_id", "model_version", "description"],
    )
    policy_metadata = _metadata_from_config(
        policy_config_path,
        ["policy_id", "policy_version", "risk_outcome_node", "high_risk_state"],
    )
    package_files = [
        "governance_artifact.json",
        "replay_verification.json",
        "audit_chain_verification.json",
        "fairness_report.json",
        "model_metadata.json",
        "policy_metadata.json",
        "control_mappings.json",
    ]
    evidence_manifest = {
        "manifest_version": PACKAGE_VERSION,
        "package_type": PACKAGE_TYPE,
        "contents": [
            {"path": path, "sha256": ""}
            for path in package_files
        ],
    }
    components = {
        "governance_artifact": artifact,
        "replay_verification": replay_verification,
        "audit_chain_verification": audit_chain_verification,
        "fairness_report": dict(fairness_report or {}),
        "model_metadata": model_metadata,
        "policy_metadata": policy_metadata,
        "control_mappings": control_mappings,
        "evidence_manifest": evidence_manifest,
    }
    integrity_hashes = {
        key: _stable_hash(value)
        for key, value in sorted(components.items())
        if key != "evidence_manifest"
    }
    components["integrity_hashes"] = integrity_hashes
    components["evidence_manifest"] = {
        **evidence_manifest,
        "contents": [
            {"path": item["path"], "sha256": integrity_hashes[item["path"].replace(".json", "")]}
            if item["path"].replace(".json", "") in integrity_hashes
            else item
            for item in evidence_manifest["contents"]
        ],
    }
    return components


def export_compliance_package(
    *,
    output_dir: str | Path,
    governance_artifact: Mapping[str, Any],
    model_config_path: str | Path,
    policy_config_path: str | Path,
    fairness_report: Mapping[str, Any] | None = None,
    control_registry: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    target = Path(output_dir)
    target.mkdir(parents=True, exist_ok=True)
    package = build_compliance_package_payload(
        governance_artifact=governance_artifact,
        model_config_path=model_config_path,
        policy_config_path=policy_config_path,
        fairness_report=fairness_report,
        control_registry=control_registry,
    )
    file_map = {
        "governance_artifact.json": package["governance_artifact"],
        "replay_verification.json": package["replay_verification"],
        "audit_chain_verification.json": package["audit_chain_verification"],
        "fairness_report.json": package["fairness_report"],
        "model_metadata.json": package["model_metadata"],
        "policy_metadata.json": package["policy_metadata"],
        "control_mappings.json": package["control_mappings"],
        "evidence_manifest.json": package["evidence_manifest"],
        "integrity_hashes.json": package["integrity_hashes"],
    }
    for name, payload in file_map.items():
        _write_json(target / name, payload)

    shutil.copy2(model_config_path, target / Path(model_config_path).name)
    shutil.copy2(policy_config_path, target / Path(policy_config_path).name)
    return {
        "package_type": PACKAGE_TYPE,
        "package_dir": str(target),
        "files": sorted(file_map),
        "integrity_hashes": package["integrity_hashes"],
    }


def import_compliance_package(package_dir: str | Path) -> dict[str, Any]:
    source = Path(package_dir)
    manifest_path = source / "evidence_manifest.json"
    hashes_path = source / "integrity_hashes.json"
    manifest = read_json_file(manifest_path)
    stored_hashes = read_json_file(hashes_path)
    if not isinstance(manifest, dict) or not isinstance(stored_hashes, dict):
        raise ValueError("Compliance package manifest and integrity hashes must be JSON objects")

    recomputed: dict[str, str] = {}
    for item in manifest.get("contents", []):
        if not isinstance(item, dict):
            continue
        path = str(item.get("path", ""))
        if not path:
            continue
        key = path.replace(".json", "")
        recomputed[key] = _json_file_hash(source / path)

    integrity_valid = all(stored_hashes.get(key) == value for key, value in recomputed.items())
    return {
        "package_type": manifest.get("package_type"),
        "package_dir": str(source),
        "integrity_valid": integrity_valid,
        "integrity_hashes": recomputed,
        "governance_artifact": read_json_file(source / "governance_artifact.json"),
        "replay_verification": read_json_file(source / "replay_verification.json"),
        "control_mappings": read_json_file(source / "control_mappings.json"),
    }
