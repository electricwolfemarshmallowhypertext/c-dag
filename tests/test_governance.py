from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile

from fastapi.testclient import TestClient

from causal_credit_risk.api import create_app
from causal_credit_risk.audit_chain import build_audit_chain_record
from causal_credit_risk.cli import run_decision
from causal_credit_risk.governance import (
    build_governance_artifact,
    compute_governance_replay_hash,
    replay_governance_artifact_payload,
    validate_governance_artifact,
)


PROJECT_ROOT = Path(__file__).resolve().parents[1]
MODEL_CONFIG_PATH = PROJECT_ROOT / "configs" / "credit_risk_model.v1.json"
POLICY_CONFIG_PATH = PROJECT_ROOT / "configs" / "decision_policy.v1.json"
SCHEMA_PATH = PROJECT_ROOT / "schemas" / "governance-artifact.schema.json"


def _env() -> dict[str, str]:
    env = dict(os.environ)
    env["PYTHONPATH"] = str(PROJECT_ROOT / "src")
    return env


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
    )


def test_governance_artifact_validates_against_schema_required_fields() -> None:
    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    artifact = _artifact()
    validate_governance_artifact(artifact)

    assert sorted(schema["required"]) == sorted(
        key for key in schema["required"] if key in artifact
    )
    assert artifact["model_version"] == "1.0.0"
    assert artifact["policy_version"] == "1.0.0"
    assert "reviewer_id" not in artifact
    assert "review_status" not in artifact


def test_human_review_fields_are_optional_and_validated() -> None:
    audit = run_decision(
        model_config_path=MODEL_CONFIG_PATH,
        policy_config_path=POLICY_CONFIG_PATH,
    ).to_dict()
    chain = build_audit_chain_record(audit, chain_index=0, previous_hash=None)
    artifact = build_governance_artifact(
        audit,
        audit_chain_record=chain,
        human_review={
            "reviewer_id": "reviewer-1",
            "review_status": "pending",
            "review_notes": "Needs second-line review.",
            "reviewed_at": None,
        },
    )
    assert artifact["reviewer_id"] == "reviewer-1"
    assert artifact["review_status"] == "pending"
    validate_governance_artifact(artifact)


def test_governance_replay_verification_and_tamper_hash_detection() -> None:
    artifact = _artifact()
    report = replay_governance_artifact_payload(
        artifact=artifact,
        model_config_path=MODEL_CONFIG_PATH,
        policy_config_path=POLICY_CONFIG_PATH,
    )
    assert report["replay_match"] is True
    assert report["model_version_match"] is True
    assert report["policy_version_match"] is True
    assert report["hash_match"] is True
    assert report["validation_status"]["replay_verified"] is True

    tampered = dict(artifact)
    tampered["decision"] = "APPROVE"
    assert compute_governance_replay_hash(tampered) != artifact["replay_hash"]
    tampered_report = replay_governance_artifact_payload(
        artifact=tampered,
        model_config_path=MODEL_CONFIG_PATH,
        policy_config_path=POLICY_CONFIG_PATH,
    )
    assert tampered_report["hash_match"] is False
    assert tampered_report["replay_match"] is False


def test_cli_exports_and_replays_governance_artifact(tmp_path: Path) -> None:
    artifact_path = tmp_path / "governance_artifact.json"
    export_result = subprocess.run(
        [
            sys.executable,
            "-m",
            "causal_credit_risk.cli",
            "--export-governance-artifact",
            str(artifact_path),
            "--json-only",
        ],
        cwd=PROJECT_ROOT,
        env=_env(),
        check=False,
        capture_output=True,
        text=True,
    )
    assert export_result.returncode == 0, export_result.stderr
    artifact = json.loads(artifact_path.read_text(encoding="utf-8"))
    validate_governance_artifact(artifact)

    replay_result = subprocess.run(
        [
            sys.executable,
            "-m",
            "causal_credit_risk.cli",
            "--replay-governance-artifact",
            str(artifact_path),
        ],
        cwd=PROJECT_ROOT,
        env=_env(),
        check=False,
        capture_output=True,
        text=True,
    )
    assert replay_result.returncode == 0, replay_result.stderr
    report = json.loads(replay_result.stdout)
    assert report["replay_match"] is True
    assert report["hash_match"] is True


def test_api_decision_exposes_governance_artifact_without_breaking_shape() -> None:
    app = create_app(
        model_config_path=MODEL_CONFIG_PATH,
        policy_config_path=POLICY_CONFIG_PATH,
    )
    response = TestClient(app).post(
        "/v1/decision",
        json={"tenure": "short", "utilization": "high"},
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["decision"] == "DECLINE"
    assert "audit_chain" in payload
    assert "governance_artifact" in payload
    validate_governance_artifact(payload["governance_artifact"])


def test_evidence_pack_manifest_is_deterministic() -> None:
    manifests: list[dict[str, object]] = []
    with tempfile.TemporaryDirectory() as tmp1, tempfile.TemporaryDirectory() as tmp2:
        for tmp in (tmp1, tmp2):
            result = subprocess.run(
                [
                    sys.executable,
                    "scripts/export_evidence_pack.py",
                    "--input-csv",
                    "examples/input.csv",
                    "--output-dir",
                    tmp,
                    "--max-rows",
                    "1",
                ],
                cwd=PROJECT_ROOT,
                env=_env(),
                check=False,
                capture_output=True,
                text=True,
            )
            assert result.returncode == 0, result.stderr
            manifest_path = Path(tmp) / "evidence_pack_manifest.json"
            governance_path = Path(tmp) / "governance_artifact.json"
            replay_path = Path(tmp) / "governance_replay_result.json"
            assert manifest_path.exists()
            assert governance_path.exists()
            assert replay_path.exists()
            manifests.append(json.loads(manifest_path.read_text(encoding="utf-8")))

    assert manifests[0] == manifests[1]
