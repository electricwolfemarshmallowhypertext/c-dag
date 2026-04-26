# OpenAPI Export

The FastAPI service exposes an OpenAPI schema.

## Regenerate

From repository root:

```bash
python scripts/export_openapi.py
```

This writes:

- `examples/openapi.json`

## Expected core paths

- `GET /healthz`
- `GET /readyz`
- `POST /v1/decision`
- `POST /v1/replay`
- `POST /v1/batch`
- `POST /v1/fairness`
- `POST /v1/fairness/report`
- `POST /v1/audit-chain/verify`
