"""Tests for CSG data-quality handling."""

from custom_components.china_southern_power_grid_stat.data_quality import (
    apply_daily_corrections,
    corrected_month_total,
    validate_month_data,
)


def test_negative_daily_value_is_rejected() -> None:
    rows = [
        {"date": "2026-08-18", "kwh": 24.67},
        {"date": "2026-08-19", "kwh": -4008.59},
    ]
    assert validate_month_data(-3983.92, rows) == (
        "invalid monthly total kWh: -3983.92"
    )


def test_negative_daily_charge_is_rejected() -> None:
    rows = [{"date": "2026-08-20", "kwh": 31.47, "charge": -302.27}]
    assert validate_month_data(31.47, rows) == (
        "invalid daily charge for 2026-08-20: -302.27"
    )


def test_confirmed_correction_replaces_bad_day_and_recalculates_total() -> None:
    rows = [
        {"date": "2026-08-18", "kwh": 24.67},
        {"date": "2026-08-19", "kwh": -4008.59},
        {"date": "2026-08-20", "kwh": 31.47},
    ]
    corrected, applied = apply_daily_corrections(
        rows, {"2026-08-19": {"kwh": 25.51}}
    )
    assert applied == ["2026-08-19"]
    assert corrected[1]["kwh"] == 25.51
    assert corrected_month_total(corrected) == 81.65
    assert validate_month_data(81.65, corrected) is None


def test_corrections_do_not_mutate_api_rows() -> None:
    rows = [{"date": "2026-08-19", "kwh": -4008.59}]
    corrected, _ = apply_daily_corrections(
        rows, {"2026-08-19": {"kwh": 25.51}}
    )
    assert rows[0]["kwh"] == -4008.59
    assert corrected[0]["kwh"] == 25.51
