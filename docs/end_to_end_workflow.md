# End-to-End Workflow

Local deterministic workflow:

1. Read CSV evidence
2. Run batch decisions
3. Generate fairness report
4. Build audit hash-chain
5. Verify audit hash-chain
6. Replay one audit decision
7. Write outputs for review

## Run

```bash
python scripts/run_end_to_end_demo.py
```

## Default outputs

- `outputs/demo/batch_output.csv`
- `outputs/demo/fairness_report.json`
- `outputs/demo/audit_chain.json`
- `outputs/demo/replay_result.json`
- `outputs/demo/summary.json`
