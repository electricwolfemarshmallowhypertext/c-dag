from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import sys
import uuid


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def test_cli_json_only_outputs_valid_json() -> None:
    env = dict(os.environ)
    env["PYTHONPATH"] = str(PROJECT_ROOT / "src")

    result = subprocess.run(
        [sys.executable, "-m", "causal_credit_risk.cli", "--json-only"],
        cwd=PROJECT_ROOT,
        env=env,
        check=True,
        capture_output=True,
        text=True,
    )
    payload = json.loads(result.stdout)
    assert payload["model_id"] == "credit_risk_causal_dag"
    assert isinstance(payload["risk_probability"], float)
    assert payload["risk_probability"] == 0.849375
    assert "audit_chain" in payload
    assert "audit_hash" in payload["audit_chain"]

    bad = subprocess.run(
        [
            sys.executable,
            "-m",
            "causal_credit_risk.cli",
            "--json-only",
            "--evidence-json",
            "{bad json}",
        ],
        cwd=PROJECT_ROOT,
        env=env,
        check=False,
        capture_output=True,
        text=True,
    )
    assert bad.returncode != 0
    combined = (bad.stdout or "") + (bad.stderr or "")
    assert "Invalid JSON" in combined
    assert "usage:" in combined.lower()


def test_cli_fairness_command_outputs_json() -> None:
    env = dict(os.environ)
    env["PYTHONPATH"] = str(PROJECT_ROOT / "src")

    fairness_csv = PROJECT_ROOT / "tests" / f"__tmp_fairness_{uuid.uuid4().hex}.csv"
    fairness_csv.write_text(
        "segment,decision,risk_probability\nA,APPROVE,0.2\nB,DECLINE,0.8\n",
        encoding="utf-8",
    )
    try:
        result = subprocess.run(
            [
                sys.executable,
                "-m",
                "causal_credit_risk.cli",
                "--fairness-input-csv",
                str(fairness_csv),
                "--fairness-subgroup-column",
                "segment",
            ],
            cwd=PROJECT_ROOT,
            env=env,
            check=True,
            capture_output=True,
            text=True,
        )
        payload = json.loads(result.stdout)
        assert payload["subgroup_column"] == "segment"
        assert "A" in payload["subgroups"]
        assert "audit_chain" in payload
    finally:
        fairness_csv.unlink(missing_ok=True)
