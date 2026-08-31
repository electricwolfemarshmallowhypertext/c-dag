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


def test_opaque_mortgage_benchmark_runs_on_normalized_fixture() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        tmp_dir = Path(tmp)
        input_csv = tmp_dir / "mortgage.csv"
        output_dir = tmp_dir / "opaque_out"

        fieldnames = [
            "source_dataset",
            "source_record_id",
            "tenant_id",
            "tenure",
            "utilization",
            "income",
            "dsc",
            "risk",
            "segment",
            "race",
            "sex",
            "ltv_ratio",
            "cltv_ratio",
            "dti_ratio",
            "credit_score",
            "loan_age_months",
            "delinquency_status",
            "occupancy_status",
            "loan_purpose",
            "property_type",
            "modification_flag",
            "zero_balance_code",
        ]
        rows = [
            ["freddie_mac_sf_loan_level", "r1", "default", "short", "high", "unstable", "below_threshold", "high_risk", "A", "1", "1", "96", "98", "52", "620", "8", "4", "I", "C", "CO", "Y", ""],
            ["freddie_mac_sf_loan_level", "r2", "default", "long", "low", "stable", "above_threshold", "low_risk", "B", "2", "2", "62", "64", "28", "760", "50", "0", "P", "P", "SF", "N", ""],
            ["freddie_mac_sf_loan_level", "r3", "default", "short", "high", "unstable", "below_threshold", "high_risk", "A", "1", "2", "92", "94", "48", "650", "16", "3", "S", "C", "MH", "N", "03"],
            ["freddie_mac_sf_loan_level", "r4", "default", "long", "low", "stable", "above_threshold", "low_risk", "B", "2", "1", "70", "72", "34", "720", "80", "0", "P", "R", "SF", "N", ""],
            ["fannie_mae_sf_performance", "r5", "default", "short", "high", "unstable", "below_threshold", "high_risk", "A", "1", "1", "88", "90", "47", "660", "10", "5", "I", "C", "CO", "Y", ""],
            ["fannie_mae_sf_performance", "r6", "default", "long", "low", "stable", "above_threshold", "low_risk", "B", "2", "2", "66", "68", "30", "780", "72", "0", "P", "P", "SF", "N", ""],
            ["fannie_mae_sf_performance", "r7", "default", "short", "high", "unstable", "below_threshold", "high_risk", "A", "1", "2", "97", "99", "55", "610", "6", "RA", "S", "C", "MH", "N", ""],
            ["fannie_mae_sf_performance", "r8", "default", "long", "low", "stable", "above_threshold", "low_risk", "B", "2", "1", "58", "60", "24", "800", "90", "0", "P", "P", "SF", "N", ""],
        ]

        with input_csv.open("w", encoding="utf-8", newline="") as fh:
            writer = csv.writer(fh)
            writer.writerow(fieldnames)
            writer.writerows(rows)

        result = _run(
            [
                "scripts/run_opaque_mortgage_benchmark.py",
                "--input",
                str(input_csv),
                "--output-dir",
                str(output_dir),
                "--max-rows",
                "8",
                "--max-stumps",
                "8",
            ]
        )
        assert result.returncode == 0, result.stderr

        summary = json.loads((output_dir / "opaque_mortgage_benchmark_summary.json").read_text(encoding="utf-8"))
        assert summary["status"] == "completed"
        assert summary["rows_loaded"] == 8
        assert summary["opaque_model_type"] == "deterministic_stump_ensemble"
        assert summary["surrogate_fidelity"]["row_count"] == summary["test_rows"]
        assert summary["sample_audit_trace"]["trace_type"] == "opaque_model_surrogate_trace"
        assert "not guaranteed true causal reasoning" in summary["boundary"]
