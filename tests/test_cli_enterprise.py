from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import sys
import uuid

from causal_credit_risk.audit_chain import build_audit_chain_record
from causal_credit_risk.cli import run_decision


PROJECT_ROOT = Path(__file__).resolve().parents[1]
MODEL_CONFIG_PATH = PROJECT_ROOT / "configs" / "credit_risk_model.v1.json"
POLICY_CONFIG_PATH = PROJECT_ROOT / "configs" / "decision_policy.v1.json"


def _env() -> dict[str, str]:
    env = dict(os.environ)
    env["PYTHONPATH"] = str(PROJECT_ROOT / "src")
    return env


def test_cli_verify_audit_chain_success_and_failure() -> None:
    audit = run_decision(
        model_config_path=MODEL_CONFIG_PATH,
        policy_config_path=POLICY_CONFIG_PATH,
        tenant_id="default",
    ).to_dict()
    r1 = build_audit_chain_record(audit, chain_index=0, previous_hash=None, tenant_id="default")
    records_path = PROJECT_ROOT / "tests" / f"__tmp_chain_{uuid.uuid4().hex}.json"
    records_path.write_text(json.dumps([r1], indent=2), encoding="utf-8")
    try:
        ok = subprocess.run(
            [
                sys.executable,
                "-m",
                "causal_credit_risk.cli",
                "--verify-audit-chain",
                str(records_path),
            ],
            cwd=PROJECT_ROOT,
            env=_env(),
            check=False,
            capture_output=True,
            text=True,
        )
        assert ok.returncode == 0
        assert json.loads(ok.stdout)["valid"] is True

        tampered = [dict(r1)]
        tampered[0]["audit_record"] = dict(tampered[0]["audit_record"])
        tampered[0]["audit_record"]["decision"] = "APPROVE"
        records_path.write_text(json.dumps(tampered, indent=2), encoding="utf-8")
        bad = subprocess.run(
            [
                sys.executable,
                "-m",
                "causal_credit_risk.cli",
                "--verify-audit-chain",
                str(records_path),
            ],
            cwd=PROJECT_ROOT,
            env=_env(),
            check=False,
            capture_output=True,
            text=True,
        )
        assert bad.returncode == 1
        assert json.loads(bad.stdout)["valid"] is False
    finally:
        records_path.unlink(missing_ok=True)


def test_cli_fairness_report_input_and_missing_subgroup_error() -> None:
    csv_path = PROJECT_ROOT / "tests" / f"__tmp_fairness_{uuid.uuid4().hex}.csv"
    csv_path.write_text(
        "segment,decision,risk_probability\nA,APPROVE,0.2\nB,DECLINE,0.8\n",
        encoding="utf-8",
    )
    try:
        ok = subprocess.run(
            [
                sys.executable,
                "-m",
                "causal_credit_risk.cli",
                "--fairness-report-input",
                str(csv_path),
                "--fairness-subgroup-column",
                "segment",
            ],
            cwd=PROJECT_ROOT,
            env=_env(),
            check=False,
            capture_output=True,
            text=True,
        )
        assert ok.returncode == 0
        payload = json.loads(ok.stdout)
        assert payload["subgroup_column"] == "segment"

        missing = subprocess.run(
            [
                sys.executable,
                "-m",
                "causal_credit_risk.cli",
                "--fairness-report-input",
                str(csv_path),
                "--fairness-subgroup-column",
                "missing_col",
            ],
            cwd=PROJECT_ROOT,
            env=_env(),
            check=False,
            capture_output=True,
            text=True,
        )
        assert missing.returncode != 0
        combined = (missing.stdout or "") + (missing.stderr or "")
        assert "Missing subgroup column" in combined
    finally:
        csv_path.unlink(missing_ok=True)
