"""Normalize CFPB complaints data for public complaint-governance validation.

WARNING:
This script supports public CFPB complaint-data validation only.
It is not a production escalation system.
"""

from __future__ import annotations

import argparse
import csv
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))


EXPECTED_HEADERS = {
    "Date received",
    "Product",
    "Issue",
    "Sub-issue",
    "Consumer complaint narrative",
    "Company response to consumer",
    "Timely response?",
    "Consumer disputed?",
    "State",
    "Complaint ID",
}

HIGH_RISK_PRODUCTS = (
    "debt collection",
    "mortgage",
    "credit reporting",
    "credit card",
    "student loan",
    "vehicle loan",
    "payday loan",
    "title loan",
    "personal loan",
)

COMPLEX_ISSUE_KEYWORDS = (
    "investigation",
    "foreclosure",
    "legal",
    "fraud",
    "identity",
    "not owed",
    "loan modification",
    "threatened",
)

POOR_RESPONSE_STATUSES = {
    "Closed without relief",
    "Closed",
    "Untimely response",
    "In progress",
}


def _resolve_input_path(path_value: str) -> Path:
    input_path = Path(path_value)
    if input_path.exists():
        return input_path
    if input_path.suffix.lower() == ".cv":
        candidate = input_path.with_suffix(".csv")
        if candidate.exists():
            return candidate
    raise FileNotFoundError(f"Input file not found: {path_value}")


def _normalize_product_risk(product: str) -> str:
    token = product.strip().lower()
    if any(keyword in token for keyword in HIGH_RISK_PRODUCTS):
        return "high_product_risk"
    return "lower_product_risk"


def _normalize_issue_complexity(issue: str, sub_issue: str, narrative: str) -> str:
    issue_lower = issue.strip().lower()
    sub_issue_lower = sub_issue.strip().lower()
    narrative_present = bool(narrative.strip())
    keyword_hit = any(keyword in issue_lower or keyword in sub_issue_lower for keyword in COMPLEX_ISSUE_KEYWORDS)
    if narrative_present or keyword_hit:
        return "complex"
    return "standard"


def _normalize_response_quality(response: str) -> str:
    token = response.strip()
    if token in POOR_RESPONSE_STATUSES or token == "":
        return "poor"
    return "adequate"


def _normalize_timely_response(value: str) -> str:
    return "timely" if value.strip().lower() == "yes" else "untimely"


def _normalize_dispute(value: str) -> str:
    return "disputed" if value.strip().lower() == "yes" else "not_disputed"


def _derive_escalation_risk(
    *,
    product_risk: str,
    issue_complexity: str,
    company_response_quality: str,
    timely_response: str,
    consumer_disputed: str,
) -> str:
    if timely_response == "untimely":
        return "high_escalation"
    if consumer_disputed == "disputed":
        return "high_escalation"
    if company_response_quality == "poor" and issue_complexity == "complex":
        return "high_escalation"
    if company_response_quality == "poor" and product_risk == "high_product_risk":
        return "high_escalation"
    return "low_escalation"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Prepare CFPB complaints for public governance validation.")
    parser.add_argument("--input", required=True, help="Path to CFPB complaints CSV (or .cv typo variant).")
    parser.add_argument(
        "--max-rows",
        type=int,
        default=None,
        help="Optional maximum number of rows to normalize.",
    )
    parser.add_argument(
        "--output",
        default=str(ROOT / "validation" / "outputs" / "cfpb_complaints_normalized.1k.csv"),
        help="Normalized output CSV path.",
    )
    parser.add_argument("--encoding", default="utf-8-sig", help="Input encoding.")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    if args.max_rows is not None and args.max_rows <= 0:
        raise ValueError("--max-rows must be a positive integer")

    input_path = _resolve_input_path(args.input)
    rows_out: list[dict[str, str]] = []
    with input_path.open("r", encoding=args.encoding, newline="") as fh:
        reader = csv.DictReader(fh)
        if reader.fieldnames is None:
            raise ValueError("CFPB input must include a header row")

        missing_headers = sorted(EXPECTED_HEADERS.difference(set(reader.fieldnames)))
        if missing_headers:
            raise ValueError(f"CFPB input missing required headers: {', '.join(missing_headers)}")

        for idx, row in enumerate(reader, start=1):
            product = str(row.get("Product", "")).strip()
            issue = str(row.get("Issue", "")).strip()
            sub_issue = str(row.get("Sub-issue", "")).strip()
            narrative = str(row.get("Consumer complaint narrative", "")).strip()
            response = str(row.get("Company response to consumer", "")).strip()
            timely_raw = str(row.get("Timely response?", "")).strip()
            disputed_raw = str(row.get("Consumer disputed?", "")).strip()
            state = str(row.get("State", "")).strip()
            complaint_id = str(row.get("Complaint ID", "")).strip() or f"cfpb_{idx}"

            product_risk = _normalize_product_risk(product)
            issue_complexity = _normalize_issue_complexity(issue, sub_issue, narrative)
            company_response_quality = _normalize_response_quality(response)
            timely_response = _normalize_timely_response(timely_raw)
            consumer_disputed = _normalize_dispute(disputed_raw)
            escalation_risk = _derive_escalation_risk(
                product_risk=product_risk,
                issue_complexity=issue_complexity,
                company_response_quality=company_response_quality,
                timely_response=timely_response,
                consumer_disputed=consumer_disputed,
            )

            rows_out.append(
                {
                    "source_dataset": "cfpb_consumer_complaints",
                    "source_record_id": complaint_id,
                    "tenant_id": "default",
                    "product_risk": product_risk,
                    "issue_complexity": issue_complexity,
                    "company_response_quality": company_response_quality,
                    "timely_response": timely_response,
                    "consumer_disputed": consumer_disputed,
                    "escalation_risk": escalation_risk,
                    "segment": state or "unspecified",
                    "state": state,
                    "product": product,
                    "issue": issue,
                    "company_response_to_consumer": response,
                    "timely_response_raw": timely_raw,
                    "consumer_disputed_raw": disputed_raw,
                    "mapping_notes": (
                        "product_risk_from_product;"
                        "issue_complexity_from_issue_subissue_narrative;"
                        "response_quality_from_company_response;"
                        "escalation_risk_proxy_from_timeliness_dispute_response_product"
                    ),
                }
            )

            if args.max_rows is not None and len(rows_out) >= args.max_rows:
                break

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "source_dataset",
        "source_record_id",
        "tenant_id",
        "product_risk",
        "issue_complexity",
        "company_response_quality",
        "timely_response",
        "consumer_disputed",
        "escalation_risk",
        "segment",
        "state",
        "product",
        "issue",
        "company_response_to_consumer",
        "timely_response_raw",
        "consumer_disputed_raw",
        "mapping_notes",
    ]
    with output_path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows_out)

    print(f"prepared_rows={len(rows_out)} output={output_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
