"""Data-quality helpers for China Southern Power Grid responses."""

from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any

from .csg_client import WF_ATTR_CHARGE, WF_ATTR_DATE, WF_ATTR_KWH


def load_daily_corrections(path: str) -> dict[str, dict[str, dict[str, float]]]:
    """Load optional account/date corrections from a user-managed JSON file."""
    correction_path = Path(path)
    if not correction_path.exists():
        return {}

    raw = json.loads(correction_path.read_text(encoding="utf-8"))
    accounts = raw.get("accounts", {})
    if not isinstance(accounts, dict):
        raise ValueError("corrections.accounts must be an object")

    corrections: dict[str, dict[str, dict[str, float]]] = {}
    for account_number, account_days in accounts.items():
        if not isinstance(account_days, dict):
            raise ValueError(f"corrections for account {account_number} must be an object")
        normalized_days: dict[str, dict[str, float]] = {}
        for date, values in account_days.items():
            if not isinstance(values, dict) or WF_ATTR_KWH not in values:
                raise ValueError(
                    f"correction {account_number}/{date} must contain a kwh value"
                )
            normalized = {WF_ATTR_KWH: _nonnegative_number(values[WF_ATTR_KWH])}
            if WF_ATTR_CHARGE in values:
                normalized[WF_ATTR_CHARGE] = _nonnegative_number(
                    values[WF_ATTR_CHARGE]
                )
            normalized_days[str(date)] = normalized
        corrections[str(account_number)] = normalized_days
    return corrections


def apply_daily_corrections(
    by_day: list[dict[str, Any]],
    corrections: dict[str, dict[str, float]],
) -> tuple[list[dict[str, Any]], list[str]]:
    """Apply confirmed per-date corrections without mutating API response objects."""
    corrected_rows: list[dict[str, Any]] = []
    applied_dates: list[str] = []
    for row in by_day:
        corrected_row = dict(row)
        date = str(corrected_row.get(WF_ATTR_DATE, ""))
        correction = corrections.get(date)
        if correction:
            corrected_row.update(correction)
            applied_dates.append(date)
        corrected_rows.append(corrected_row)
    return corrected_rows, applied_dates


def validate_month_data(
    total_kwh: float | str,
    by_day: list[dict[str, Any]] | str,
) -> str | None:
    """Return a validation error for impossible consumption data, else None."""
    if not _is_nonnegative_number(total_kwh):
        return f"invalid monthly total kWh: {total_kwh!r}"
    if not isinstance(by_day, list):
        return "daily usage is unavailable"
    for row in by_day:
        date = row.get(WF_ATTR_DATE, "unknown date")
        kwh = row.get(WF_ATTR_KWH)
        if not _is_nonnegative_number(kwh):
            return f"invalid daily kWh for {date}: {kwh!r}"
        charge = row.get(WF_ATTR_CHARGE)
        if charge is not None and not _is_nonnegative_number(charge):
            return f"invalid daily charge for {date}: {charge!r}"
    return None


def corrected_month_total(by_day: list[dict[str, Any]]) -> float:
    """Calculate a corrected monthly total from validated daily rows."""
    return round(sum(float(row[WF_ATTR_KWH]) for row in by_day), 2)


def _is_nonnegative_number(value: Any) -> bool:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return False
    return math.isfinite(number) and number >= 0


def _nonnegative_number(value: Any) -> float:
    if not _is_nonnegative_number(value):
        raise ValueError(f"correction values must be finite and non-negative: {value!r}")
    return float(value)
