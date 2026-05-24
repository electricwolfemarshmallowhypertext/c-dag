from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys
import tempfile


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def _run(args: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, *args],
        cwd=PROJECT_ROOT,
        check=False,
        capture_output=True,
        text=True,
    )


def test_run_loss_exposure_mapping_generates_pack() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        tmp_dir = Path(tmp)
        cases_json = tmp_dir / "loss_cases.json"
        output_md = tmp_dir / "loss_pack.md"
        output_json = tmp_dir / "loss_pack.json"
        cases_json.write_text(
            json.dumps(
                {
                    "non_production_statement": (
                        "C-DAG does not prove prevention or savings. It demonstrates how high-risk financial "
                        "decisions can be made replayable, inspectable, and auditable before issues escalate."
                    ),
                    "cases": [
                        {
                            "case_id": "c1",
                            "case_title": "Sample enforcement case",
                            "source_name": "Public source",
                            "source_url": "https://example.com/case",
                            "source_fact_summary": "Public case summary.",
                            "failure_type": "Control failure.",
                            "affected_workflow": "Review workflow.",
                            "likely_missing_evidence_artifact": "Replayable audit artifact.",
                            "cdag_artifacts_for_review": ["replay_check", "audit_hash_chain"],
                            "buyer_relevance": "Supports governance challenge workflows.",
                            "limitation_language": "Mapping reference only."
                        }
                    ]
                }
            ),
            encoding="utf-8",
        )

        result = _run(
            [
                "scripts/run_loss_exposure_mapping.py",
                "--cases-json",
                str(cases_json),
                "--output-markdown",
                str(output_md),
                "--output-json",
                str(output_json),
            ]
        )
        assert result.returncode == 0, result.stderr
        assert output_md.exists()
        assert output_json.exists()

        markdown = output_md.read_text(encoding="utf-8")
        assert "C-DAG Loss Exposure Pack" in markdown
        assert "Sample enforcement case" in markdown
        assert "Replay check" in markdown
        assert "Audit hash-chain" in markdown
        assert "C-DAG does not prove prevention or savings." in markdown

        payload = json.loads(output_json.read_text(encoding="utf-8"))
        assert payload["case_count"] == 1
        assert payload["cases"][0]["case_id"] == "c1"


def test_loss_exposure_cases_json_contains_required_cases() -> None:
    payload = json.loads((PROJECT_ROOT / "validation" / "loss_exposure_cases.json").read_text(encoding="utf-8"))
    case_ids = {case["case_id"] for case in payload["cases"]}
    assert {
        "cfpb_wells_fargo_3_7b_order",
        "finra_2025_sanctions_categories",
        "sec_ai_washing_enforcement_focus",
        "ai_operational_losses_bhc_research",
        "occ_spring_2025_risk_framing",
    }.issubset(case_ids)
