# Procurement FAQ

## Is this open-source?

No. This project is source-available under BUSL-1.1.

## What does BUSL-1.1 mean here?

Commercial production use requires written permission from the licensor until the Change Date in the license terms.

## How is data handled?

The local package processes provided inputs and outputs local artifacts. It does not require network calls for core workflows.

## Does this require PII?

No. Demo workflows do not require PII and should not use production borrower data.

## Where does auth belong?

At deployment boundaries (API gateway/service layer). Local API-key mode is an adapter seam, not enterprise IAM.

## What support is available?

Public support is best-effort. Commercial support is available by written agreement.

## Is this legal/compliance advice?

No. This package and documentation are technical references only.

## Integration requirements

- Python 3.10+
- Controlled config/version management
- Governance storage for audit artifacts
- Internal security controls for deployment surfaces
