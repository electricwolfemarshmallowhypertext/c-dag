# Audit Storage Adapter Plan

## Current local options

- File JSONL audit store
- SQLite audit store

## Future adapter path

- Replace with managed Postgres or equivalent transactional store
- Add retention and archival policies at storage layer
- Add encryption, access controls, and immutable storage controls

## Boundary statement

Local storage is for pilots and development. Production governance storage requires enterprise controls.
