from __future__ import annotations

from pathlib import Path

from causal_credit_risk.audit_chain import (
    build_audit_chain_record,
    compute_audit_hash,
    verify_audit_chain,
    verify_audit_hash,
)
from causal_credit_risk.cli import run_decision


PROJECT_ROOT = Path(__file__).resolve().parents[1]
MODEL_CONFIG_PATH = PROJECT_ROOT / "configs" / "credit_risk_model.v1.json"
POLICY_CONFIG_PATH = PROJECT_ROOT / "configs" / "decision_policy.v1.json"


def _audit_payload() -> dict:
    return run_decision(
        model_config_path=MODEL_CONFIG_PATH,
        policy_config_path=POLICY_CONFIG_PATH,
    ).to_dict()


def test_audit_hash_stability_and_mutation_detection() -> None:
    audit = _audit_payload()
    h1 = compute_audit_hash(audit, previous_hash=None, chain_index=0)
    h2 = compute_audit_hash(audit, previous_hash=None, chain_index=0)
    assert h1 == h2

    mutated = dict(audit)
    mutated["decision"] = "APPROVE"
    h3 = compute_audit_hash(mutated, previous_hash=None, chain_index=0)
    assert h3 != h1


def test_audit_chain_verification_and_tamper_failure() -> None:
    audit_1 = _audit_payload()
    r1 = build_audit_chain_record(audit_1, chain_index=0, previous_hash=None)
    audit_2 = _audit_payload()
    r2 = build_audit_chain_record(audit_2, chain_index=1, previous_hash=r1["audit_hash"])

    assert verify_audit_hash(r1) is True
    assert verify_audit_hash(r2) is True
    assert verify_audit_chain([r1, r2]) is True

    tampered = [dict(r1), dict(r2)]
    tampered[1]["audit_record"] = dict(tampered[1]["audit_record"])
    tampered[1]["audit_record"]["risk_probability"] = 0.1
    assert verify_audit_hash(tampered[1]) is False
    assert verify_audit_chain(tampered) is False
