from __future__ import annotations

import csv
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def _run(args: list[str]) -> subprocess.CompletedProcess[str]:
    env = dict(os.environ)
    env["PYTHONPATH"] = str(PROJECT_ROOT / "src")
    return subprocess.run(
        [sys.executable, *args],
        cwd=PROJECT_ROOT,
        env=env,
        check=False,
        capture_output=True,
        text=True,
    )


def test_prepare_cfpb_complaints_normalizes_rows() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        tmp_dir = Path(tmp)
        input_csv = tmp_dir / "complaints.csv"
        output_csv = tmp_dir / "normalized.csv"
        input_csv.write_text(
            "Date received,Product,Sub-product,Issue,Sub-issue,Consumer complaint narrative,Company public response,Company,State,ZIP code,Tags,Consumer consent provided?,Submitted via,Date sent to company,Company response to consumer,Timely response?,Consumer disputed?,Complaint ID\n"
            "2026-01-01,Credit card,,Managing an account,,Narrative text,,Example Co,TX,75001,,,Web,2026-01-02,Closed with explanation,Yes,No,1\n"
            "2026-01-02,Debt collection,,Attempts to collect debt not owed,,,,Example Co,FL,33000,,,Web,2026-01-03,Closed without relief,No,Yes,2\n",
            encoding="utf-8",
        )

        result = _run(
            [
                "scripts/prepare_cfpb_complaints.py",
                "--input",
                str(input_csv),
                "--max-rows",
                "2",
                "--output",
                str(output_csv),
            ]
        )
        assert result.returncode == 0, result.stderr

        with output_csv.open("r", encoding="utf-8", newline="") as fh:
            rows = list(csv.DictReader(fh))

        assert len(rows) == 2
        assert rows[0]["source_dataset"] == "cfpb_consumer_complaints"
        assert rows[0]["timely_response"] in {"timely", "untimely"}
        assert rows[1]["consumer_disputed"] == "disputed"
        assert rows[1]["escalation_risk"] == "high_escalation"


def test_run_cfpb_validation_with_tiny_fixture() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        tmp_dir = Path(tmp)
        input_csv = tmp_dir / "normalized.csv"
        output_dir = tmp_dir / "validation_out"

        input_csv.write_text(
            "source_dataset,source_record_id,tenant_id,product_risk,issue_complexity,company_response_quality,timely_response,consumer_disputed,escalation_risk,segment\n"
            "cfpb_consumer_complaints,c1,default,high_product_risk,complex,poor,untimely,disputed,high_escalation,TX\n"
            "cfpb_consumer_complaints,c2,default,lower_product_risk,standard,adequate,timely,not_disputed,low_escalation,CA\n"
            "cfpb_consumer_complaints,c3,default,high_product_risk,complex,adequate,timely,disputed,high_escalation,TX\n",
            encoding="utf-8",
        )

        result = _run(
            [
                "scripts/run_cfpb_complaint_validation.py",
                "--input",
                str(input_csv),
                "--output-dir",
                str(output_dir),
                "--max-audits",
                "3",
                "--skip-evidence-pack",
            ]
        )
        assert result.returncode == 0, result.stderr

        summary = json.loads((output_dir / "validation_summary.json").read_text(encoding="utf-8"))
        assert summary["status"] == "completed"
        assert summary["accepted_rows"] == 3
        assert summary["rejected_rows"] == 0
        assert summary["decision_distribution"]["APPROVE"] + summary["decision_distribution"]["REVIEW"] + summary["decision_distribution"]["DECLINE"] == 3
