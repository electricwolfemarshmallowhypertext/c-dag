from __future__ import annotations

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


def _write_rows(path: Path, rows: list[str]) -> None:
    path.write_text(
        "source_dataset,source_record_id,tenant_id,tenure,utilization,income,dsc,risk,segment,loan_age_months\n"
        + "\n".join(rows)
        + "\n",
        encoding="utf-8",
    )


def test_holdout_validation_script_runs_and_emits_metrics() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        tmp_dir = Path(tmp)
        train_csv = tmp_dir / "train.csv"
        test_csv = tmp_dir / "test.csv"
        output_dir = tmp_dir / "holdout_out"

        _write_rows(
            train_csv,
            [
                "freddie_mac_sf_loan_level,t1,default,short,high,unstable,below_threshold,high_risk,TX,12",
                "freddie_mac_sf_loan_level,t2,default,long,low,stable,above_threshold,low_risk,CA,48",
                "freddie_mac_sf_loan_level,t3,default,short,high,unstable,below_threshold,high_risk,FL,18",
                "fannie_mae_sf_performance,t4,default,long,low,stable,above_threshold,low_risk,NY,60",
                "fannie_mae_sf_performance,t5,default,short,high,unstable,below_threshold,high_risk,IL,6",
                "fannie_mae_sf_performance,t6,default,long,low,stable,above_threshold,low_risk,WA,72",
                "fannie_mae_sf_performance,t7,default,short,high,unstable,below_threshold,high_risk,GA,9",
                "fannie_mae_sf_performance,t8,default,long,low,stable,above_threshold,low_risk,AZ,84",
            ],
        )

        _write_rows(
            test_csv,
            [
                "fannie_mae_sf_performance,h1,default,short,high,unstable,below_threshold,high_risk,TX,90",
                "fannie_mae_sf_performance,h2,default,long,low,stable,above_threshold,low_risk,CA,91",
                "fannie_mae_sf_performance,h3,default,short,high,unstable,below_threshold,high_risk,FL,92",
                "fannie_mae_sf_performance,h4,default,long,low,stable,above_threshold,low_risk,WA,93",
            ],
        )

        result = _run(
            [
                "scripts/run_holdout_validation.py",
                "--train-input",
                str(train_csv),
                "--test-input",
                str(test_csv),
                "--output-dir",
                str(output_dir),
                "--max-audits",
                "4",
                "--skip-evidence-pack",
            ]
        )
        assert result.returncode == 0, result.stderr

        summary = json.loads((output_dir / "holdout_validation_summary.json").read_text(encoding="utf-8"))
        assert summary["status"] == "completed"
        assert summary["train_rows"] == 8
        assert summary["test_rows"] == 4
        assert summary["baseline_features"] == ["tenure", "utilization"]
        assert summary["calibrated_features"] == ["tenure", "utilization", "income", "dsc"]
        assert summary["replay_success_rate"] == 1.0
        assert summary["audit_chain_valid"] is True
        assert "decision_distribution" in summary
        assert "decision_distribution_before" in summary
        assert "decision_distribution_after" in summary
        assert "metrics" in summary
        assert "metrics_before" in summary
        assert "metrics_after" in summary
        assert summary["metrics"]["auc"] is not None
        assert summary["metrics"]["pr_auc"] is not None
        assert isinstance(summary["metrics"]["brier_score"], float)
        bucket_total = sum(int(bucket["count"]) for bucket in summary["metrics"]["calibration_buckets"])
        assert bucket_total == summary["test_rows"]
        assert summary["policy_after"]["policy_version"].endswith(".holdout_calibrated")
        assert (output_dir / "calibrated_policy.holdout.json").exists()
        assert "guardrails" in summary
        assert summary["guardrails"]["underpowered"] is True
        assert "data_profile" in summary
