from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys
import os

from fastapi.testclient import TestClient

from causal_credit_risk.api import create_app
from causal_credit_risk.audit_chain import build_audit_chain_record
from causal_credit_risk.cli import run_decision
from causal_credit_risk.compliance import export_compliance_package, import_compliance_package
from causal_credit_risk.controls import list_control_frameworks, load_control_registry, map_controls
from causal_credit_risk.governance import (
    apply_review_event,
    build_governance_artifact,
    replay_governance_artifact_payload,
)


PROJECT_ROOT = Path(__file__).resolve().parents[1]
MODEL_CONFIG_PATH = PROJECT_ROOT / "configs" / "credit_risk_model.v1.json"
POLICY_CONFIG_PATH = PROJECT_ROOT / "configs" / "decision_policy.v1.json"


def _artifact() -> dict[str, object]:
    audit = run_decision(
        model_config_path=MODEL_CONFIG_PATH,
        policy_config_path=POLICY_CONFIG_PATH,
    ).to_dict()
    chain = build_audit_chain_record(
        audit,
        chain_index=0,
        previous_hash=None,
        tenant_id=str(audit["tenant_id"]),
    )
    return build_governance_artifact(
        audit,
        audit_chain_record=chain,
        tenant_id=str(audit["tenant_id"]),
        deployment_version="deploy-2026-06-28",
        superseded_version="deploy-2026-01-01",
        change_reason="test lineage",
    )


def _env() -> dict[str, str]:
    env = dict(os.environ)
    env["PYTHONPATH"] = str(PROJECT_ROOT / "src")
    return env


def test_control_mappings_are_deterministic_and_config_driven() -> None:
    registry = load_control_registry()
    frameworks = list_control_frameworks(registry)
    assert {item["name"] for item in frameworks} >= {
        "NIST AI RMF",
        "ISO/IEC 42001",
        "SR 11-7 Model Risk Management",
        "EU AI Act high-risk obligations",
        "Internal custom controls",
    }

    first = map_controls(_artifact(), registry=registry)
    second = map_controls(_artifact(), registry=registry)
    assert first == second

    sr_trace = next(item for item in first["controls"] if item["id"] == "SR11-7-TRACE")
    assert sr_trace["status"] == "supported"
    assert sr_trace["evidence"] == ["replay_hash", "audit_chain", "model_version"]


def test_compliance_package_generation_and_import_are_stable(tmp_path: Path) -> None:
    artifact = _artifact()
    first_dir = tmp_path / "first"
    second_dir = tmp_path / "second"

    first = export_compliance_package(
        output_dir=first_dir,
        governance_artifact=artifact,
        model_config_path=MODEL_CONFIG_PATH,
        policy_config_path=POLICY_CONFIG_PATH,
    )
    second = export_compliance_package(
        output_dir=second_dir,
        governance_artifact=artifact,
        model_config_path=MODEL_CONFIG_PATH,
        policy_config_path=POLICY_CONFIG_PATH,
    )

    assert first["integrity_hashes"] == second["integrity_hashes"]
    first_manifest = json.loads((first_dir / "evidence_manifest.json").read_text(encoding="utf-8"))
    second_manifest = json.loads((second_dir / "evidence_manifest.json").read_text(encoding="utf-8"))
    assert first_manifest == second_manifest

    restored = import_compliance_package(first_dir)
    assert restored["integrity_valid"] is True
    replay = replay_governance_artifact_payload(
        artifact=restored["governance_artifact"],
        model_config_path=MODEL_CONFIG_PATH,
        policy_config_path=POLICY_CONFIG_PATH,
    )
    assert replay["replay_match"] is True


def test_review_lifecycle_persists_history_and_updates_hash() -> None:
    artifact = _artifact()
    pending = apply_review_event(
        artifact,
        reviewer_id="risk-reviewer",
        review_status="pending",
        review_notes="Initial assignment.",
        reviewed_at="2026-06-28T12:00:00+00:00",
    )
    approved = apply_review_event(
        pending,
        reviewer_id="risk-reviewer",
        review_status="approved",
        review_notes="Approved for internal evaluation.",
        reviewed_at="2026-06-28T12:05:00+00:00",
    )

    assert pending["review_status"] == "pending"
    assert approved["review_status"] == "approved"
    assert len(approved["review_history"]) == 2
    assert approved["replay_hash"] != artifact["replay_hash"]


def test_version_lineage_is_reported_during_replay() -> None:
    artifact = _artifact()
    lifecycle = artifact["model_lifecycle"]
    assert lifecycle["deployment_version"] == "deploy-2026-06-28"
    assert lifecycle["superseded_version"] == "deploy-2026-01-01"
    assert lifecycle["change_reason"] == "test lineage"

    replay = replay_governance_artifact_payload(
        artifact=artifact,
        model_config_path=MODEL_CONFIG_PATH,
        policy_config_path=POLICY_CONFIG_PATH,
    )
    assert replay["version_lineage"] == lifecycle


def test_cli_exports_and_imports_compliance_package(tmp_path: Path) -> None:
    package_dir = tmp_path / "package"
    export_result = subprocess.run(
        [
            sys.executable,
            "-m",
            "causal_credit_risk.cli",
            "--json-only",
            "--export-compliance-package",
            str(package_dir),
        ],
        cwd=PROJECT_ROOT,
        env=_env(),
        check=False,
        capture_output=True,
        text=True,
    )
    assert export_result.returncode == 0, export_result.stderr
    assert (package_dir / "governance_artifact.json").exists()
    assert (package_dir / "integrity_hashes.json").exists()

    import_result = subprocess.run(
        [
            sys.executable,
            "-m",
            "causal_credit_risk.cli",
            "--import-compliance-package",
            str(package_dir),
        ],
        cwd=PROJECT_ROOT,
        env=_env(),
        check=False,
        capture_output=True,
        text=True,
    )
    assert import_result.returncode == 0, import_result.stderr
    payload = json.loads(import_result.stdout)
    assert payload["integrity_valid"] is True
    assert payload["restore_replay_verification"]["replay_match"] is True


def test_compliance_api_endpoints() -> None:
    client = TestClient(
        create_app(
            model_config_path=MODEL_CONFIG_PATH,
            policy_config_path=POLICY_CONFIG_PATH,
        )
    )

    frameworks = client.get("/v1/control-frameworks")
    assert frameworks.status_code == 200
    assert frameworks.json()["registry_version"] == "1.0.0"

    mappings = client.get("/v1/control-mappings")
    assert mappings.status_code == 200
    assert mappings.json()["registry_id"] == "cdag_control_frameworks"

    package = client.post(
        "/v1/compliance-package",
        json={"tenure": "short", "utilization": "high"},
    )
    assert package.status_code == 200
    package_payload = package.json()
    assert "governance_artifact" in package_payload
    assert "control_mappings" in package_payload
    assert "integrity_hashes" in package_payload

    review = client.post(
        "/v1/review",
        json={
            "governance_artifact": package_payload["governance_artifact"],
            "reviewer_id": "reviewer-1",
            "review_status": "escalated",
            "review_notes": "Needs second-line review.",
            "reviewed_at": "2026-06-28T12:00:00+00:00",
        },
    )
    assert review.status_code == 200
    reviewed_artifact = review.json()["governance_artifact"]
    assert reviewed_artifact["review_status"] == "escalated"
    assert len(reviewed_artifact["review_history"]) == 1
