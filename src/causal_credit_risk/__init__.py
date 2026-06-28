"""Causal credit-risk explainability engine.

WARNING:
This package is a demonstration framework for causal explainability.
It is not sufficient for real credit decisioning without governance,
fairness testing, legal review, and production monitoring.
"""

from causal_credit_risk.audit import build_causal_chain, create_audit_record
from causal_credit_risk.audit_chain import (
    build_audit_chain_record,
    canonical_json,
    compute_audit_hash,
    verify_audit_chain,
    verify_audit_hash,
)
from causal_credit_risk.audit_store import LocalJsonAuditStore, SQLiteAuditStore
from causal_credit_risk.auth import ApiKeyAuthProvider, NoAuthProvider
from causal_credit_risk.batch import run_batch_csv
from causal_credit_risk.compliance import (
    build_compliance_package_payload,
    export_compliance_package,
    import_compliance_package,
)
from causal_credit_risk.controls import (
    list_control_frameworks,
    load_control_registry,
    map_controls,
)
from causal_credit_risk.cpd_estimation import CsvCPDEstimator, build_draft_model_config
from causal_credit_risk.counterfactuals import intervention_counterfactual
from causal_credit_risk.fairness import compute_fairness_report
from causal_credit_risk.governance import (
    apply_review_event,
    build_governance_artifact,
    replay_governance_artifact_file,
    replay_governance_artifact_payload,
)
from causal_credit_risk.inference import ExactInferenceEngine
from causal_credit_risk.model import CausalDAGModel, ModelValidationError
from causal_credit_risk.policy import DecisionPolicy, PolicyValidationError
from causal_credit_risk.registry import FileModelRegistry, FilePolicyRegistry
from causal_credit_risk.replay import replay_from_audit_file
from causal_credit_risk.settings import RuntimeSettings
from causal_credit_risk.schemas import (
    AuditRecord,
    CounterfactualResult,
    ModelConfig,
    PolicyConfig,
)
from causal_credit_risk.tenancy import SingleTenantResolver, TenantIdResolver
from causal_credit_risk.visualization import to_dot

__all__ = [
    "AuditRecord",
    "ApiKeyAuthProvider",
    "CausalDAGModel",
    "CounterfactualResult",
    "CsvCPDEstimator",
    "DecisionPolicy",
    "ExactInferenceEngine",
    "FileModelRegistry",
    "FilePolicyRegistry",
    "LocalJsonAuditStore",
    "ModelConfig",
    "ModelValidationError",
    "NoAuthProvider",
    "PolicyConfig",
    "PolicyValidationError",
    "RuntimeSettings",
    "SQLiteAuditStore",
    "SingleTenantResolver",
    "TenantIdResolver",
    "build_audit_chain_record",
    "build_causal_chain",
    "build_compliance_package_payload",
    "build_governance_artifact",
    "canonical_json",
    "compute_audit_hash",
    "compute_fairness_report",
    "create_audit_record",
    "export_compliance_package",
    "build_draft_model_config",
    "import_compliance_package",
    "intervention_counterfactual",
    "list_control_frameworks",
    "load_control_registry",
    "map_controls",
    "apply_review_event",
    "replay_from_audit_file",
    "replay_governance_artifact_file",
    "replay_governance_artifact_payload",
    "run_batch_csv",
    "to_dot",
    "verify_audit_chain",
    "verify_audit_hash",
]
