# API Examples

Base local URL:

```text
http://127.0.0.1:8000
```

## Health

```bash
curl -s http://127.0.0.1:8000/healthz
```

## Readiness

```bash
curl -s http://127.0.0.1:8000/readyz
```

## Decision

```bash
curl -s -X POST http://127.0.0.1:8000/v1/decision \
  -H "Content-Type: application/json" \
  -d "{\"tenure\":\"short\",\"utilization\":\"high\"}"
```

## Replay

```bash
curl -s -X POST http://127.0.0.1:8000/v1/replay \
  -H "Content-Type: application/json" \
  --data-binary @examples/audit_example.json
```

## Batch

```bash
curl -s -X POST http://127.0.0.1:8000/v1/batch \
  -H "Content-Type: application/json" \
  -d "[{\"tenure\":\"short\",\"utilization\":\"high\",\"segment\":\"A\"},{\"tenure\":\"long\",\"utilization\":\"low\",\"segment\":\"B\"}]"
```

## Fairness

```bash
curl -s -X POST http://127.0.0.1:8000/v1/fairness/report \
  -H "Content-Type: application/json" \
  -d "{\"rows\":[{\"segment\":\"A\",\"decision\":\"DECLINE\",\"risk_probability\":0.8},{\"segment\":\"B\",\"decision\":\"REVIEW\",\"risk_probability\":0.5}],\"subgroup_column\":\"segment\",\"min_sample_size\":2}"
```

## Audit-chain verification

```bash
curl -s -X POST http://127.0.0.1:8000/v1/audit-chain/verify \
  -H "Content-Type: application/json" \
  --data-binary @examples/audit_chain.example.json
```

Authentication is intentionally not embedded in the package. Apply auth at the deployment boundary.
