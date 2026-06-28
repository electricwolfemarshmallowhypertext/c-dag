"""Deterministic control registry and mapping helpers."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping

from causal_credit_risk.io_utils import read_json_file
from causal_credit_risk.settings import project_root


def default_control_registry_path() -> Path:
    return project_root() / "configs" / "control_frameworks.v1.json"


def load_control_registry(path: str | Path | None = None) -> dict[str, Any]:
    registry_path = Path(path) if path is not None else default_control_registry_path()
    payload = read_json_file(registry_path)
    if not isinstance(payload, dict):
        raise ValueError("Control registry must be a JSON object")
    frameworks = payload.get("frameworks")
    if not isinstance(frameworks, list):
        raise ValueError("Control registry must include frameworks")
    return payload


def list_control_frameworks(registry: Mapping[str, Any] | None = None) -> list[dict[str, Any]]:
    payload = dict(registry or load_control_registry())
    frameworks = payload.get("frameworks", [])
    return [
        {
            "id": str(framework["id"]),
            "name": str(framework["name"]),
            "version": str(framework["version"]),
            "control_count": len(framework.get("controls", [])),
        }
        for framework in sorted(frameworks, key=lambda item: str(item.get("id", "")))
        if isinstance(framework, dict)
    ]


def _field_present(payload: Mapping[str, Any], field_path: str) -> bool:
    current: Any = payload
    for part in field_path.split("."):
        if not isinstance(current, Mapping) or part not in current:
            return False
        current = current[part]
    return current not in (None, "", [], {})


def map_controls(
    artifact: Mapping[str, Any],
    *,
    registry: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    payload = dict(registry or load_control_registry())
    controls: list[dict[str, Any]] = []

    for framework in sorted(payload.get("frameworks", []), key=lambda item: str(item.get("id", ""))):
        if not isinstance(framework, dict):
            continue
        for control in sorted(framework.get("controls", []), key=lambda item: str(item.get("id", ""))):
            if not isinstance(control, dict):
                continue
            evidence_fields = [
                str(field) for field in control.get("evidence_fields", []) if isinstance(field, str)
            ]
            present = [field for field in evidence_fields if _field_present(artifact, field)]
            missing = [field for field in evidence_fields if field not in present]
            if present and not missing:
                status = "supported"
            elif present:
                status = "partial"
            else:
                status = "not_supported"
            controls.append(
                {
                    "id": str(control["id"]),
                    "framework_id": str(framework["id"]),
                    "framework": str(framework["name"]),
                    "framework_version": str(framework["version"]),
                    "title": str(control.get("title", "")),
                    "status": status,
                    "evidence": present,
                    "missing_evidence": missing,
                }
            )

    return {
        "registry_id": str(payload.get("registry_id", "")),
        "registry_version": str(payload.get("registry_version", "")),
        "controls": controls,
    }


def control_references_from_mapping(mapping: Mapping[str, Any]) -> list[dict[str, str]]:
    references: list[dict[str, str]] = []
    for control in mapping.get("controls", []):
        if not isinstance(control, Mapping):
            continue
        references.append(
            {
                "id": str(control.get("id", "")),
                "framework_id": str(control.get("framework_id", "")),
                "status": str(control.get("status", "")),
            }
        )
    return references
