"""Tenant resolution abstractions and local defaults."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from causal_credit_risk.interfaces import TenantResolver
from causal_credit_risk.settings import RuntimeSettings


class TenancyError(ValueError):
    """Raised when tenant resolution fails."""


class SingleTenantResolver(TenantResolver):
    def __init__(self, tenant_id: str = "default") -> None:
        self._tenant_id = tenant_id

    def resolve(self, payload: Mapping[str, Any] | None = None) -> str:  # noqa: ARG002
        return self._tenant_id


class TenantIdResolver(TenantResolver):
    def resolve(self, payload: Mapping[str, Any] | None = None) -> str:
        if payload is None:
            raise TenancyError("tenant_id is required when TENANCY_MODE=tenant_id")

        raw = payload.get("tenant_id")
        if raw is None:
            raise TenancyError("tenant_id is required when TENANCY_MODE=tenant_id")

        tenant_id = str(raw).strip()
        if not tenant_id:
            raise TenancyError("tenant_id must be a non-empty string")
        return tenant_id


def resolve_tenant_id(
    resolver: TenantResolver,
    payload: Mapping[str, Any] | None = None,
) -> str:
    return resolver.resolve(payload)


def build_tenant_resolver(settings: RuntimeSettings) -> TenantResolver:
    if settings.tenancy_mode == "tenant_id":
        return TenantIdResolver()
    return SingleTenantResolver()
