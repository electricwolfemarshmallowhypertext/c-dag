# Tenant Isolation Plan

## Current support

- `TENANCY_MODE=single` uses `tenant_id=default`
- `TENANCY_MODE=tenant_id` requires tenant_id in API/batch flows
- Tenant identifiers are persisted in audit records and chain records

## Future adapter path

- Enforce tenant scoping in auth claims
- Partition audit storage by tenant at database/storage layer
- Add per-tenant encryption keys and access policies

## Boundary statement

Tenant tagging in local mode is a seam for later isolation controls, not full multi-tenant security.
