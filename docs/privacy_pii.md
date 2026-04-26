# Privacy and PII

## Current demo posture

- The reference model does not require direct personal identifiers.
- Example fields (`tenure`, `utilization`) are non-PII demo attributes.

## Operational guidance

- Do not ingest unnecessary personal data into this package.
- If production attributes include sensitive personal data, apply data minimization and role-based access controls.
- Keep sensitive datasets out of logs, examples, and artifacts.

## Audit records

- Audit records should not include secrets.
- If enterprise deployment needs richer attributes, apply masking/tokenization policies before storage or export.

## Compliance note

This document is operational guidance, not legal advice.
