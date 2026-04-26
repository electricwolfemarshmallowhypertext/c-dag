# Audit Integrity

This project supports tamper-evident audit integrity using canonical JSON hashing and optional hash chaining.

## Scope

- Hashing method: SHA-256
- Input: canonical JSON serialization of audit payload and chain context
- Chain support: optional `previous_hash`
- Verification:
  - `verify_audit_hash(record)`
  - `verify_audit_chain(records)`

This mechanism provides integrity checks. It is not a substitute for enterprise key management, HSM-backed signing, or legal non-repudiation controls.

## Canonical serialization

Canonical JSON is generated with:

- sorted keys
- compact separators
- UTF-8 encoding

Stable canonicalization is required for deterministic hash verification.

## Chain record format

Each chain record contains:

- `chain_index`
- `timestamp_utc`
- `previous_hash`
- `audit_hash`
- `audit_record`

The `audit_hash` is derived from:

- `audit_record`
- `previous_hash`
- `chain_index`

## Verification behavior

`verify_audit_hash(record)` checks:

- required fields exist
- computed hash matches `audit_hash`

`verify_audit_chain(records)` checks:

- each record hash is valid
- chain indices are sequential
- `previous_hash` links to prior `audit_hash`

## Deployment guidance

For enterprise deployment, pair hash-chaining with:

- immutable or append-only storage
- strong retention and backup policies
- access controls for audit data
- independent verification pipelines
