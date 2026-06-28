from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def _env() -> dict[str, str]:
    env = dict(os.environ)
    env["PYTHONPATH"] = str(PROJECT_ROOT / "src")
    return env


def test_cpd_estimation_script_creates_draft_output() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        tmp_dir = Path(tmp)
        input_csv = tmp_dir / "cpd_input.csv"
        output_json = tmp_dir / "draft_model.json"
        input_csv.write_text(
            "tenure,utilization\nshort,high\nlong,low\nshort,high\n",
            encoding="utf-8",
        )

        result = subprocess.run(
            [
                sys.executable,
                "scripts/estimate_cpds_from_csv.py",
                "--input-csv",
                str(input_csv),
                "--output",
                str(output_json),
                "--source-dataset-reference",
                "unit_test_dataset",
            ],
            cwd=PROJECT_ROOT,
            env=_env(),
            check=False,
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0, result.stderr
        payload = json.loads(output_json.read_text(encoding="utf-8"))
        assert payload["estimation_metadata"]["approval_status"] == "draft"
        assert payload["estimation_metadata"]["source_dataset_reference"] == "unit_test_dataset"


def test_export_evidence_pack_script_creates_expected_files() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        tmp_dir = Path(tmp)
        result = subprocess.run(
            [
                sys.executable,
                "scripts/export_evidence_pack.py",
                "--input-csv",
                "examples/input.csv",
                "--output-dir",
                str(tmp_dir),
            ],
            cwd=PROJECT_ROOT,
            env=_env(),
            check=False,
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0, result.stderr
        for name in [
            "batch_output.csv",
            "fairness_report.json",
            "audit_chain.json",
            "audit_chain_verify.json",
            "evidence_pack_manifest.json",
            "governance_artifact.json",
            "governance_replay_result.json",
            "replay_result.json",
            "metadata.json",
            "credit_risk_model.v1.json",
            "decision_policy.v1.json",
        ]:
            assert (tmp_dir / name).exists(), name


def test_run_end_to_end_demo_script() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        tmp_dir = Path(tmp)
        result = subprocess.run(
            [
                sys.executable,
                "scripts/run_end_to_end_demo.py",
                "--input-csv",
                "examples/input.csv",
                "--output-dir",
                str(tmp_dir),
            ],
            cwd=PROJECT_ROOT,
            env=_env(),
            check=False,
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0, result.stderr
        summary = json.loads((tmp_dir / "summary.json").read_text(encoding="utf-8"))
        assert summary["replay_match"] is True
        assert summary["audit_chain_valid"] is True
