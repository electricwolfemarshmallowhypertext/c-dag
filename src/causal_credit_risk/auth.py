"""Auth provider abstractions and local implementations."""

from __future__ import annotations

from causal_credit_risk.interfaces import AuthProvider
from causal_credit_risk.settings import RuntimeSettings


class AuthError(PermissionError):
    """Raised when request auth fails."""


class NoAuthProvider(AuthProvider):
    def authorize(self, presented_key: str | None) -> None:  # noqa: ARG002
        return


class ApiKeyAuthProvider(AuthProvider):
    def __init__(self, expected_api_key: str | None) -> None:
        if expected_api_key is None or expected_api_key.strip() == "":
            raise ValueError("API_KEY must be set when AUTH_MODE=api_key")
        self._expected_api_key = expected_api_key

    def authorize(self, presented_key: str | None) -> None:
        if presented_key is None or presented_key.strip() == "":
            raise AuthError("Missing API key")
        if presented_key != self._expected_api_key:
            raise AuthError("Invalid API key")


def build_auth_provider(settings: RuntimeSettings) -> AuthProvider:
    if settings.auth_mode == "api_key":
        return ApiKeyAuthProvider(settings.api_key)
    return NoAuthProvider()
