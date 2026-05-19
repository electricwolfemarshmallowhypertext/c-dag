"""Run public CFPB complaint-data validation workflow.

WARNING:
This is public CFPB complaint-data validation for governance testing.
It is not production validation and not credit-eligibility scoring.
"""

from __future__ import annotations

import argparse
import csv
from datetime import datetime, timezone
import json
from pathlib import Path
import sys
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from causal_credit_risk.audit_chain import verify_audit_chain
from causal_credit_risk.batch import run_batch_csv
from causal_credit_risk.cli import run_decision
from causal_credit_risk.cpd_estimation import build_draft_model_config
from causal_credit_risk.fairness import compute_fairness_report
from causal_credit_risk.replay import replay_from_audit_payload
from export_evidence_pack import export_evidence_pack


REQUIRED_COLUMNS: tuple[str, ...] = (
    "source_dataset",
    "source_record_id",
    "product_risk",
    "issue_complexity",
    "company_response_quality",
    "timely_response",
    "consumer_disputed",
    "escalation_risk",
    "segment",
)

ALLOWED_STATES: dict[str, set[str]] = {
    "product_risk": {"high_product_risk", "lower_product_risk"},
    "issue_complexity": {"complex", "standard"},
    "company_response_quality": {"poor", "adequate"},
    "timely_response": {"untimely", "timely"},
    "consumer_disputed": {"disputed", "not_disputed"},
    "escalation_risk": {"high_escalation", "low_escalation"},
}

DEFAULT_COUNTERFACTUALS: list[dict[str, str]] = [
    {"timely_response": "timely"},
    {"consumer_disputed": "not_disputed"},
    {"timely_response": "timely", "consumer_disputed": "not_disputed"},
]


def _progress(message: str) -> None:
    print(f"[progress] {message}", file=sys.stderr, flush=True)


def _utc_now() -> str:
    return datetime.now(tz=timezone.utc).isoformat(timespec="seconds")


def _read_csv_rows(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as fh:
        reader = csv.DictReader(fh)
        if reader.fieldnames is None:
            raise ValueError(f"Missing header row in CSV: {path}")
        return [dict(row) for row in reader]


def _write_csv(path: Path, fieldnames: list[str], rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow({key: row.get(key, "") for key in fieldnames})


def _validate_rows(rows: list[dict[str, str]]) -> tuple[list[dict[str, str]], int]:
    valid: list[dict[str, str]] = []
    rejected = 0
    for row in rows:
        missing = [column for column in REQUIRED_COLUMNS if not str(row.get(column, "")).strip()]
        if missing:
            rejected += 1
            continue

        bad_state = False
        for col, allowed in ALLOWED_STATES.items():
            if str(row.get(col, "")).strip() not in allowed:
                bad_state = True
                break
        if bad_state:
            rejected += 1
            continue
        valid.append(row)
    return valid, rejected


def _decision_distribution(batch_rows: list[dict[str, str]]) -> dict[str, int]:
    counts: dict[str, int] = {"APPROVE": 0, "REVIEW": 0, "DECLINE": 0, "error": 0}
    for row in batch_rows:
        if row.get("status") != "ok":
            counts["error"] += 1
            continue
        decision = row.get("decision", "")
        if decision in counts:
            counts[decision] += 1
        else:
            counts[decision] = 1
    return counts


def _write_report(
    *,
    report_path: Path,
    input_rows: int,
    accepted_rows: int,
    rejected_rows: int,
    decision_distribution: dict[str, int],
    replay_success_rate: float,
    audit_chain_valid: bool | None,
    fairness_summary: dict[str, Any],
    evidence_pack_mode: str,
    evidence_pack_rows: int | None,
) -> None:
    lines = [
        "# Public CFPB Complaint-Data Validation Report",
        "",
        f"Generated: {_utc_now()}",
        "",
        "## Non-production disclaimer",
        "",
        "This is public CFPB complaint-data validation, not production validation. "
        "It does not use customer data, does not make credit-eligibility decisions, and does not prove regulatory compliance.",
        "",
        "## Rows processed",
        "",
        f"- rows_processed: {input_rows}",
        f"- accepted_rows: {accepted_rows}",
        f"- rejected_rows: {rejected_rows}",
        "",
        "## Field mapping",
        "",
        "- product_risk <- Product",
        "- issue_complexity <- Issue, Sub-issue, Consumer complaint narrative",
        "- company_response_quality <- Company response to consumer",
        "- timely_response <- Timely response?",
        "- consumer_disputed <- Consumer disputed?",
        "- escalation_risk <- proxy derived from timeliness, dispute, response quality, and product risk",
        "- segment <- State",
        "",
        "## Decision distribution",
        "",
        json.dumps(decision_distribution, indent=2),
        "",
        "## Replay success rate",
        "",
        f"{replay_success_rate:.6f}",
        "",
        "## Audit-chain verification",
        "",
        ("skipped" if audit_chain_valid is None else str(audit_chain_valid).lower()),
        "",
        "## Fairness diagnostics",
        "",
        json.dumps(fairness_summary, indent=2),
        "",
        "## Evidence-pack mode",
        "",
        f"- mode: {evidence_pack_mode}",
    ]
    if evidence_pack_rows is not None:
        lines.append(f"- sampled_rows: {evidence_pack_rows}")
    lines.extend(
        [
            "",
            "## Limitations",
            "",
            "- Escalation risk is a proxy outcome, not a legal/regulatory determination.",
            "- Mapping rules are heuristic and require domain review before operational use.",
            "- This workflow is for governance and escalation-process testing only.",
        ]
    )
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text("\n".join(lines), encoding="utf-8")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run public CFPB complaint-data validation.")
    parser.add_argument("--input", required=True, help="Path to normalized CFPB complaints CSV.")
    parser.add_argument(
        "--model-config",
        default=str(ROOT / "configs" / "public_complaint_model.v1.json"),
        help="Base complaint model config path.",
    )
    parser.add_argument(
        "--policy-config",
        default=str(ROOT / "configs" / "public_complaint_policy.v1.json"),
        help="Complaint policy config path.",
    )
    parser.add_argument(
        "--output-dir",
        default=str(ROOT / "validation" / "outputs" / "cfpb_complaint_validation"),
        help="Output directory for validation artifacts.",
    )
    parser.add_argument("--max-audits", type=int, default=50, help="Max decision-level audit traces to generate.")
    parser.add_argument("--skip-evidence-pack", action="store_true", help="Skip evidence-pack export.")
    parser.add_argument(
        "--evidence-pack-max-rows",
        type=int,
        default=None,
        help="Optional cap on rows used for evidence-pack export.",
    )
    return parser


def main() -> int:
    args = build_parser().parse_args()
    if args.evidence_pack_max_rows is not None and args.evidence_pack_max_rows <= 0:
        raise ValueError("--evidence-pack-max-rows must be a positive integer")

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    _progress("loading inputs")
    input_rows = _read_csv_rows(Path(args.input))
    valid_rows, rejected_rows = _validate_rows(input_rows)
    if not valid_rows:
        raise ValueError("No valid normalized complaint rows available after validation.")

    _progress("combining normalized rows")
    combined_path = output_dir / "combined_normalized.csv"
    combined_fields = sorted({key for row in valid_rows for key in row.keys()})
    _write_csv(combined_path, combined_fields, valid_rows)

    _progress("estimating CPDs from complaint rows")
    cpd_rows = [
        {
            "product_risk": row["product_risk"],
            "issue_complexity": row["issue_complexity"],
            "company_response_quality": row["company_response_quality"],
            "timely_response": row["timely_response"],
            "consumer_disputed": row["consumer_disputed"],
            "escalation_risk": row["escalation_risk"],
        }
        for row in valid_rows
    ]
    draft_payload = build_draft_model_config(
        base_model_config_path=args.model_config,
        rows=cpd_rows,
        source_dataset_reference="cfpb_consumer_complaints",
        notes="Draft CPD estimate from public CFPB complaint-data validation inputs.",
    )
    draft_model_path = output_dir / "draft_model_config.public_cfpb.json"
    draft_model_path.write_text(json.dumps(draft_payload, indent=2), encoding="utf-8")

    _progress("running batch decisions")
    batch_rows = [
        {
            "tenant_id": row.get("tenant_id", "default"),
            "product_risk": row["product_risk"],
            "issue_complexity": row["issue_complexity"],
            "timely_response": row["timely_response"],
            "consumer_disputed": row["consumer_disputed"],
            "segment": row.get("segment", "unspecified"),
        }
        for row in valid_rows
    ]
    batch_input_path = output_dir / "batch_input.csv"
    _write_csv(
        batch_input_path,
        ["tenant_id", "product_risk", "issue_complexity", "timely_response", "consumer_disputed", "segment"],
        batch_rows,
    )

    batch_output_path = output_dir / "batch_output.csv"
    batch_summary = run_batch_csv(
        model_config_path=draft_model_path,
        policy_config_path=args.policy_config,
        csv_input_path=batch_input_path,
        csv_output_path=batch_output_path,
        subgroup_column="segment",
    )
    batch_output_rows = _read_csv_rows(batch_output_path)
    distribution = _decision_distribution(batch_output_rows)

    _progress("generating fairness report")
    fairness = compute_fairness_report(
        batch_output_rows,
        subgroup_column="segment",
        min_sample_size=30,
    )
    fairness_path = output_dir / "fairness_report.json"
    fairness_path.write_text(json.dumps(fairness, indent=2), encoding="utf-8")

    _progress("generating audit traces")
    audit_traces: list[dict[str, Any]] = []
    replay_success = 0
    replay_checked = 0
    for row in valid_rows[: max(args.max_audits, 0)]:
        evidence = {
            "product_risk": row["product_risk"],
            "issue_complexity": row["issue_complexity"],
            "timely_response": row["timely_response"],
            "consumer_disputed": row["consumer_disputed"],
        }
        audit = run_decision(
            model_config_path=draft_model_path,
            policy_config_path=args.policy_config,
            evidence=evidence,
            intervention_scenarios=DEFAULT_COUNTERFACTUALS,
            tenant_id=row.get("tenant_id", "default"),
        ).to_dict()
        audit["source_record_id"] = row.get("source_record_id", "")
        audit["source_dataset"] = row.get("source_dataset", "")
        audit_traces.append(audit)

        replay_checked += 1
        replay = replay_from_audit_payload(
            audit_payload=audit,
            model_config_path=draft_model_path,
            policy_config_path=args.policy_config,
        )
        if replay.get("risk_probability_match") and replay.get("decision_match"):
            replay_success += 1

    audit_traces_path = output_dir / "audit_traces.json"
    audit_traces_path.write_text(json.dumps(audit_traces, indent=2), encoding="utf-8")
    replay_success_rate = (replay_success / replay_checked) if replay_checked else 0.0

    evidence_pack_mode = "skipped" if args.skip_evidence_pack else "full"
    evidence_pack_rows: int | None = None
    evidence_pack_metadata: dict[str, Any] | None = None
    audit_chain_valid: bool | None = None
    if not args.skip_evidence_pack:
        _progress("exporting evidence pack")
        evidence_pack_dir = output_dir / "evidence_pack"
        evidence_input = batch_input_path
        if args.evidence_pack_max_rows is not None:
            evidence_pack_mode = "sampled"
            evidence_pack_rows = min(args.evidence_pack_max_rows, len(batch_rows))
            evidence_input = output_dir / "evidence_pack_input.sampled.csv"
            _write_csv(
                evidence_input,
                ["tenant_id", "product_risk", "issue_complexity", "timely_response", "consumer_disputed", "segment"],
                batch_rows[:evidence_pack_rows],
            )
        evidence_pack_metadata = export_evidence_pack(
            input_csv=evidence_input,
            output_dir=evidence_pack_dir,
            model_config_path=draft_model_path,
            policy_config_path=Path(args.policy_config),
        )
        chain_path = evidence_pack_dir / "audit_chain.json"
        chain_rows = json.loads(chain_path.read_text(encoding="utf-8"))
        audit_chain_valid = verify_audit_chain(chain_rows)

    _progress("writing report")
    report_path = output_dir / "public_cfpb_complaint_validation_report.generated.md"
    _write_report(
        report_path=report_path,
        input_rows=len(input_rows),
        accepted_rows=len(valid_rows),
        rejected_rows=rejected_rows,
        decision_distribution=distribution,
        replay_success_rate=replay_success_rate,
        audit_chain_valid=audit_chain_valid,
        fairness_summary={
            "subgroup_column": fairness.get("subgroup_column"),
            "rows_analyzed": fairness.get("rows_analyzed"),
            "max_min_subgroup_delta": fairness.get("max_min_subgroup_delta"),
            "warnings": fairness.get("warnings"),
        },
        evidence_pack_mode=evidence_pack_mode,
        evidence_pack_rows=evidence_pack_rows,
    )

    summary = {
        "status": "completed",
        "rows_processed": len(input_rows),
        "accepted_rows": len(valid_rows),
        "rejected_rows": rejected_rows,
        "model_config": str(draft_model_path),
        "policy_config": str(args.policy_config),
        "batch_summary": batch_summary,
        "decision_distribution": distribution,
        "replay_success_rate": replay_success_rate,
        "audit_chain_valid": audit_chain_valid,
        "fairness_report": str(fairness_path),
        "audit_traces": str(audit_traces_path),
        "evidence_pack_mode": evidence_pack_mode,
        "evidence_pack_rows": evidence_pack_rows,
        "evidence_pack": evidence_pack_metadata,
        "validation_report": str(report_path),
        "non_production_disclaimer": (
            "public CFPB complaint-data validation only; not production validation and not credit-eligibility scoring."
        ),
    }
    summary_path = output_dir / "validation_summary.json"
    summary_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
