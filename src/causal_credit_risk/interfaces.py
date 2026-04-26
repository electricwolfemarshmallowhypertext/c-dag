"""Minimal enterprise seam interfaces.

These protocols define replaceable boundaries without changing core inference math.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any, Protocol


class AuditStore(Protocol):
    def save_audit(self, audit_record: Mapping[str, Any]) -> None: ...

    def get_audit(
        self, decision_id: str, *, tenant_id: str = "default"
    ) -> dict[str, Any] | None: ...

    def list_audits(self, *, tenant_id: str = "default") -> list[dict[str, Any]]: ...

    def save_chain_record(self, chain_record: Mapping[str, Any]) -> None: ...

    def list_chain_records(self, *, tenant_id: str = "default") -> list[dict[str, Any]]: ...


class AuthProvider(Protocol):
    def authorize(self, presented_key: str | None) -> None: ...


class TenantResolver(Protocol):
    def resolve(self, payload: Mapping[str, Any] | None = None) -> str: ...


class CPDEstimator(Protocol):
    def estimate(self, rows: Sequence[Mapping[str, str]]) -> dict[str, Any]: ...


class ModelRegistry(Protocol):
    def load_model(self, model_config_path: str | None = None) -> Any: ...

    def load_model_config(self, model_config_path: str | None = None) -> Any: ...


class PolicyRegistry(Protocol):
    def load_policy_config(self, policy_config_path: str | None = None) -> Any: ...
