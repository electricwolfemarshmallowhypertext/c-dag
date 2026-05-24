"""Build a public loss-exposure validation pack for C-DAG.

WARNING:
This workflow maps public enforcement/research evidence to governance artifacts.
It does not prove prevention, savings, or regulatory compliance.
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import sys
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from causal_credit_risk.io_utils import read_json_file


REQUIRED_CASE_FIELDS: tuple[str, ...] = (
    "case_id",
    "case_title",
    "source_name",
    "source_url",
    "source_fact_summary",
    "failure_type",
    "affected_workflow",
    "likely_missing_evidence_artifact",
    "cdag_artifacts_for_review",
    "buyer_relevance",
    "limitation_language",
)

ARTIFACT_LABELS: dict[str, str] = {
    "causal_trace": "Causal trace",
    "counterfactual_review": "Counterfactual review",
    "replay_check": "Replay check",
    "audit_hash_chain": "Audit hash-chain",
    "evidence_pack": "Evidence pack",
    "fairness_segment_diagnostics": "Fairness/segment diagnostics",
}

DEFAULT_DISCLAIMER = (
    "C-DAG does not prove prevention or savings. "
    "It demonstrates how high-risk financial decisions can be made replayable, inspectable, "
    "and auditable before issues escalate."
)


def _utc_now() -> str:
    return datetime.now(tz=timezone.utc).isoformat(timespec="seconds")


def _as_cases(payload: Any) -> tuple[list[dict[str, Any]], str]:
    if isinstance(payload, dict):
        cases = payload.get("cases")
        if not isinstance(cases, list):
            raise ValueError("cases JSON must include a list field named 'cases'")
        disclaimer = str(payload.get("non_production_statement", DEFAULT_DISCLAIMER)).strip() or DEFAULT_DISCLAIMER
        return [dict(item) for item in cases], disclaimer
    if isinstance(payload, list):
        return [dict(item) for item in payload], DEFAULT_DISCLAIMER
    raise ValueError("cases JSON must be an object with 'cases' or a list of case objects")


def _validate_cases(cases: list[dict[str, Any]]) -> None:
    if not cases:
        raise ValueError("cases list is empty")
    for index, case in enumerate(cases, start=1):
        missing = [field for field in REQUIRED_CASE_FIELDS if field not in case]
        if missing:
            raise ValueError(f"case #{index} missing required fields: {', '.join(missing)}")
        artifacts = case.get("cdag_artifacts_for_review")
        if not isinstance(artifacts, list) or not artifacts:
            raise ValueError(f"case #{index} must include non-empty cdag_artifacts_for_review list")


def _artifact_label(artifact_id: str) -> str:
    return ARTIFACT_LABELS.get(artifact_id, artifact_id.replace("_", " ").strip().title())


def _render_pack(*, cases: list[dict[str, Any]], disclaimer: str) -> str:
    lines = [
        "# C-DAG Loss Exposure Pack",
        "",
        f"Generated: {_utc_now()}",
        "",
        "## Scope",
        "",
        "Public loss-exposure mapping using enforcement, supervisory, and operational-risk evidence.",
        "This is a governance review artifact, not a production-risk model validation artifact.",
        "",
        "## Core limitation",
        "",
        disclaimer,
        "",
    ]

    for case in cases:
        lines.extend(
            [
                f"## {case['case_title']}",
                "",
                f"- Source: [{case['source_name']}]({case['source_url']})",
                f"- Public fact: {case['source_fact_summary']}",
                f"- Failure type: {case['failure_type']}",
                f"- Affected workflow: {case['affected_workflow']}",
                f"- Likely missing evidence artifact: {case['likely_missing_evidence_artifact']}",
                "- C-DAG artifact mapping:",
            ]
        )
        for artifact_id in case["cdag_artifacts_for_review"]:
            lines.append(f"  - {_artifact_label(str(artifact_id))}")
        lines.extend(
            [
                f"- Buyer relevance: {case['buyer_relevance']}",
                f"- Limitation: {case['limitation_language']}",
                "",
            ]
        )

    lines.extend(
        [
            "## Required usage boundary",
            "",
            "C-DAG does not make lending decisions and is not a compliance certification system.",
            "Use this pack to support pre-escalation governance review, replayability checks, and audit evidence assembly.",
        ]
    )
    return "\n".join(lines).strip() + "\n"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Build public loss-exposure mapping artifacts for C-DAG.")
    parser.add_argument(
        "--cases-json",
        default=str(ROOT / "validation" / "loss_exposure_cases.json"),
        help="Input JSON containing public loss-exposure case mappings.",
    )
    parser.add_argument(
        "--output-markdown",
        default=str(ROOT / "validation" / "loss_exposure_pack.md"),
        help="Output markdown pack path.",
    )
    parser.add_argument(
        "--output-json",
        default=None,
        help="Optional output path for validated/normalized cases JSON copy.",
    )
    return parser


def main() -> int:
    args = build_parser().parse_args()

    payload = read_json_file(args.cases_json)
    cases, disclaimer = _as_cases(payload)
    _validate_cases(cases)

    markdown = _render_pack(cases=cases, disclaimer=disclaimer)
    output_markdown = Path(args.output_markdown)
    output_markdown.parent.mkdir(parents=True, exist_ok=True)
    output_markdown.write_text(markdown, encoding="utf-8")

    if args.output_json:
        normalized = {
            "generated_utc": _utc_now(),
            "case_count": len(cases),
            "non_production_statement": disclaimer,
            "cases": cases,
        }
        output_json = Path(args.output_json)
        output_json.parent.mkdir(parents=True, exist_ok=True)
        output_json.write_text(json.dumps(normalized, indent=2), encoding="utf-8")

    print(
        json.dumps(
            {
                "status": "completed",
                "cases": len(cases),
                "input_json": str(Path(args.cases_json)),
                "output_markdown": str(output_markdown),
                "output_json": args.output_json,
                "disclaimer": disclaimer,
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
