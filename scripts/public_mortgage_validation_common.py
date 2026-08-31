"""Shared helpers for public institutional mortgage validation scripts.

These helpers normalize heterogeneous public mortgage datasets into the
engine-compatible categorical fields used by causal-credit-risk-engine.
"""

from __future__ import annotations

import csv
from pathlib import Path
import re
from typing import Any


NORMALIZED_COLUMNS: tuple[str, ...] = (
    "source_dataset",
    "source_record_id",
    "tenant_id",
    "tenure",
    "utilization",
    "income",
    "dsc",
    "risk",
    "stability_proxy",
    "affordability_proxy",
    "performance_outcome",
    "segment",
    "action_taken",
    "loan_purpose",
    "geography_state",
    "geography_county",
    "geography_tract",
    "race",
    "sex",
    "income_amount",
    "ltv_ratio",
    "cltv_ratio",
    "dti_ratio",
    "credit_score",
    "loan_age_months",
    "delinquency_status",
    "occupancy_status",
    "property_type",
    "modification_flag",
    "zero_balance_code",
    "ltv_risk",
    "cltv_risk",
    "dti_risk",
    "fico_risk",
    "loan_age_risk",
    "delinquency_history_risk",
    "occupancy_risk",
    "loan_purpose_risk",
    "property_type_risk",
    "modification_risk",
    "default_loss_risk",
    "mapping_notes",
)


def normalize_header(name: str) -> str:
    cleaned = name.strip().lstrip("\ufeff")
    cleaned = cleaned.replace("%", " pct ")
    cleaned = re.sub(r"[^A-Za-z0-9]+", "_", cleaned)
    return cleaned.strip("_").lower()


def read_delimited_rows(
    *,
    input_path: str | Path,
    delimiter: str,
    has_header: bool,
    fieldnames: list[str] | None = None,
    encoding: str = "utf-8-sig",
) -> list[dict[str, str]]:
    path = Path(input_path)
    with path.open("r", encoding=encoding, newline="") as fh:
        if has_header:
            reader = csv.DictReader(fh, delimiter=delimiter)
            if reader.fieldnames is None:
                raise ValueError(f"Input has no header row: {path}")
            headers = [normalize_header(name) for name in reader.fieldnames]
            rows: list[dict[str, str]] = []
            for row in reader:
                normalized_row = {
                    headers[idx]: str(value).strip()
                    for idx, value in enumerate(row.values())
                    if idx < len(headers)
                }
                rows.append(normalized_row)
            return rows

        if not fieldnames:
            raise ValueError("fieldnames are required when has_header is false")
        normalized_fieldnames = [normalize_header(name) for name in fieldnames]
        reader = csv.reader(fh, delimiter=delimiter)
        rows = []
        for raw in reader:
            row: dict[str, str] = {}
            for idx, key in enumerate(normalized_fieldnames):
                row[key] = raw[idx].strip() if idx < len(raw) else ""
            rows.append(row)
        return rows


def write_normalized_csv(path: str | Path, rows: list[dict[str, Any]]) -> None:
    out_path = Path(path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(NORMALIZED_COLUMNS))
        writer.writeheader()
        for row in rows:
            normalized = {column: str(row.get(column, "")) for column in NORMALIZED_COLUMNS}
            writer.writerow(normalized)


def first_value(row: dict[str, str], aliases: tuple[str, ...]) -> str | None:
    for alias in aliases:
        value = row.get(normalize_header(alias))
        if value is None:
            continue
        stripped = str(value).strip()
        if stripped != "":
            return stripped
    return None


def to_float(value: str | None) -> float | None:
    if value is None:
        return None
    token = str(value).strip()
    if token in {"", "NA", "N/A", "Exempt", "999", "9999"}:
        return None
    token = token.replace("%", "").replace(",", "")
    try:
        return float(token)
    except ValueError:
        return None


def to_int(value: str | None) -> int | None:
    parsed = to_float(value)
    if parsed is None:
        return None
    return int(parsed)


def _flagged(value: str | None) -> bool:
    if value is None:
        return False
    return str(value).strip().upper() in {"Y", "YES", "TRUE", "T", "1", "MOD", "MODIFIED"}


def _delinquency_value(row: dict[str, str]) -> str | None:
    return first_value(
        row,
        (
            "current_loan_delinquency_status",
            "loan_delinquency_status",
            "delinquency_status",
        ),
    )


def _serious_delinquency(value: str | None) -> bool:
    if value is None:
        return False
    token = value.strip().upper()
    if token in {"RA", "REO", "FC", "F", "D"}:
        return True
    parsed = to_int(token)
    return parsed is not None and parsed >= 3


def _any_delinquency(value: str | None) -> bool:
    if value is None:
        return False
    token = value.strip().upper()
    if token in {"RA", "REO", "FC", "F", "D"}:
        return True
    parsed = to_int(token)
    return parsed is not None and parsed > 0


def _ltv_value(row: dict[str, str]) -> float | None:
    return to_float(
        first_value(
            row,
            (
                "original_loan_to_value",
                "original_ltv",
                "current_ltv",
                "ltv",
                "loan_to_value_ratio",
            ),
        )
    )


def _cltv_value(row: dict[str, str]) -> float | None:
    return to_float(
        first_value(
            row,
            (
                "original_combined_loan_to_value",
                "original_cltv",
                "current_cltv",
                "cltv",
                "combined_loan_to_value_ratio",
            ),
        )
    )


def _dti_value(row: dict[str, str]) -> float | None:
    return to_float(
        first_value(
            row,
            (
                "original_debt_to_income_ratio",
                "debt_to_income_ratio",
                "dti",
            ),
        )
    )


def _fico_value(row: dict[str, str]) -> int | None:
    borrower = to_int(
        first_value(
            row,
            (
                "credit_score",
                "borrower_credit_score",
                "current_credit_score",
            ),
        )
    )
    co_borrower = to_int(first_value(row, ("co_borrower_credit_score",)))
    scores = [score for score in (borrower, co_borrower) if score is not None and score > 0]
    if not scores:
        return None
    return min(scores)


def _loan_age_value(row: dict[str, str]) -> int | None:
    return to_int(
        first_value(
            row,
            (
                "loan_age",
                "loan_age_months",
                "age_of_mortgage_note",
                "age_of_mortgage",
            ),
        )
    )


def map_ltv_risk(row: dict[str, str]) -> tuple[str, str]:
    ltv = _ltv_value(row)
    if ltv is None:
        return ("elevated", "ltv_risk_default_elevated_missing_ltv")
    return ("elevated" if ltv >= 80 else "standard", "ltv_risk_from_ltv")


def map_cltv_risk(row: dict[str, str]) -> tuple[str, str]:
    cltv = _cltv_value(row)
    if cltv is None:
        return ("elevated", "cltv_risk_default_elevated_missing_cltv")
    return ("elevated" if cltv >= 80 else "standard", "cltv_risk_from_cltv")


def map_dti_risk(row: dict[str, str]) -> tuple[str, str]:
    dti = _dti_value(row)
    if dti is None:
        return ("elevated", "dti_risk_default_elevated_missing_dti")
    return ("elevated" if dti >= 43 else "standard", "dti_risk_from_dti")


def map_fico_risk(row: dict[str, str]) -> tuple[str, str]:
    fico = _fico_value(row)
    if fico is None:
        return ("elevated", "fico_risk_default_elevated_missing_fico")
    return ("elevated" if fico < 680 else "standard", "fico_risk_from_credit_score")


def map_loan_age_risk(row: dict[str, str]) -> tuple[str, str]:
    loan_age = _loan_age_value(row)
    if loan_age is None:
        return ("newer", "loan_age_risk_default_newer_missing_age")
    return ("seasoned" if loan_age >= 24 else "newer", "loan_age_risk_from_loan_age")


def map_delinquency_history_risk(row: dict[str, str]) -> tuple[str, str]:
    delinquency = _delinquency_value(row)
    return (
        "adverse" if _any_delinquency(delinquency) else "clean",
        "delinquency_history_risk_from_status",
    )


def map_occupancy_risk(row: dict[str, str]) -> tuple[str, str]:
    occupancy = first_value(row, ("occupancy_status", "occupancy", "occupancy_type"))
    if occupancy is None:
        return ("unknown", "occupancy_risk_missing")
    token = occupancy.strip().upper()
    elevated = token in {"I", "INVESTOR", "INVESTMENT", "S", "SECOND", "SECOND_HOME", "2", "3"}
    return ("elevated" if elevated else "standard", "occupancy_risk_from_status")


def map_loan_purpose_risk(row: dict[str, str]) -> tuple[str, str]:
    purpose = first_value(row, ("loan_purpose", "loan_purpose_type"))
    if purpose is None:
        return ("unknown", "loan_purpose_risk_missing")
    token = purpose.strip().upper().replace(" ", "_")
    elevated = token in {"C", "CASH_OUT", "CASH_OUT_REFINANCE", "32", "REFINANCE_CASH_OUT"}
    return ("elevated" if elevated else "standard", "loan_purpose_risk_from_purpose")


def map_property_type_risk(row: dict[str, str]) -> tuple[str, str]:
    property_type = first_value(row, ("property_type", "property_type_code"))
    unit_count = to_int(first_value(row, ("number_of_units", "unit_count")))
    if property_type is None and unit_count is None:
        return ("unknown", "property_type_risk_missing")
    token = (property_type or "").strip().upper()
    elevated = token in {"CO", "CONDO", "CP", "COOP", "MH", "MANUFACTURED", "2-4", "MULTIFAMILY"}
    if unit_count is not None and unit_count > 1:
        elevated = True
    return ("elevated" if elevated else "standard", "property_type_risk_from_property")


def map_modification_risk(row: dict[str, str]) -> tuple[str, str]:
    modification = first_value(row, ("modification_flag", "loan_modification_flag"))
    return (
        "modified" if _flagged(modification) else "not_modified",
        "modification_risk_from_flag",
    )


def map_default_loss_risk(row: dict[str, str]) -> tuple[str, str]:
    zero_balance_code = first_value(row, ("zero_balance_code",))
    delinquency = _delinquency_value(row)
    if zero_balance_code is not None and zero_balance_code.strip().upper() in {"03", "06", "09"}:
        return ("adverse", "default_loss_risk_from_zero_balance_code")
    if _serious_delinquency(delinquency):
        return ("adverse", "default_loss_risk_from_serious_delinquency")
    return ("clean", "default_loss_risk_clean")


def map_tenure_proxy(row: dict[str, str]) -> tuple[str, str]:
    # Mapping assumption: longer observed mortgage age proxies stronger repayment tenure.
    loan_age = _loan_age_value(row)
    if loan_age is not None:
        return ("long" if loan_age >= 24 else "short", "tenure_from_loan_age")
    return ("short", "tenure_default_short_missing_age")


def map_utilization_proxy(row: dict[str, str]) -> tuple[str, str]:
    # Mapping assumption: higher LTV/CLTV proxies higher leverage utilization.
    cltv = _cltv_value(row)
    ltv = _ltv_value(row)
    leverage = cltv if cltv is not None else ltv
    if leverage is not None:
        return ("high" if leverage >= 80 else "low", "utilization_from_ltv_cltv")
    return ("high", "utilization_default_high_missing_ltv")


def map_income_proxy(row: dict[str, str]) -> tuple[str, str]:
    # Mapping assumption: higher borrower credit score proxies greater income stability.
    fico = _fico_value(row)
    if fico is not None:
        return ("stable" if fico >= 680 else "unstable", "income_from_credit_score")
    return ("unstable", "income_default_unstable_missing_fico")


def map_dsc_proxy(row: dict[str, str]) -> tuple[str, str]:
    # Mapping assumption: higher DTI proxies weaker debt-service coverage.
    dti = _dti_value(row)
    if dti is not None:
        return (
            "below_threshold" if dti >= 43 else "above_threshold",
            "dsc_from_dti",
        )
    return ("below_threshold", "dsc_default_below_missing_dti")


def map_performance_outcome(row: dict[str, str]) -> tuple[str, str]:
    delinquency = _delinquency_value(row)
    if delinquency is not None:
        token = delinquency.strip().upper()
        if token in {"RA", "REO", "FC", "F", "D"}:
            return ("high_risk", "risk_from_delinquency_code")
        parsed = to_int(token)
        if parsed is not None:
            return (
                "high_risk" if parsed >= 3 else "low_risk",
                "risk_from_delinquency_bucket",
            )

    zero_balance_code = first_value(row, ("zero_balance_code",))
    if zero_balance_code is not None and zero_balance_code.strip().upper() in {"03", "06", "09"}:
        return ("high_risk", "risk_from_zero_balance_code")

    modification = first_value(row, ("modification_flag", "loan_modification_flag"))
    if _flagged(modification):
        return ("high_risk", "risk_from_modification_flag")

    action_taken = first_value(row, ("action_taken",))
    if action_taken is not None:
        code = action_taken.strip()
        if code in {"3", "7"}:
            return ("high_risk", "risk_from_hmda_action_taken")
        if code in {"1", "2", "6", "8"}:
            return ("low_risk", "risk_from_hmda_action_taken")

    return ("low_risk", "risk_default_low_missing_outcome")


def build_segment(row: dict[str, str]) -> str:
    race = first_value(row, ("applicant_race_1", "race", "race_of_applicant_or_borrower_1"))
    sex = first_value(row, ("applicant_sex", "sex", "sex_of_applicant_or_borrower"))
    state = first_value(row, ("property_state", "state", "state_2", "state_3"))
    parts = [item for item in (race, sex, state) if item]
    return "|".join(parts) if parts else "unspecified"


def normalized_record(
    *,
    source_dataset: str,
    source_record_id: str,
    row: dict[str, str],
) -> dict[str, str]:
    tenure, tenure_note = map_tenure_proxy(row)
    utilization, utilization_note = map_utilization_proxy(row)
    income_state, income_note = map_income_proxy(row)
    dsc_state, dsc_note = map_dsc_proxy(row)
    risk_state, risk_note = map_performance_outcome(row)
    ltv_risk, ltv_note = map_ltv_risk(row)
    cltv_risk, cltv_note = map_cltv_risk(row)
    dti_risk, dti_risk_note = map_dti_risk(row)
    fico_risk, fico_note = map_fico_risk(row)
    loan_age_risk, loan_age_note = map_loan_age_risk(row)
    delinquency_risk, delinquency_note = map_delinquency_history_risk(row)
    occupancy_risk, occupancy_note = map_occupancy_risk(row)
    purpose_risk, purpose_note = map_loan_purpose_risk(row)
    property_risk, property_note = map_property_type_risk(row)
    modification_risk, modification_note = map_modification_risk(row)
    default_loss_risk, default_loss_note = map_default_loss_risk(row)

    mapping_notes = ";".join(
        [
            tenure_note,
            utilization_note,
            income_note,
            dsc_note,
            risk_note,
            ltv_note,
            cltv_note,
            dti_risk_note,
            fico_note,
            loan_age_note,
            delinquency_note,
            occupancy_note,
            purpose_note,
            property_note,
            modification_note,
            default_loss_note,
        ]
    )

    return {
        "source_dataset": source_dataset,
        "source_record_id": source_record_id,
        "tenant_id": "default",
        "tenure": tenure,
        "utilization": utilization,
        "income": income_state,
        "dsc": dsc_state,
        "risk": risk_state,
        "stability_proxy": income_state,
        "affordability_proxy": dsc_state,
        "performance_outcome": risk_state,
        "segment": build_segment(row),
        "action_taken": first_value(row, ("action_taken",)) or "",
        "loan_purpose": first_value(row, ("loan_purpose",)) or "",
        "geography_state": first_value(row, ("property_state", "state", "state_2", "state_3")) or "",
        "geography_county": first_value(row, ("county", "property_county")) or "",
        "geography_tract": first_value(row, ("census_tract", "tract")) or "",
        "race": first_value(row, ("race", "applicant_race_1", "race_of_applicant_or_borrower_1")) or "",
        "sex": first_value(row, ("sex", "applicant_sex", "sex_of_applicant_or_borrower")) or "",
        "income_amount": first_value(row, ("income", "borrower_income", "income_amount")) or "",
        "ltv_ratio": first_value(row, ("original_loan_to_value", "ltv", "original_ltv")) or "",
        "cltv_ratio": first_value(row, ("original_combined_loan_to_value", "cltv", "original_cltv")) or "",
        "dti_ratio": first_value(row, ("original_debt_to_income_ratio", "debt_to_income_ratio", "dti")) or "",
        "credit_score": first_value(row, ("credit_score", "borrower_credit_score")) or "",
        "loan_age_months": first_value(row, ("loan_age", "loan_age_months", "age_of_mortgage_note")) or "",
        "delinquency_status": first_value(
            row, ("current_loan_delinquency_status", "loan_delinquency_status", "delinquency_status")
        )
        or "",
        "occupancy_status": first_value(row, ("occupancy_status", "occupancy", "occupancy_type")) or "",
        "property_type": first_value(row, ("property_type", "property_type_code")) or "",
        "modification_flag": first_value(row, ("modification_flag", "loan_modification_flag")) or "",
        "zero_balance_code": first_value(row, ("zero_balance_code",)) or "",
        "ltv_risk": ltv_risk,
        "cltv_risk": cltv_risk,
        "dti_risk": dti_risk,
        "fico_risk": fico_risk,
        "loan_age_risk": loan_age_risk,
        "delinquency_history_risk": delinquency_risk,
        "occupancy_risk": occupancy_risk,
        "loan_purpose_risk": purpose_risk,
        "property_type_risk": property_risk,
        "modification_risk": modification_risk,
        "default_loss_risk": default_loss_risk,
        "mapping_notes": mapping_notes,
    }
