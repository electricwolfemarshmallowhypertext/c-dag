"""Compatibility alias for interface protocols."""

from causal_credit_risk.interfaces import (
    AuditStore,
    AuthProvider,
    CPDEstimator,
    ModelRegistry,
    PolicyRegistry,
    TenantResolver,
)

__all__ = [
    "AuditStore",
    "AuthProvider",
    "CPDEstimator",
    "ModelRegistry",
    "PolicyRegistry",
    "TenantResolver",
]
