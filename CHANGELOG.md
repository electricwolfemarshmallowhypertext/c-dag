# Changelog

All notable changes to this project are documented in this file.

## [Unreleased]

### Added

- Enterprise seam interfaces (`interfaces.py` / `ports.py`) for auth, tenancy, registries, CPD estimation, and audit stores.
- Local implementations: API-key auth, tenant resolvers, file/sqlite audit stores, file registries.
- New scripts for OpenAPI export, CPD draft estimation, end-to-end workflow, and evidence-pack export.
- Audit-chain verification surfaces in CLI and API.
- Fairness report API route alignment (`/v1/fairness/report`) while preserving compatibility route.

### Changed

- CLI and API outputs now include tenant-aware audit-chain metadata.
- Batch mode can preserve `tenant_id` and enforce tenant requirements when configured.

## [0.2.0-draft]

### Added

- FastAPI service endpoints for decision, replay, batch, and fairness diagnostics.
- Deterministic replay checks against active model/policy versions.
- Tamper-evident hash-chain primitives for audit records.
- Batch processing with row-level error handling.
- Governance and pilot-readiness documentation set.

### Notes

- Core inference math, CPD values, model semantics, and default risk output (`0.849375`) remain unchanged.
- License posture remains BUSL-1.1 (source-available).
