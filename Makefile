.PHONY: test cli json replay api fairness demo

test:
	python -m pytest -q

cli:
	python -m causal_credit_risk.cli

json:
	python -m causal_credit_risk.cli --json-only

replay:
	python -m causal_credit_risk.cli --replay-audit examples/audit_example.json

api:
	uvicorn causal_credit_risk.api:app --reload

fairness:
	python -m causal_credit_risk.cli --fairness-report-input examples/batch_output.example.csv --fairness-subgroup-column segment --fairness-output examples/fairness_report.example.json

demo:
	python scripts/run_end_to_end_demo.py
