"""Export FastAPI OpenAPI spec to examples/openapi.json."""

from __future__ import annotations

import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from causal_credit_risk.api import create_app


def project_root() -> Path:
    return ROOT


def main() -> int:
    root = project_root()
    out_path = root / "examples" / "openapi.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)

    app = create_app(
        model_config_path=root / "configs" / "credit_risk_model.v1.json",
        policy_config_path=root / "configs" / "decision_policy.v1.json",
    )
    out_path.write_text(json.dumps(app.openapi(), indent=2), encoding="utf-8")
    print(str(out_path))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
