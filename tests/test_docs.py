from __future__ import annotations

from pathlib import Path
import re


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def test_readme_contains_required_warning_and_replay_reference() -> None:
    readme = (PROJECT_ROOT / "README.md").read_text(encoding="utf-8")
    assert "Source-available software under BUSL-1.1" in readme
    assert "not OSI open-source" in readme
    assert "not for real lending decisions" in readme
    assert "not for credit eligibility decisions" in readme
    assert "docs/replay_proof.md" in readme


def test_docs_do_not_contain_local_machine_paths() -> None:
    targets = [PROJECT_ROOT / "README.md", PROJECT_ROOT / "MODEL_CARD.md"]
    targets.extend((PROJECT_ROOT / "docs").glob("*.md"))
    local_path_pattern = re.compile(r"[A-Za-z]:\\\\")

    for path in targets:
        body = path.read_text(encoding="utf-8")
        assert local_path_pattern.search(body) is None, f"Local path found in {path.name}"
