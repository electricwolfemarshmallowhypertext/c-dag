"""Estimate draft CPDs from categorical CSV data."""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from causal_credit_risk.cpd_estimation import build_draft_model_config
from causal_credit_risk.registry import default_model_config_path


def _read_rows(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as fh:
        reader = csv.DictReader(fh)
        if reader.fieldnames is None:
            raise ValueError("Input CSV must include headers")
        return [dict(row) for row in reader]


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Estimate draft CPDs from CSV.")
    parser.add_argument("--input-csv", required=True, help="Input CSV path")
    parser.add_argument(
        "--model-config",
        default=str(default_model_config_path()),
        help="Base model config path",
    )
    parser.add_argument(
        "--output",
        required=True,
        help="Output path for draft model config JSON",
    )
    parser.add_argument(
        "--source-dataset-reference",
        default="unspecified",
        help="Dataset reference identifier used in draft metadata",
    )
    parser.add_argument(
        "--notes",
        default=None,
        help="Optional estimation note",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Overwrite output if it exists",
    )
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    output_path = Path(args.output)
    if output_path.exists() and not args.force:
        parser.error(f"Output already exists: {output_path}. Use --force to overwrite.")

    rows = _read_rows(Path(args.input_csv))
    draft = build_draft_model_config(
        base_model_config_path=args.model_config,
        rows=rows,
        source_dataset_reference=args.source_dataset_reference,
        notes=args.notes,
    )

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(draft, indent=2), encoding="utf-8")
    print(str(output_path))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
