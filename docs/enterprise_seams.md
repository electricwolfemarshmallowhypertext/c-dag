# Enterprise Seams

This package adds replaceable seams for future enterprise adapters without changing inference math.

## Current seam interfaces

- `AuditStore`
- `AuthProvider`
- `TenantResolver`
- `CPDEstimator`
- `ModelRegistry`
- `PolicyRegistry`

## Local implementations

- File JSONL and SQLite audit stores
- No-auth and API-key auth providers
- Single-tenant and `tenant_id` resolvers
- File-backed model/policy registries
- CSV draft CPD estimator

## Adapter roadmap

These seams support adapter swaps later (SSO, Postgres, governed registry, artifact stores) without core logic surgery.
