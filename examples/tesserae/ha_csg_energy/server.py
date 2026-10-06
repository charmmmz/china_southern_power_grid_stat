"""China Southern Power Grid data, normalized from Home Assistant.

The CSG Home Assistant integration exposes one sensor per measure and stores
the useful chart series in entity attributes (``this_month_by_day``,
``last_month_by_day`` and ``this_year_by_month``).  This widget deliberately
uses those source arrays instead of Home Assistant recorder history: the
integration remains useful even when recorder excludes the CSG entities.

No full account or meter identifier is returned to the browser.  The editor
may use the discovered entity prefix as an option value, but rendered data only
contains a masked label (last four digits) or a user supplied label.
"""

from __future__ import annotations

import math
from calendar import monthrange
import re
import time
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo
from typing import Any

try:
    from flask import current_app
except ModuleNotFoundError:  # pragma: no cover - unit tests patch _core()
    current_app = None


ENTITY_PREFIX = "sensor.csgaccount_"
KNOWN_SUFFIXES = (
    "this_month_total_usage", "last_month_total_usage", "last_month_total_cost",
    "this_year_total_usage", "this_year_total_cost", "last_year_total_usage",
    "last_year_total_cost", "latest_day_kwh", "yesterday_kwh", "arrears", "balance",
)
STATUS_ENTITIES = {"arrears": "sensor.electricity_arrears_status", "data": "sensor.electricity_data_status"}
MISSING = {"", "unknown", "unavailable", "none", "null"}


def _core() -> Any:
    if current_app is None:
        return None
    plugin = current_app.config["PLUGIN_REGISTRY"].get("ha_core")
    return plugin.server_module if plugin is not None else None


def _clean(value: Any) -> str:
    if value is None:
        return ""
    text = str(value).strip()
    return "" if text.casefold() in MISSING else text


def _number(value: Any) -> float | None:
    text = _clean(value)
    if not text:
        return None
    try:
        number = float(text)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def _rounded(value: Any, digits: int = 2) -> float | None:
    number = _number(value)
    return round(number, digits) if number is not None else None


def _attributes(state: dict[str, Any] | None) -> dict[str, Any]:
    attrs = (state or {}).get("attributes") or {}
    return attrs if isinstance(attrs, dict) else {}


def _split_entity(entity_id: str) -> tuple[str, str] | None:
    if not entity_id.startswith(ENTITY_PREFIX):
        return None
    for suffix in KNOWN_SUFFIXES:
        marker = f"_{suffix}"
        if entity_id.endswith(marker):
            return entity_id[: -len(marker)], suffix
    return None


def _discover_accounts(states: list[dict[str, Any]]) -> dict[str, dict[str, dict[str, Any]]]:
    accounts: dict[str, dict[str, dict[str, Any]]] = {}
    for state in states:
        entity_id = str(state.get("entity_id") or "")
        parsed = _split_entity(entity_id)
        if parsed is None:
            continue
        account, suffix = parsed
        accounts.setdefault(account, {})[suffix] = state
    return accounts


def _masked_account(account: str) -> str:
    digits = re.findall(r"\d+", account)
    tail = digits[-1][-4:] if digits else "GRID"
    return f"CSG •••• {tail}"


def choices(name: str) -> list[dict[str, str]]:
    if name != "account":
        return []
    core = _core()
    if core is None:
        return []
    try:
        accounts = _discover_accounts(core.get_states())
    except Exception:
        return [{"value": "", "label": "Home Assistant unavailable"}]
    if not accounts:
        return [{"value": "", "label": "No China Southern Grid account found"}]
    return [
        {"value": account, "label": _masked_account(account)}
        for account in sorted(accounts)
    ]


def _normalise_days(raw: Any) -> list[dict[str, Any]]:
    if not isinstance(raw, list):
        return []
    by_date: dict[str, dict[str, Any]] = {}
    for item in raw:
        if not isinstance(item, dict):
            continue
        date = _clean(item.get("date"))
        if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", date):
            continue
        try:
            datetime.strptime(date, "%Y-%m-%d")
        except ValueError:
            continue
        kwh = _rounded(item.get("kwh"))
        if kwh is not None and kwh >= 0:
            by_date[date] = {"date": date, "kwh": kwh}
    return [by_date[date] for date in sorted(by_date)]


def _normalise_months(raw: Any) -> list[dict[str, Any]]:
    if not isinstance(raw, list):
        return []
    by_month: dict[str, dict[str, Any]] = {}
    for item in raw:
        if not isinstance(item, dict):
            continue
        month = _clean(item.get("month"))
        if not re.fullmatch(r"\d{4}-\d{2}", month):
            continue
        by_month[month] = {
            "month": month,
            "charge": _rounded(item.get("charge")),
            "kwh": _rounded(item.get("kwh")),
        }
    return [by_month[month] for month in sorted(by_month)]


def _attribute_series(
    account: dict[str, dict[str, Any]], suffixes: tuple[str, ...], key: str
) -> list[dict[str, Any]]:
    for suffix in suffixes:
        raw = _attributes(account.get(suffix)).get(key)
        series = _normalise_months(raw) if "by_month" in key else _normalise_days(raw)
        if series:
            return series
    return []


def _state_value(account: dict[str, dict[str, Any]], suffix: str) -> float | None:
    return _rounded((account.get(suffix) or {}).get("state"))


def _sum(items: list[dict[str, Any]], field: str) -> float | None:
    values = [item.get(field) for item in items if item.get(field) is not None]
    return round(sum(values), 2) if values else None


def _mean(items: list[dict[str, Any]], field: str) -> float | None:
    values = [item.get(field) for item in items if item.get(field) is not None]
    return round(sum(values) / len(values), 2) if values else None


def _quantile(values: list[float], q: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    if len(ordered) == 1:
        return ordered[0]
    pos = (len(ordered) - 1) * q
    lower = int(math.floor(pos))
    upper = int(math.ceil(pos))
    if lower == upper:
        return ordered[lower]
    weight = pos - lower
    return ordered[lower] * (1 - weight) + ordered[upper] * weight


def _window(current: list[dict[str, Any]], previous: list[dict[str, Any]], raw: Any) -> list[dict[str, Any]]:
    value = _clean(raw).lower() or "14"
    if value in {"month", "current_month"}:
        return current
    try:
        limit = max(3, min(62, int(value)))
    except ValueError:
        limit = 14
    rows = sorted(previous + current, key=lambda row: row["date"])
    if not rows:
        return []
    start = (date.fromisoformat(rows[-1]["date"]) - timedelta(days=limit - 1)).isoformat()
    return [row for row in rows if row["date"] >= start]


def _comparison(current: list[dict[str, Any]], previous: list[dict[str, Any]]) -> dict[str, Any]:
    # Compare identical day numbers, never the first N records across gaps.
    now = {row["date"][-2:]: row for row in current}
    before = {row["date"][-2:]: row for row in previous}
    matched = sorted(now.keys() & before.keys())
    current_kwh = _sum([now[day] for day in matched], "kwh")
    previous_kwh = _sum([before[day] for day in matched], "kwh")
    delta = None
    if current_kwh is not None and previous_kwh not in (None, 0):
        delta = round((current_kwh - previous_kwh) / previous_kwh * 100, 1)
    return {"days": len(matched), "current_kwh": current_kwh, "previous_kwh": previous_kwh, "delta_pct": delta}


def _average_comparison(current: list[dict[str, Any]], previous: list[dict[str, Any]], period: str) -> dict[str, Any]:
    """Compare reported current days with a complete previous calendar month."""
    year, month = (int(part) for part in period.split("-"))
    expected = {f"{period}-{day:02d}" for day in range(1, monthrange(year, month)[1] + 1)}
    actual = {row["date"] for row in previous}
    complete = actual == expected and len(previous) == len(expected)
    current_average = sum(row["kwh"] for row in current) / len(current) if current else None
    previous_average = sum(row["kwh"] for row in previous) / len(previous) if complete else None
    delta = None
    if current_average is not None and previous_average not in (None, 0):
        delta = round((current_average / previous_average - 1) * 100, 1)
    return {
        "current_daily_kwh": round(current_average, 2) if current_average is not None else None,
        "previous_daily_kwh": round(previous_average, 2) if previous_average is not None else None,
        "delta_pct": delta,
    }


def _thresholds(series: list[dict[str, Any]], options: dict[str, Any]) -> dict[str, Any]:
    mode = _clean(options.get("threshold_mode")).lower() or "auto"
    values = [float(item["kwh"]) for item in series if item.get("kwh") is not None]
    # Cost thresholds from older canvases are not energy thresholds.
    low = _number(options.get("low_kwh_threshold")) if mode == "manual" else None
    high = _number(options.get("high_kwh_threshold")) if mode == "manual" else None
    if low is None or high is None or low < 0 or high <= low:
        mode = "auto"
        low = _quantile(values, 0.33)
        high = _quantile(values, 0.72)
    low = low if low is not None else 15.0
    high = high if high is not None else 25.0
    return {"mode": mode, "low": round(low, 2), "high": round(max(low + 0.01, high), 2), "unit": "kWh"}


def _today() -> date:
    return datetime.now(ZoneInfo("Asia/Shanghai")).date()


def _status(states: list[dict[str, Any]]) -> dict[str, str]:
    by_id = {str(state.get("entity_id") or ""): state for state in states}
    return {
        name: _clean((by_id.get(entity_id) or {}).get("state"))
        for name, entity_id in STATUS_ENTITIES.items()
    }


def fetch(
    options: dict[str, Any], settings: dict[str, Any], *, ctx: dict[str, Any]
) -> dict[str, Any]:
    del settings, ctx
    core = _core()
    if core is None:
        return {"error": "Home Assistant Core plugin is unavailable"}
    try:
        states = core.get_states()
    except Exception as err:
        return {"error": core.coerce_error(err)}

    accounts = _discover_accounts(states)
    if not accounts:
        return {
            "empty": True,
            "label": "ENERGY//USAGE",
            "message": "No China Southern Power Grid entities found",
        }

    requested = _clean(options.get("account"))
    if requested and requested not in accounts:
        return {"error": "Selected electricity account is unavailable"}
    account_key = requested or sorted(accounts)[0]
    account = accounts[account_key]

    today = _today()
    current_month = today.strftime("%Y-%m")
    previous_month = (today.replace(day=1) - timedelta(days=1)).strftime("%Y-%m")
    current_days = [row for row in _attribute_series(account, ("this_month_total_usage",), "this_month_by_day")
                    if row["date"].startswith(current_month) and row["date"] <= today.isoformat()]
    previous_days = [row for row in _attribute_series(account, ("last_month_total_usage",), "last_month_by_day")
                     if row["date"].startswith(previous_month)]
    year_months = _attribute_series(account, ("this_year_total_usage", "this_year_total_cost"), "this_year_by_month")
    visible_series = _window(current_days, previous_days, options.get("window"))
    reported_days = current_days + previous_days
    latest = max(reported_days, key=lambda row: row["date"]) if reported_days else {"date": "", "kwh": None}
    latest_attrs = _attributes(account.get("latest_day_kwh"))
    latest_date = _clean(latest_attrs.get("latest_day_date"))
    latest_kwh = _state_value(account, "latest_day_kwh")
    if re.fullmatch(r"\d{4}-\d{2}-\d{2}", latest_date) and latest_date > latest["date"] and latest_date <= today.isoformat() and latest_kwh is not None:
        latest = {"date": latest_date, "kwh": latest_kwh}

    billing_attrs = _attributes(account.get("last_month_total_cost"))
    billing_month = _clean(billing_attrs.get("billing_month"))
    last_cost = _state_value(account, "last_month_total_cost") if billing_month == previous_month else None
    if last_cost is None:
        bill = next((row for row in year_months if row["month"] == previous_month), {})
        last_cost = bill.get("charge")
    month_kwh = _state_value(account, "this_month_total_usage")
    previous_kwh = _state_value(account, "last_month_total_usage")
    average_comparison = _average_comparison(current_days, previous_days, previous_month)
    custom_label = _clean(options.get("account_label"))
    label = _clean(options.get("label")) or "ENERGY//USAGE"
    if label == "ENERGY//COST":
        label = "ENERGY//USAGE"
    return {
        "label": label,
        "account_label": custom_label or _masked_account(account_key),
        "account_count": len(accounts),
        "latest": latest,
        "month": {
            "period": current_month,
            "total_kwh": month_kwh,
            "series_kwh": _sum(current_days, "kwh"),
            "average_daily_kwh": _mean(current_days, "kwh"),
            "days": len(current_days),
            "comparison": _comparison(current_days, previous_days),
            "average_comparison": average_comparison,
        },
        "previous_month": {
            "period": previous_month,
            "total_kwh": previous_kwh,
            "average_daily_kwh": average_comparison["previous_daily_kwh"],
            "total_cost": last_cost,
            "billing_month": previous_month if last_cost is not None else "",
        },
        "series": visible_series,
        "current_month_days": current_days,
        "previous_month_days": previous_days,
        "year_months": [row for row in year_months if row["month"] < current_month],
        "thresholds": _thresholds(visible_series, options),
        "billing": {"balance": _state_value(account, "balance"), "arrears": _state_value(account, "arrears")},
        "status": _status(states),
        "updated_at": datetime.now().astimezone().isoformat(),
        "_fetched_at": int(time.time()),
    }
