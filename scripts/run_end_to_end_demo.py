"""Run local end-to-end workflow: CSV -> batch -> fairness -> audit chain -> replay."""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
import sys
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from causal_credit_risk.audit_chain import build_audit_chain_record, verify_audit_chain
from causal_credit_risk.batch import run_batch_csv
from causal_credit_risk.cli import run_decision
from causal_credit_risk.fairness import compute_fairness_report
from causal_credit_risk.replay import replay_from_audit_payload


def project_root() -> Path:
    return ROOT


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as fh:
        reader = csv.DictReader(fh)
        if reader.fieldnames is None:
            raise ValueError(f"CSV file is missing headers: {path}")
        return [dict(row) for row in reader]


def _resolve_subgroup(rows: list[dict[str, str]]) -> str | None:
    if not rows:
        return None
    if "segment" in rows[0]:
        return "segment"
    return None


def run_demo(input_csv: Path, output_dir: Path) -> dict[str, Any]:
    root = project_root()
    model_path = root / "configs" / "credit_risk_model.v1.json"
    policy_path = root / "configs" / "decision_policy.v1.json"
    output_dir.mkdir(parents=True, exist_ok=True)

    source_rows = _read_csv(input_csv)
    subgroup_column = _resolve_subgroup(source_rows)

    batch_output = output_dir / "batch_output.csv"
    batch_summary = run_batch_csv(
        model_config_path=model_path,
        policy_config_path=policy_path,
        csv_input_path=input_csv,
        csv_output_path=batch_output,
        subgroup_column=subgroup_column,
    )

    batch_rows = _read_csv(batch_output)
    fairness_report = compute_fairness_report(
        batch_rows,
        subgroup_column=subgroup_column or "segment",
        min_sample_size=2,
    )
    fairness_path = output_dir / "fairness_report.json"
    fairness_path.write_text(json.dumps(fairness_report, indent=2), encoding="utf-8")

    chain_records: list[dict[str, Any]] = []
    previous_hash: str | None = None
    chain_index = 0
    for row in source_rows:
        evidence = {k: v for k, v in row.items() if k in {"tenure", "utilization"}}
        tenant_id = str(row.get("tenant_id", "default")).strip() or "default"
        audit = run_decision(
            model_config_path=model_path,
            policy_config_path=policy_path,
            evidence=evidence,
            tenant_id=tenant_id,
        ).to_dict()
        chain_record = build_audit_chain_record(
            audit,
            chain_index=chain_index,
            previous_hash=previous_hash,
            tenant_id=tenant_id,
        )
        chain_records.append(chain_record)
        previous_hash = str(chain_record["audit_hash"])
        chain_index += 1

    chain_path = output_dir / "audit_chain.json"
    chain_path.write_text(json.dumps(chain_records, indent=2), encoding="utf-8")
    chain_valid = verify_audit_chain(chain_records)

    replay_result = replay_from_audit_payload(
        audit_payload=chain_records[0]["audit_record"],
        model_config_path=model_path,
        policy_config_path=policy_path,
    )
    replay_path = output_dir / "replay_result.json"
    replay_path.write_text(json.dumps(replay_result, indent=2), encoding="utf-8")

    summary = {
        "input_csv": str(input_csv),
        "batch_summary": batch_summary,
        "fairness_report_path": str(fairness_path),
        "audit_chain_path": str(chain_path),
        "audit_chain_valid": chain_valid,
        "replay_result_path": str(replay_path),
        "replay_match": bool(
            replay_result.get("risk_probability_match") and replay_result.get("decision_match")
        ),
    }
    summary_path = output_dir / "summary.json"
    summary_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    return summary


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run end-to-end local demo workflow.")
    parser.add_argument(
        "--input-csv",
        default=None,
        help="CSV input path. Defaults to examples/batch_with_segments.csv if present, else examples/input.csv",
    )
    parser.add_argument(
        "--output-dir",
        default="outputs/demo",
        help="Output directory for generated demo artifacts.",
    )
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    root = project_root()
    default_input = root / "examples" / "batch_with_segments.csv"
    fallback_input = root / "examples" / "input.csv"
    input_path = Path(args.input_csv) if args.input_csv else (default_input if default_input.exists() else fallback_input)
    summary = run_demo(input_path, Path(args.output_dir))
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
