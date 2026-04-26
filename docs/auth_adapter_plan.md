# Auth Adapter Plan

## Current state

- `AUTH_MODE=none` (default) or `AUTH_MODE=api_key`
- API-key mode checks `X-API-Key` against `API_KEY`

## Future adapter path

- Add enterprise SSO/OIDC adapters (Okta/Auth0/internal IdP)
- Map identity claims to tenant scope and audit metadata
- Externalize auth policy and key rotation

## Boundary statement

This package does not attempt to be a full IAM product. Auth is deliberately a seam.
