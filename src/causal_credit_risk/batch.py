"""CSV batch decision helpers."""

from __future__ import annotations

import csv
from pathlib import Path
from typing import Any

from causal_credit_risk.audit_chain import build_audit_chain_record
from causal_credit_risk.model import CausalDAGModel


def _normalize_header(name: str) -> str:
    return name.replace("\ufeff", "").strip()


def run_batch_csv(
    *,
    model_config_path: str | Path,
    policy_config_path: str | Path,
    csv_input_path: str | Path,
    csv_output_path: str | Path,
    subgroup_column: str | None = None,
    chain_start_index: int = 0,
    previous_hash: str | None = None,
    tenancy_mode: str = "single",
    default_tenant_id: str = "default",
) -> dict[str, Any]:
    from causal_credit_risk.cli import run_decision

    model = CausalDAGModel.from_json(model_config_path)
    required_observed_nodes = sorted(
        node_id for node_id, node in model.nodes.items() if node.node_type == "observed"
    )
    required_set = set(required_observed_nodes)
    allowed_columns = set(required_set)
    allowed_columns.add("tenant_id")
    if subgroup_column is not None:
        allowed_columns.add(subgroup_column)

    input_path = Path(csv_input_path)
    output_path = Path(csv_output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with input_path.open("r", encoding="utf-8-sig", newline="") as in_fh:
        raw_reader = csv.reader(in_fh)
        raw_headers = next(raw_reader, None)
        if raw_headers is None:
            raise ValueError("Batch CSV input must include a header row")

        normalized_headers = [_normalize_header(header) for header in raw_headers]
        if any(not header for header in normalized_headers):
            raise ValueError("Batch CSV headers cannot be empty")
        if len(set(normalized_headers)) != len(normalized_headers):
            raise ValueError("Batch CSV headers contain duplicates after normalization")

        missing_required = sorted(required_set.difference(normalized_headers))
        if missing_required:
            raise ValueError(
                "Batch CSV missing required observed columns: "
                + ", ".join(missing_required)
            )

        if subgroup_column is not None and subgroup_column not in normalized_headers:
            raise ValueError(f"Batch CSV missing subgroup column: {subgroup_column}")
        if tenancy_mode == "tenant_id" and "tenant_id" not in normalized_headers:
            raise ValueError("Batch CSV missing required tenant_id column for TENANCY_MODE=tenant_id")

        unknown_headers = sorted(set(normalized_headers).difference(allowed_columns))
        if unknown_headers:
            raise ValueError(
                "Batch CSV has unknown columns in strict mode: "
                + ", ".join(unknown_headers)
            )

        rows_out: list[dict[str, str]] = []
        error_count = 0
        chain_index = chain_start_index
        chain_prev_hash = previous_hash
        for row_idx, raw_row in enumerate(raw_reader, start=1):
            row_map = dict(zip(normalized_headers, raw_row))
            for header in normalized_headers[len(raw_row) :]:
                row_map[header] = ""

            evidence: dict[str, str] = {}
            row_error: str | None = None
            for node_id in required_observed_nodes:
                value = row_map.get(node_id, "")
                cleaned = str(value).strip()
                if cleaned == "":
                    row_error = f"Missing required evidence: {node_id}"
                    break
                evidence[node_id] = cleaned

            tenant_value = str(row_map.get("tenant_id", default_tenant_id)).strip()
            if tenancy_mode == "tenant_id":
                if tenant_value == "":
                    row_error = "Missing required evidence: tenant_id"
            elif tenant_value == "":
                tenant_value = default_tenant_id

            if row_error is None:
                try:
                    audit = run_decision(
                        model_config_path=model_config_path,
                        policy_config_path=policy_config_path,
                        evidence=evidence,
                        tenant_id=tenant_value,
                    )
                    chain_record = build_audit_chain_record(
                        audit.to_dict(),
                        chain_index=chain_index,
                        previous_hash=chain_prev_hash,
                        tenant_id=tenant_value,
                    )
                    chain_prev_hash = chain_record["audit_hash"]
                    chain_index += 1
                    rows_out.append(
                        {
                            "row_id": str(row_idx),
                            "status": "ok",
                            "decision_id": audit.decision_id,
                            "risk_probability": f"{audit.risk_probability:.6f}",
                            "decision": audit.decision,
                            "chain_index": str(chain_record["chain_index"]),
                            "previous_hash": str(chain_record["previous_hash"] or ""),
                            "audit_hash": str(chain_record["audit_hash"]),
                            "tenant_id": tenant_value,
                            "error": "",
                            **(
                                {subgroup_column: str(row_map.get(subgroup_column, ""))}
                                if subgroup_column is not None
                                else {}
                            ),
                        }
                    )
                except Exception as exc:
                    row_error = str(exc)

            if row_error is not None:
                error_count += 1
                rows_out.append(
                    {
                        "row_id": str(row_idx),
                        "status": "error",
                        "decision_id": "",
                        "risk_probability": "",
                        "decision": "",
                        "chain_index": "",
                        "previous_hash": "",
                        "audit_hash": "",
                        "tenant_id": tenant_value,
                        "error": row_error,
                        **(
                            {subgroup_column: str(row_map.get(subgroup_column, ""))}
                            if subgroup_column is not None
                            else {}
                        ),
                    }
                )

    fieldnames = [
        "row_id",
        "status",
        "decision_id",
        "risk_probability",
        "decision",
        "chain_index",
        "previous_hash",
        "audit_hash",
        "tenant_id",
        "error",
    ]
    if subgroup_column is not None:
        fieldnames.append(subgroup_column)
    with output_path.open("w", encoding="utf-8", newline="") as out_fh:
        writer = csv.DictWriter(out_fh, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows_out)

    return {
        "input_path": str(input_path),
        "output_path": str(output_path),
        "rows_processed": len(rows_out),
        "rows_failed": error_count,
    }
