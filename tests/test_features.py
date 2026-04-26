from __future__ import annotations

import csv
import json
from pathlib import Path
import uuid

import pytest

from causal_credit_risk.batch import run_batch_csv
from causal_credit_risk.cli import run_decision
from causal_credit_risk.model import CausalDAGModel
from causal_credit_risk.replay import ReplayValidationError, replay_from_audit_file
from causal_credit_risk.visualization import to_dot


PROJECT_ROOT = Path(__file__).resolve().parents[1]
MODEL_CONFIG_PATH = PROJECT_ROOT / "configs" / "credit_risk_model.v1.json"
POLICY_CONFIG_PATH = PROJECT_ROOT / "configs" / "decision_policy.v1.json"


def test_replay_matches_saved_audit_and_enforces_contracts() -> None:
    audit = run_decision(
        model_config_path=MODEL_CONFIG_PATH,
        policy_config_path=POLICY_CONFIG_PATH,
    )
    audit_path = PROJECT_ROOT / "tests" / f"__tmp_audit_{uuid.uuid4().hex}.json"
    audit_payload = audit.to_dict()
    audit_path.write_text(json.dumps(audit_payload, indent=2), encoding="utf-8-sig")
    try:
        replay = replay_from_audit_file(
            audit_path=audit_path,
            model_config_path=MODEL_CONFIG_PATH,
            policy_config_path=POLICY_CONFIG_PATH,
        )
        assert replay["risk_probability_match"] is True
        assert replay["decision_match"] is True

        mismatch_path = PROJECT_ROOT / "tests" / f"__tmp_audit_mismatch_{uuid.uuid4().hex}.json"
        try:
            for field, value in [
                ("model_id", "other_model"),
                ("model_version", "999.0.0"),
                ("policy_version", "999.0.0"),
            ]:
                modified = dict(audit_payload)
                modified[field] = value
                mismatch_path.write_text(
                    json.dumps(modified, indent=2),
                    encoding="utf-8-sig",
                )
                with pytest.raises(ReplayValidationError, match=field):
                    replay_from_audit_file(
                        audit_path=mismatch_path,
                        model_config_path=MODEL_CONFIG_PATH,
                        policy_config_path=POLICY_CONFIG_PATH,
                    )
        finally:
            mismatch_path.unlink(missing_ok=True)
    finally:
        audit_path.unlink(missing_ok=True)


def test_batch_csv_mode_is_strict_and_reports_row_errors() -> None:
    # BOM-prefixed + whitespace headers must normalize and preserve evidence.
    bom_input = PROJECT_ROOT / "tests" / f"__tmp_batch_bom_{uuid.uuid4().hex}.csv"
    bom_output = PROJECT_ROOT / "tests" / f"__tmp_batch_bom_out_{uuid.uuid4().hex}.csv"
    bom_input.write_text(
        " tenure , utilization \nshort,high\nlong,low\n",
        encoding="utf-8-sig",
    )
    try:
        summary = run_batch_csv(
            model_config_path=MODEL_CONFIG_PATH,
            policy_config_path=POLICY_CONFIG_PATH,
            csv_input_path=bom_input,
            csv_output_path=bom_output,
        )
        assert summary["rows_processed"] == 2
        assert summary["rows_failed"] == 0
        with bom_output.open("r", encoding="utf-8", newline="") as fh:
            rows = list(csv.DictReader(fh))
        assert rows[0]["status"] == "ok"
        assert rows[0]["risk_probability"] == "0.849375"
        assert rows[0]["audit_hash"] != ""
        assert rows[1]["status"] == "ok"
    finally:
        bom_input.unlink(missing_ok=True)
        bom_output.unlink(missing_ok=True)

    # Missing required observed columns must fail fast.
    missing_cols_input = PROJECT_ROOT / "tests" / f"__tmp_batch_missing_{uuid.uuid4().hex}.csv"
    missing_cols_output = PROJECT_ROOT / "tests" / f"__tmp_batch_missing_out_{uuid.uuid4().hex}.csv"
    missing_cols_input.write_text("tenure\nshort\n", encoding="utf-8")
    try:
        with pytest.raises(ValueError, match="missing required observed columns"):
            run_batch_csv(
                model_config_path=MODEL_CONFIG_PATH,
                policy_config_path=POLICY_CONFIG_PATH,
                csv_input_path=missing_cols_input,
                csv_output_path=missing_cols_output,
            )
    finally:
        missing_cols_input.unlink(missing_ok=True)
        missing_cols_output.unlink(missing_ok=True)

    # Unknown columns fail in strict mode.
    unknown_cols_input = PROJECT_ROOT / "tests" / f"__tmp_batch_unknown_{uuid.uuid4().hex}.csv"
    unknown_cols_output = PROJECT_ROOT / "tests" / f"__tmp_batch_unknown_out_{uuid.uuid4().hex}.csv"
    unknown_cols_input.write_text(
        "tenure,utilization,extra_col\nshort,high,x\n",
        encoding="utf-8",
    )
    try:
        with pytest.raises(ValueError, match="unknown columns in strict mode"):
            run_batch_csv(
                model_config_path=MODEL_CONFIG_PATH,
                policy_config_path=POLICY_CONFIG_PATH,
                csv_input_path=unknown_cols_input,
                csv_output_path=unknown_cols_output,
            )
    finally:
        unknown_cols_input.unlink(missing_ok=True)
        unknown_cols_output.unlink(missing_ok=True)

    # Invalid or missing row evidence must emit row-level errors, not silent partial inference.
    row_error_input = PROJECT_ROOT / "tests" / f"__tmp_batch_rowerr_{uuid.uuid4().hex}.csv"
    row_error_output = PROJECT_ROOT / "tests" / f"__tmp_batch_rowerr_out_{uuid.uuid4().hex}.csv"
    row_error_input.write_text(
        "tenure,utilization\nshort,high\ninvalid_state,low\nlong,\n",
        encoding="utf-8",
    )
    try:
        summary = run_batch_csv(
            model_config_path=MODEL_CONFIG_PATH,
            policy_config_path=POLICY_CONFIG_PATH,
            csv_input_path=row_error_input,
            csv_output_path=row_error_output,
        )
        assert summary["rows_processed"] == 3
        assert summary["rows_failed"] == 2
        with row_error_output.open("r", encoding="utf-8", newline="") as fh:
            rows = list(csv.DictReader(fh))
        assert rows[0]["status"] == "ok"
        assert rows[1]["status"] == "error"
        assert rows[2]["status"] == "error"
        assert rows[1]["decision"] == ""
        assert rows[2]["risk_probability"] == ""
    finally:
        row_error_input.unlink(missing_ok=True)
        row_error_output.unlink(missing_ok=True)


def test_batch_csv_with_subgroup_passthrough() -> None:
    input_path = PROJECT_ROOT / "tests" / f"__tmp_batch_group_{uuid.uuid4().hex}.csv"
    output_path = PROJECT_ROOT / "tests" / f"__tmp_batch_group_out_{uuid.uuid4().hex}.csv"
    input_path.write_text(
        "tenure,utilization,segment\nshort,high,A\nlong,low,B\n",
        encoding="utf-8",
    )
    try:
        summary = run_batch_csv(
            model_config_path=MODEL_CONFIG_PATH,
            policy_config_path=POLICY_CONFIG_PATH,
            csv_input_path=input_path,
            csv_output_path=output_path,
            subgroup_column="segment",
        )
        assert summary["rows_failed"] == 0
        with output_path.open("r", encoding="utf-8", newline="") as fh:
            rows = list(csv.DictReader(fh))
        assert rows[0]["segment"] == "A"
        assert rows[1]["segment"] == "B"
    finally:
        input_path.unlink(missing_ok=True)
        output_path.unlink(missing_ok=True)


def test_dot_export_contains_expected_edges() -> None:
    model = CausalDAGModel.from_json(MODEL_CONFIG_PATH)
    dot = to_dot(model)
    assert '"tenure" -> "income";' in dot
    assert '"income" -> "dsc";' in dot
    assert '"dsc" -> "risk";' in dot
