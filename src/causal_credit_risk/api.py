"""FastAPI surface for local service-style integration."""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path
from typing import Any

from fastapi import FastAPI, Header, HTTPException

from causal_credit_risk.audit_chain import build_audit_chain_record, verify_audit_chain
from causal_credit_risk.audit_store import build_audit_store
from causal_credit_risk.auth import AuthError, build_auth_provider
from causal_credit_risk.cli import run_decision
from causal_credit_risk.compliance import build_compliance_package_payload
from causal_credit_risk.controls import list_control_frameworks, load_control_registry, map_controls
from causal_credit_risk.fairness import compute_fairness_report
from causal_credit_risk.governance import apply_review_event, build_governance_artifact
from causal_credit_risk.model import CausalDAGModel, ModelValidationError
from causal_credit_risk.policy import (
    DecisionPolicy,
    PolicyValidationError,
    validate_policy_against_model,
)
from causal_credit_risk.registry import default_model_config_path, default_policy_config_path
from causal_credit_risk.replay import ReplayValidationError, replay_from_audit_payload
from causal_credit_risk.schemas import PolicyConfig
from causal_credit_risk.settings import RuntimeSettings
from causal_credit_risk.tenancy import TenancyError, build_tenant_resolver


def _default_model_config() -> Path:
    return default_model_config_path()


def _default_policy_config() -> Path:
    return default_policy_config_path()


def _validate_runtime(model_config_path: str | Path, policy_config_path: str | Path) -> dict[str, str]:
    model = CausalDAGModel.from_json(model_config_path)
    policy_config = PolicyConfig.from_json(policy_config_path)
    policy = DecisionPolicy(policy_config)
    validate_policy_against_model(model, policy)
    return {
        "model_id": model.config.model_id,
        "model_version": model.config.model_version,
        "policy_version": policy_config.policy_version,
    }


def _observed_nodes(model_config_path: str | Path) -> list[str]:
    model = CausalDAGModel.from_json(model_config_path)
    return sorted(
        node_id for node_id, node in model.nodes.items() if node.node_type == "observed"
    )


def create_app(
    *,
    model_config_path: str | Path | None = None,
    policy_config_path: str | Path | None = None,
    settings: RuntimeSettings | None = None,
) -> FastAPI:
    model_path = Path(model_config_path or _default_model_config())
    policy_path = Path(policy_config_path or _default_policy_config())
    runtime_settings = settings or RuntimeSettings.from_env()
    auth_provider = build_auth_provider(runtime_settings)
    tenant_resolver = build_tenant_resolver(runtime_settings)
    audit_store = build_audit_store(runtime_settings)

    app = FastAPI(title="causal-credit-risk-engine", version="0.2.0")

    def _authorize(x_api_key: str | None) -> None:
        try:
            auth_provider.authorize(x_api_key)
        except AuthError as exc:
            raise HTTPException(status_code=401, detail=str(exc)) from exc

    def _resolve_tenant(payload: Mapping[str, Any] | None = None) -> str:
        try:
            return tenant_resolver.resolve(payload)
        except TenancyError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.get("/healthz")
    def healthz() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/readyz")
    def readyz() -> dict[str, Any]:
        try:
            validated = _validate_runtime(model_path, policy_path)
            return {"status": "ready", **validated}
        except (ModelValidationError, PolicyValidationError, ValueError, KeyError) as exc:
            raise HTTPException(status_code=503, detail=str(exc)) from exc

    @app.post("/v1/decision")
    def decision(
        evidence: dict[str, Any],
        x_api_key: str | None = Header(default=None, alias="X-API-Key"),
    ) -> dict[str, Any]:
        _authorize(x_api_key)
        tenant_payload = {"tenant_id": evidence.get("tenant_id")} if "tenant_id" in evidence else None
        tenant_id = _resolve_tenant(tenant_payload)
        decision_evidence = {k: v for k, v in evidence.items() if k != "tenant_id"}

        try:
            audit = run_decision(
                model_config_path=model_path,
                policy_config_path=policy_path,
                evidence=decision_evidence,
                tenant_id=tenant_id,
            )
            payload = audit.to_dict()
            chain = build_audit_chain_record(
                payload,
                chain_index=0,
                previous_hash=None,
                tenant_id=tenant_id,
            )
            payload["audit_chain"] = {
                "chain_index": chain["chain_index"],
                "timestamp_utc": chain["timestamp_utc"],
                "previous_hash": chain["previous_hash"],
                "audit_hash": chain["audit_hash"],
                "tenant_id": chain["tenant_id"],
            }
            payload["governance_artifact"] = build_governance_artifact(
                audit.to_dict(),
                audit_chain_record=chain,
                tenant_id=tenant_id,
            )
            if audit_store is not None:
                audit_store.save_audit(payload)
                audit_store.save_chain_record(chain)
            return payload
        except (ValueError, KeyError, ModelValidationError, PolicyValidationError) as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.post("/v1/replay")
    def replay(
        audit_payload: dict[str, Any],
        x_api_key: str | None = Header(default=None, alias="X-API-Key"),
    ) -> dict[str, Any]:
        _authorize(x_api_key)
        tenant_payload = (
            {"tenant_id": audit_payload.get("tenant_id")} if "tenant_id" in audit_payload else None
        )
        tenant_id = _resolve_tenant(tenant_payload)
        try:
            report = replay_from_audit_payload(
                audit_payload=audit_payload,
                model_config_path=model_path,
                policy_config_path=policy_path,
            )
            report["tenant_id"] = report.get("tenant_id", tenant_id)
            chain = build_audit_chain_record(
                report,
                chain_index=0,
                previous_hash=None,
                tenant_id=str(report["tenant_id"]),
            )
            report["audit_chain"] = {
                "chain_index": chain["chain_index"],
                "timestamp_utc": chain["timestamp_utc"],
                "previous_hash": chain["previous_hash"],
                "audit_hash": chain["audit_hash"],
                "tenant_id": chain["tenant_id"],
            }
            if audit_store is not None:
                audit_store.save_chain_record(chain)
            return report
        except (ReplayValidationError, ValueError, KeyError, ModelValidationError, PolicyValidationError) as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.post("/v1/batch")
    def batch(
        rows: list[dict[str, Any]],
        x_api_key: str | None = Header(default=None, alias="X-API-Key"),
    ) -> dict[str, Any]:
        _authorize(x_api_key)
        required_observed_nodes = _observed_nodes(model_path)
        results: list[dict[str, Any]] = []
        failed = 0
        chain_index = 0
        previous_hash: str | None = None

        for idx, row in enumerate(rows, start=1):
            missing: list[str] = []
            evidence: dict[str, Any] = {}
            for node_id in required_observed_nodes:
                value = row.get(node_id)
                if value is None or str(value).strip() == "":
                    missing.append(node_id)
                else:
                    evidence[node_id] = value

            tenant_payload = {"tenant_id": row.get("tenant_id")} if "tenant_id" in row else None
            try:
                tenant_id = _resolve_tenant(tenant_payload)
            except HTTPException as exc:
                failed += 1
                results.append(
                    {
                        "row_id": idx,
                        "status": "error",
                        "error": str(exc.detail),
                    }
                )
                continue

            if missing:
                failed += 1
                results.append(
                    {
                        "row_id": idx,
                        "status": "error",
                        "tenant_id": tenant_id,
                        "error": f"Missing required evidence: {', '.join(sorted(missing))}",
                    }
                )
                continue

            try:
                audit = run_decision(
                    model_config_path=model_path,
                    policy_config_path=policy_path,
                    evidence=evidence,
                    tenant_id=tenant_id,
                )
                payload = audit.to_dict()
                chain = build_audit_chain_record(
                    payload,
                    chain_index=chain_index,
                    previous_hash=previous_hash,
                    tenant_id=tenant_id,
                )
                previous_hash = str(chain["audit_hash"])
                chain_index += 1
                results.append(
                    {
                        "row_id": idx,
                        "status": "ok",
                        "tenant_id": tenant_id,
                        "audit": payload,
                        "audit_chain": {
                            "chain_index": chain["chain_index"],
                            "timestamp_utc": chain["timestamp_utc"],
                            "previous_hash": chain["previous_hash"],
                            "audit_hash": chain["audit_hash"],
                            "tenant_id": chain["tenant_id"],
                        },
                    }
                )
                if audit_store is not None:
                    audit_store.save_audit(payload)
                    audit_store.save_chain_record(chain)
            except (ValueError, KeyError, ModelValidationError, PolicyValidationError) as exc:
                failed += 1
                results.append(
                    {
                        "row_id": idx,
                        "status": "error",
                        "tenant_id": tenant_id,
                        "error": str(exc),
                    }
                )

        return {
            "rows_processed": len(rows),
            "rows_failed": failed,
            "results": results,
        }

    def _fairness_handler(
        payload: dict[str, Any],
        x_api_key: str | None,
    ) -> dict[str, Any]:
        _authorize(x_api_key)
        try:
            rows = payload.get("rows")
            if not isinstance(rows, list):
                raise ValueError("rows must be a JSON array")
            subgroup_column = payload.get("subgroup_column", "segment")
            if not isinstance(subgroup_column, str) or not subgroup_column.strip():
                raise ValueError("subgroup_column must be a non-empty string")
            min_sample_size = payload.get("min_sample_size", 5)
            if not isinstance(min_sample_size, int) or min_sample_size < 1:
                raise ValueError("min_sample_size must be a positive integer")

            tenant_payload = {"tenant_id": payload.get("tenant_id")} if "tenant_id" in payload else None
            if tenant_payload is None and runtime_settings.tenancy_mode == "tenant_id":
                tenant_values = {
                    str(row.get("tenant_id")).strip()
                    for row in rows
                    if isinstance(row, dict)
                    and row.get("tenant_id") is not None
                    and str(row.get("tenant_id")).strip()
                }
                if len(tenant_values) == 1:
                    tenant_payload = {"tenant_id": next(iter(tenant_values))}
            tenant_id = _resolve_tenant(tenant_payload)

            report = compute_fairness_report(
                rows,
                subgroup_column=subgroup_column,
                min_sample_size=min_sample_size,
                tenant_id=tenant_id,
            )
            chain = build_audit_chain_record(
                report,
                chain_index=0,
                previous_hash=None,
                tenant_id=tenant_id,
            )
            report["audit_chain"] = {
                "chain_index": chain["chain_index"],
                "timestamp_utc": chain["timestamp_utc"],
                "previous_hash": chain["previous_hash"],
                "audit_hash": chain["audit_hash"],
                "tenant_id": chain["tenant_id"],
            }
            if audit_store is not None:
                audit_store.save_chain_record(chain)
            return report
        except (ValueError, KeyError) as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.post("/v1/fairness")
    def fairness(
        payload: dict[str, Any],
        x_api_key: str | None = Header(default=None, alias="X-API-Key"),
    ) -> dict[str, Any]:
        return _fairness_handler(payload, x_api_key)

    @app.post("/v1/fairness/report")
    def fairness_report(
        payload: dict[str, Any],
        x_api_key: str | None = Header(default=None, alias="X-API-Key"),
    ) -> dict[str, Any]:
        return _fairness_handler(payload, x_api_key)

    @app.get("/v1/control-frameworks")
    def control_frameworks(
        x_api_key: str | None = Header(default=None, alias="X-API-Key"),
    ) -> dict[str, Any]:
        _authorize(x_api_key)
        registry = load_control_registry()
        return {
            "registry_id": registry.get("registry_id"),
            "registry_version": registry.get("registry_version"),
            "frameworks": list_control_frameworks(registry),
        }

    @app.get("/v1/control-mappings")
    def control_mappings(
        x_api_key: str | None = Header(default=None, alias="X-API-Key"),
    ) -> dict[str, Any]:
        _authorize(x_api_key)
        return load_control_registry()

    @app.post("/v1/compliance-package")
    def compliance_package(
        evidence: dict[str, Any],
        x_api_key: str | None = Header(default=None, alias="X-API-Key"),
    ) -> dict[str, Any]:
        _authorize(x_api_key)
        tenant_payload = {"tenant_id": evidence.get("tenant_id")} if "tenant_id" in evidence else None
        tenant_id = _resolve_tenant(tenant_payload)
        decision_evidence = {k: v for k, v in evidence.items() if k != "tenant_id"}
        try:
            audit = run_decision(
                model_config_path=model_path,
                policy_config_path=policy_path,
                evidence=decision_evidence,
                tenant_id=tenant_id,
            )
            audit_payload = audit.to_dict()
            chain = build_audit_chain_record(
                audit_payload,
                chain_index=0,
                previous_hash=None,
                tenant_id=tenant_id,
            )
            artifact = build_governance_artifact(
                audit_payload,
                audit_chain_record=chain,
                tenant_id=tenant_id,
            )
            return build_compliance_package_payload(
                governance_artifact=artifact,
                model_config_path=model_path,
                policy_config_path=policy_path,
            )
        except (ValueError, KeyError, ModelValidationError, PolicyValidationError) as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.post("/v1/review")
    def review(
        payload: dict[str, Any],
        x_api_key: str | None = Header(default=None, alias="X-API-Key"),
    ) -> dict[str, Any]:
        _authorize(x_api_key)
        artifact = payload.get("governance_artifact")
        if not isinstance(artifact, dict):
            raise HTTPException(status_code=400, detail="governance_artifact must be an object")
        reviewer_id = payload.get("reviewer_id")
        review_status = payload.get("review_status")
        if not isinstance(reviewer_id, str) or not reviewer_id.strip():
            raise HTTPException(status_code=400, detail="reviewer_id must be a non-empty string")
        if not isinstance(review_status, str):
            raise HTTPException(status_code=400, detail="review_status must be a string")
        try:
            updated = apply_review_event(
                artifact,
                reviewer_id=reviewer_id,
                review_status=review_status,
                review_notes=payload.get("review_notes"),
                reviewed_at=payload.get("reviewed_at"),
            )
            return {"governance_artifact": updated, "control_mappings": map_controls(updated)}
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.post("/v1/audit-chain/verify")
    def audit_chain_verify(
        records: list[dict[str, Any]],
        x_api_key: str | None = Header(default=None, alias="X-API-Key"),
    ) -> dict[str, Any]:
        _authorize(x_api_key)
        if not isinstance(records, list):
            raise HTTPException(status_code=400, detail="records must be a JSON list")
        return {
            "valid": verify_audit_chain(records),
            "records_checked": len(records),
        }

    return app


app = create_app()
