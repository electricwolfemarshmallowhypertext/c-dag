"""CLI entry point for auditable causal credit-risk explainability demos.

WARNING:
This CLI demonstrates explainability and policy tracing only.
It is not a production lending decision service.
"""

from __future__ import annotations

import argparse
from collections.abc import Mapping, Sequence
import csv
import json
from json import JSONDecodeError
from pathlib import Path
from typing import Any

from causal_credit_risk.audit import build_causal_chain, create_audit_record
from causal_credit_risk.audit_chain import build_audit_chain_record, verify_audit_chain
from causal_credit_risk.audit_store import build_audit_store
from causal_credit_risk.batch import run_batch_csv
from causal_credit_risk.compliance import export_compliance_package, import_compliance_package
from causal_credit_risk.counterfactuals import intervention_counterfactual
from causal_credit_risk.fairness import compute_fairness_report
from causal_credit_risk.governance import (
    build_governance_artifact,
    replay_governance_artifact_payload,
    replay_governance_artifact_file,
)
from causal_credit_risk.inference import ExactInferenceEngine
from causal_credit_risk.io_utils import read_json_file
from causal_credit_risk.model import CausalDAGModel, ModelValidationError
from causal_credit_risk.policy import DecisionPolicy, PolicyValidationError, validate_policy_against_model
from causal_credit_risk.registry import default_model_config_path, default_policy_config_path
from causal_credit_risk.replay import ReplayValidationError, replay_from_audit_file
from causal_credit_risk.schemas import AuditRecord, PolicyConfig, StateRef
from causal_credit_risk.settings import RuntimeSettings
from causal_credit_risk.tenancy import TenancyError, build_tenant_resolver
from causal_credit_risk.visualization import to_dot

DEFAULT_EVIDENCE: dict[str, StateRef] = {
    "tenure": "short",
    "utilization": "high",
}

DEFAULT_COUNTERFACTUALS: list[dict[str, StateRef]] = [
    {"tenure": "long"},
    {"utilization": "low"},
    {"tenure": "long", "utilization": "low"},
]


def _default_model_config_path() -> Path:
    return default_model_config_path()


def _default_policy_config_path() -> Path:
    return default_policy_config_path()


def run_decision(
    *,
    model_config_path: str | Path,
    policy_config_path: str | Path,
    evidence: Mapping[str, StateRef] | None = None,
    intervention_scenarios: Sequence[Mapping[str, StateRef]] | None = None,
    tenant_id: str = "default",
) -> AuditRecord:
    model = CausalDAGModel.from_json(model_config_path)
    policy_config = PolicyConfig.from_json(policy_config_path)
    policy = DecisionPolicy(policy_config)
    validate_policy_against_model(model, policy)
    engine = ExactInferenceEngine(model)

    baseline_evidence = dict(evidence or DEFAULT_EVIDENCE)
    if intervention_scenarios is None:
        if {"tenure", "utilization"}.issubset(set(model.nodes.keys())):
            scenarios = list(DEFAULT_COUNTERFACTUALS)
        else:
            scenarios = []
    else:
        scenarios = list(intervention_scenarios)

    risk_probability = engine.query_probability(
        policy_config.risk_outcome_node,
        policy_config.high_risk_state,
        evidence=baseline_evidence,
    )
    decision = policy.decide(risk_probability)

    inferred_nodes = engine.infer_node_posteriors(evidence=baseline_evidence)
    causal_chain = build_causal_chain(
        model,
        engine,
        input_evidence=baseline_evidence,
        outcome_node_id=policy_config.risk_outcome_node,
    )
    counterfactuals = [
        intervention_counterfactual(
            engine,
            outcome_node_id=policy_config.risk_outcome_node,
            outcome_state=policy_config.high_risk_state,
            baseline_evidence=baseline_evidence,
            intervention_evidence=scenario,
        )
        for scenario in scenarios
    ]

    return create_audit_record(
        model=model,
        policy_config=policy_config,
        input_evidence=baseline_evidence,
        inferred_nodes=inferred_nodes,
        risk_probability=risk_probability,
        decision=decision,
        causal_chain=causal_chain,
        counterfactuals=counterfactuals,
        tenant_id=tenant_id,
    )


def format_explanation(audit: AuditRecord) -> str:
    lines = [
        "Causal Explainability Decision",
        f"  decision_id:    {audit.decision_id}",
        f"  tenant_id:      {audit.tenant_id}",
        f"  model:          {audit.model_id} v{audit.model_version}",
        f"  policy_version: {audit.policy_version}",
        f"  timestamp_utc:  {audit.timestamp_utc}",
        "",
        "Inputs",
    ]
    for node_id, state in audit.input_evidence.items():
        lines.append(f"  {node_id}: {state}")

    lines.extend(
        [
            "",
            f"Risk probability (high_risk): {audit.risk_probability:.6f}",
            f"Decision: {audit.decision}",
            "",
            "Causal chain",
        ]
    )
    for step in audit.causal_chain:
        if step.get("source") == "observed":
            lines.append(
                f"  {step['node_id']} ({step['human_label']}): observed={step['state']}"
            )
            continue
        lines.append(
            "  "
            + f"{step['node_id']} ({step['human_label']}): "
            + f"most_likely={step['most_likely_state']}, "
            + f"p_adverse_state={float(step['p_adverse_state']):.6f}"
        )

    lines.append("")
    lines.append("Counterfactuals")
    for cf in audit.counterfactuals:
        intervention = ", ".join(f"{k}={v}" for k, v in cf["intervention_evidence"].items())
        lines.append(
            "  "
            + f"{intervention}: before={cf['before_probability']:.6f}, "
            + f"after={cf['after_probability']:.6f}, delta={cf['delta']:+.6f}"
        )

    return "\n".join(lines)


def _load_json_argument(raw: str, expected_type: type[Any]) -> Any:
    try:
        value = json.loads(raw)
    except JSONDecodeError as exc:
        raise ValueError(f"Invalid JSON: {exc.msg} at position {exc.pos}") from exc
    if not isinstance(value, expected_type):
        raise ValueError(f"Expected JSON {expected_type.__name__}, got {type(value).__name__}")
    return value


def _load_csv_rows(path: str | Path) -> list[dict[str, Any]]:
    csv_path = Path(path)
    with csv_path.open("r", encoding="utf-8-sig", newline="") as fh:
        reader = csv.DictReader(fh)
        if reader.fieldnames is None:
            raise ValueError("Fairness CSV input must include headers")
        return [dict(row) for row in reader]


def _load_fairness_rows(path: str | Path) -> list[dict[str, Any]]:
    source = Path(path)
    if source.suffix.lower() == ".json":
        payload = read_json_file(source)
        if isinstance(payload, list):
            return [dict(item) for item in payload if isinstance(item, dict)]
        if isinstance(payload, dict) and isinstance(payload.get("rows"), list):
            return [dict(item) for item in payload["rows"] if isinstance(item, dict)]
        raise ValueError("Fairness JSON input must be a list of objects or {\"rows\": [...]}")
    return _load_csv_rows(source)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run auditable causal credit-risk explainability.")
    parser.add_argument(
        "--model-config",
        default=str(_default_model_config_path()),
        help="Path to model JSON config.",
    )
    parser.add_argument(
        "--policy-config",
        default=str(_default_policy_config_path()),
        help="Path to decision policy JSON config.",
    )
    parser.add_argument(
        "--evidence-json",
        default=json.dumps(DEFAULT_EVIDENCE),
        help='Baseline evidence as JSON object, e.g. {"tenure":"short","utilization":"high"}',
    )
    parser.add_argument(
        "--counterfactuals-json",
        default=json.dumps(DEFAULT_COUNTERFACTUALS),
        help='Counterfactual interventions as JSON list, e.g. [{"tenure":"long"}]',
    )
    parser.add_argument(
        "--audit-output",
        default=None,
        help="Optional file path to save JSON audit record.",
    )
    parser.add_argument(
        "--json-only",
        action="store_true",
        help="Suppress human-readable explanation and print only JSON audit output.",
    )
    parser.add_argument(
        "--batch-csv-input",
        default=None,
        help="Optional path to input CSV for batch decisions.",
    )
    parser.add_argument(
        "--batch-csv-output",
        default=None,
        help="Optional path to output CSV for batch decisions.",
    )
    parser.add_argument(
        "--replay-audit",
        default=None,
        help="Optional path to an existing audit JSON file for deterministic replay.",
    )
    parser.add_argument(
        "--export-governance-artifact",
        default=None,
        help="Optional file path to save a governance evidence artifact for the decision.",
    )
    parser.add_argument(
        "--replay-governance-artifact",
        default=None,
        help="Optional path to a governance evidence artifact JSON file for replay verification.",
    )
    parser.add_argument(
        "--export-compliance-package",
        default=None,
        help="Optional directory path to export a compliance-support evidence package.",
    )
    parser.add_argument(
        "--import-compliance-package",
        default=None,
        help="Optional directory path to verify a restored compliance-support evidence package.",
    )
    parser.add_argument(
        "--verify-audit-chain",
        default=None,
        help="Optional path to a JSON list of audit-chain records to verify.",
    )
    parser.add_argument(
        "--export-dot",
        default=None,
        help="Optional path to write DAG Graphviz DOT output.",
    )
    parser.add_argument(
        "--chain-index",
        type=int,
        default=0,
        help="Chain index for audit hash-chain metadata.",
    )
    parser.add_argument(
        "--previous-hash",
        default=None,
        help="Optional previous hash for audit hash-chain metadata.",
    )
    parser.add_argument(
        "--batch-subgroup-column",
        default=None,
        help="Optional subgroup column to pass through in batch output.",
    )
    parser.add_argument(
        "--fairness-report-input",
        default=None,
        help="Optional CSV or JSON input path for fairness diagnostics.",
    )
    parser.add_argument(
        "--fairness-input-csv",
        default=None,
        help=argparse.SUPPRESS,
    )
    parser.add_argument(
        "--fairness-subgroup-column",
        default="segment",
        help="Subgroup column name used for fairness diagnostics.",
    )
    parser.add_argument(
        "--fairness-min-sample-size",
        type=int,
        default=5,
        help="Minimum subgroup sample size threshold for warnings.",
    )
    parser.add_argument(
        "--fairness-output",
        default=None,
        help="Optional file path to save fairness report JSON.",
    )
    parser.add_argument(
        "--tenant-id",
        default=None,
        help="Optional tenant identifier. Required when TENANCY_MODE=tenant_id.",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        settings = RuntimeSettings.from_env()
        tenant_resolver = build_tenant_resolver(settings)
        audit_store = build_audit_store(settings)

        if args.export_dot:
            model = CausalDAGModel.from_json(args.model_config)
            dot_path = Path(args.export_dot)
            dot_path.parent.mkdir(parents=True, exist_ok=True)
            dot_path.write_text(to_dot(model), encoding="utf-8")

        if args.verify_audit_chain:
            records_payload = read_json_file(args.verify_audit_chain)
            if not isinstance(records_payload, list):
                parser.error("--verify-audit-chain must point to a JSON list")
            valid = verify_audit_chain(records_payload)
            result = {
                "valid": bool(valid),
                "records_checked": len(records_payload),
            }
            print(json.dumps(result, indent=2))
            return 0 if valid else 1

        if args.import_compliance_package:
            restored = import_compliance_package(args.import_compliance_package)
            replay_report = replay_governance_artifact_payload(
                artifact=restored["governance_artifact"],
                model_config_path=args.model_config,
                policy_config_path=args.policy_config,
            )
            restored["restore_replay_verification"] = replay_report
            print(json.dumps(restored, indent=2))
            return 0 if restored.get("integrity_valid") and replay_report.get("replay_match") else 1

        if args.replay_governance_artifact:
            replay_report = replay_governance_artifact_file(
                artifact_path=args.replay_governance_artifact,
                model_config_path=args.model_config,
                policy_config_path=args.policy_config,
            )
            print(json.dumps(replay_report, indent=2))
            return 0 if replay_report.get("replay_match") is True else 1

        if args.replay_audit:
            replay_report = replay_from_audit_file(
                audit_path=args.replay_audit,
                model_config_path=args.model_config,
                policy_config_path=args.policy_config,
            )
            tenant_id = str(replay_report.get("tenant_id", "default"))
            replay_chain = build_audit_chain_record(
                replay_report,
                chain_index=args.chain_index,
                previous_hash=args.previous_hash,
                tenant_id=tenant_id,
            )
            replay_report["audit_chain"] = {
                "chain_index": replay_chain["chain_index"],
                "timestamp_utc": replay_chain["timestamp_utc"],
                "previous_hash": replay_chain["previous_hash"],
                "audit_hash": replay_chain["audit_hash"],
                "tenant_id": replay_chain["tenant_id"],
            }
            if audit_store is not None:
                audit_store.save_chain_record(replay_chain)
            print(json.dumps(replay_report, indent=2))
            return 0

        if args.batch_csv_input:
            if not args.batch_csv_output:
                parser.error("--batch-csv-output is required when --batch-csv-input is provided")
            summary = run_batch_csv(
                model_config_path=args.model_config,
                policy_config_path=args.policy_config,
                csv_input_path=args.batch_csv_input,
                csv_output_path=args.batch_csv_output,
                subgroup_column=args.batch_subgroup_column,
                chain_start_index=args.chain_index,
                previous_hash=args.previous_hash,
                tenancy_mode=settings.tenancy_mode,
                default_tenant_id="default",
            )
            print(json.dumps(summary, indent=2))
            return 0

        fairness_input = args.fairness_report_input or args.fairness_input_csv
        if fairness_input:
            rows = _load_fairness_rows(fairness_input)
            tenant_candidates = {
                str(row.get("tenant_id")).strip()
                for row in rows
                if isinstance(row, dict) and row.get("tenant_id") is not None and str(row.get("tenant_id")).strip()
            }
            tenant_payload: dict[str, str] = {}
            if args.tenant_id is not None:
                tenant_payload["tenant_id"] = str(args.tenant_id).strip()
            elif len(tenant_candidates) == 1:
                tenant_payload["tenant_id"] = next(iter(tenant_candidates))
            tenant_id = tenant_resolver.resolve(tenant_payload if tenant_payload else None)
            report = compute_fairness_report(
                rows,
                subgroup_column=args.fairness_subgroup_column,
                min_sample_size=args.fairness_min_sample_size,
                tenant_id=tenant_id,
            )
            fairness_chain = build_audit_chain_record(
                report,
                chain_index=args.chain_index,
                previous_hash=args.previous_hash,
                tenant_id=tenant_id,
            )
            report["audit_chain"] = {
                "chain_index": fairness_chain["chain_index"],
                "timestamp_utc": fairness_chain["timestamp_utc"],
                "previous_hash": fairness_chain["previous_hash"],
                "audit_hash": fairness_chain["audit_hash"],
                "tenant_id": fairness_chain["tenant_id"],
            }
            if args.fairness_output:
                out = Path(args.fairness_output)
                out.write_text(json.dumps(report, indent=2), encoding="utf-8")
            if audit_store is not None:
                audit_store.save_chain_record(fairness_chain)
            print(json.dumps(report, indent=2))
            return 0

        evidence = _load_json_argument(args.evidence_json, dict)
        scenarios = _load_json_argument(args.counterfactuals_json, list)
        raw_tenant = args.tenant_id if args.tenant_id is not None else evidence.pop("tenant_id", None)
        tenant_payload = {"tenant_id": raw_tenant} if raw_tenant is not None else None
        tenant_id = tenant_resolver.resolve(tenant_payload)

        audit = run_decision(
            model_config_path=args.model_config,
            policy_config_path=args.policy_config,
            evidence=evidence,
            intervention_scenarios=scenarios,
            tenant_id=tenant_id,
        )

        if not args.json_only:
            print(format_explanation(audit))
            print("")
        payload = audit.to_dict()
        chain_record = build_audit_chain_record(
            payload,
            chain_index=args.chain_index,
            previous_hash=args.previous_hash,
            tenant_id=tenant_id,
        )
        payload["audit_chain"] = {
            "chain_index": chain_record["chain_index"],
            "timestamp_utc": chain_record["timestamp_utc"],
            "previous_hash": chain_record["previous_hash"],
            "audit_hash": chain_record["audit_hash"],
            "tenant_id": chain_record["tenant_id"],
        }
        governance_artifact = build_governance_artifact(
            audit.to_dict(),
            audit_chain_record=chain_record,
            tenant_id=tenant_id,
        )
        payload["governance_artifact"] = governance_artifact
        if args.export_compliance_package:
            payload["compliance_package"] = export_compliance_package(
                output_dir=args.export_compliance_package,
                governance_artifact=governance_artifact,
                model_config_path=args.model_config,
                policy_config_path=args.policy_config,
            )
        print(json.dumps(payload, indent=2))

        if args.audit_output:
            output_path = Path(args.audit_output)
            output_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        if args.export_governance_artifact:
            output_path = Path(args.export_governance_artifact)
            output_path.write_text(json.dumps(governance_artifact, indent=2), encoding="utf-8")
        if audit_store is not None:
            audit_store.save_audit(payload)
            audit_store.save_chain_record(chain_record)

        return 0
    except (
        ValueError,
        KeyError,
        ModelValidationError,
        PolicyValidationError,
        ReplayValidationError,
        TenancyError,
    ) as exc:
        parser.error(str(exc))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
