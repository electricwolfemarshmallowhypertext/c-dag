from __future__ import annotations

import csv
from pathlib import Path
import uuid

import pytest

from causal_credit_risk.batch import run_batch_csv
from causal_credit_risk.fairness import compute_fairness_report


PROJECT_ROOT = Path(__file__).resolve().parents[1]
MODEL_CONFIG_PATH = PROJECT_ROOT / "configs" / "credit_risk_model.v1.json"
POLICY_CONFIG_PATH = PROJECT_ROOT / "configs" / "decision_policy.v1.json"


def test_batch_tenant_id_preserved_when_present() -> None:
    input_path = PROJECT_ROOT / "tests" / f"__tmp_tenant_batch_{uuid.uuid4().hex}.csv"
    output_path = PROJECT_ROOT / "tests" / f"__tmp_tenant_batch_out_{uuid.uuid4().hex}.csv"
    input_path.write_text(
        "tenant_id,tenure,utilization,segment\nt-1,short,high,A\nt-1,long,low,B\n",
        encoding="utf-8",
    )
    try:
        summary = run_batch_csv(
            model_config_path=MODEL_CONFIG_PATH,
            policy_config_path=POLICY_CONFIG_PATH,
            csv_input_path=input_path,
            csv_output_path=output_path,
            subgroup_column="segment",
            tenancy_mode="tenant_id",
        )
        assert summary["rows_failed"] == 0
        with output_path.open("r", encoding="utf-8", newline="") as fh:
            rows = list(csv.DictReader(fh))
        assert rows[0]["tenant_id"] == "t-1"
        assert rows[1]["tenant_id"] == "t-1"
    finally:
        input_path.unlink(missing_ok=True)
        output_path.unlink(missing_ok=True)


def test_batch_tenant_mode_requires_tenant_column() -> None:
    input_path = PROJECT_ROOT / "tests" / f"__tmp_tenant_missing_{uuid.uuid4().hex}.csv"
    output_path = PROJECT_ROOT / "tests" / f"__tmp_tenant_missing_out_{uuid.uuid4().hex}.csv"
    input_path.write_text("tenure,utilization\nshort,high\n", encoding="utf-8")
    try:
        with pytest.raises(ValueError, match="tenant_id column"):
            run_batch_csv(
                model_config_path=MODEL_CONFIG_PATH,
                policy_config_path=POLICY_CONFIG_PATH,
                csv_input_path=input_path,
                csv_output_path=output_path,
                tenancy_mode="tenant_id",
            )
    finally:
        input_path.unlink(missing_ok=True)
        output_path.unlink(missing_ok=True)


def test_fairness_report_includes_tenant_id() -> None:
    rows = [
        {"tenant_id": "t-1", "segment": "A", "decision": "APPROVE", "risk_probability": 0.2},
        {"tenant_id": "t-1", "segment": "B", "decision": "DECLINE", "risk_probability": 0.8},
    ]
    report = compute_fairness_report(rows, subgroup_column="segment", min_sample_size=1)
    assert report["tenant_id"] == "t-1"
