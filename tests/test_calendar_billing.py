"""Regression coverage for calendar energy and separately settled monthly bills."""

import asyncio
import datetime
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from homeassistant.const import STATE_UNAVAILABLE

from custom_components.china_southern_power_grid_stat.csg_client import CSGClient
from custom_components.china_southern_power_grid_stat.const import (
    ATTR_KEY_LAST_MONTH_BILL,
    ATTR_KEY_LATEST_DAY_DATE,
    ATTR_KEY_THIS_MONTH_BY_DAY,
    SUFFIX_LAST_MONTH_COST,
    SUFFIX_LAST_MONTH_KWH,
    SUFFIX_LATEST_DAY_KWH,
    SUFFIX_THIS_MONTH_COST,
    SUFFIX_THIS_MONTH_KWH,
    SUFFIX_YESTERDAY_KWH,
)
from custom_components.china_southern_power_grid_stat.sensor import (
    CSGBaseSensor,
    CSGCoordinator,
    UNSUPPORTED_SUFFIXES,
)

ACCOUNT = SimpleNamespace(
    account_number="test",
    area_code="0300",
    ele_customer_id="binding",
    metering_point_id="point",
    metering_point_number="meter",
)


def calendar_client(rows, total="3"):
    client = CSGClient()
    client.api_query_electricity_calender = Mock(
        return_value={"totalPower": total, "result": rows}
    )
    client.api_query_day_electric_by_m_point = Mock(
        side_effect=AssertionError("retired endpoint")
    )
    return client


def test_calendar_sorts_dates_preserves_zero_and_skips_unreported_cells():
    client = calendar_client(
        [
            {"date": "2026-10-03", "power": "3"},
            {"date": "2026-10-01", "power": "0"},
            {"date": "2026-10-02", "power": None},
        ]
    )
    total, rows = client.get_month_daily_usage_detail(ACCOUNT, (2026, 10))
    assert total == 3
    assert rows == [{"date": "2026-10-01", "kwh": 0}, {"date": "2026-10-03", "kwh": 3}]
    client.api_query_electricity_calender.assert_called_once_with(
        2026, 10, "0300", "binding", "point", "meter"
    )
    client.api_query_day_electric_by_m_point.assert_not_called()


@pytest.mark.parametrize(
    "dates",
    [
        ["2026-10-01", "2026-10-01"],
        ["2026-09-30"],
        ["2026-10-32"],
    ],
)
def test_invalid_calendar_dates_are_rejected(dates):
    client = calendar_client([{"date": date, "power": "3"} for date in dates])
    with pytest.raises(ValueError):
        client.get_month_daily_usage_detail(ACCOUNT, (2026, 10))


def coordinator(today=datetime.date(2026, 10, 4)):
    value = object.__new__(CSGCoordinator)
    value._today = today
    value._this_year = today.year
    value._last_year = today.year - 1
    value._this_month_ym = (today.year, today.month)
    previous = today.replace(day=1) - datetime.timedelta(days=1)
    value._last_month_ym = (previous.year, previous.month)
    value._last_year_cache = {}
    value._gathered_data = {"test": {}}
    value._daily_corrections = {}

    async def execute(func, *args, **kwargs):
        return func(*args, **kwargs)

    value.hass = SimpleNamespace(async_add_executor_job=execute)
    value._client = SimpleNamespace(
        get_balance_and_arrears=Mock(return_value=(0, 354.13)),
        get_year_month_stats=Mock(
            side_effect=lambda account, year: (
                354.13,
                515,
                [{"month": "2026-09", "charge": 354.13, "kwh": 515}],
            )
        ),
        get_month_daily_usage_detail=Mock(
            side_effect=lambda account, ym: (
                (
                    65.78,
                    [
                        {"date": "2026-10-01", "kwh": 16.85},
                        {"date": "2026-10-02", "kwh": 23.12},
                        {"date": "2026-10-03", "kwh": 25.81},
                    ],
                )
                if ym == (2026, 10)
                else (515.12, [{"date": "2026-09-30", "kwh": 24.41}])
            )
        ),
    )
    for name, method in vars(value._client).items():
        method.__name__ = name
    return value


def refresh(value):
    value._gathered_data = {"test": {}}
    asyncio.run(value._async_update_account_data(ACCOUNT))
    return value._gathered_data["test"]


def test_calendar_and_bill_are_independent_and_retired_fields_unavailable():
    data = refresh(coordinator())
    assert data[SUFFIX_THIS_MONTH_KWH] == 65.78
    assert data[SUFFIX_LAST_MONTH_KWH] == 515.12
    assert data[SUFFIX_LAST_MONTH_COST] == 354.13
    assert data[ATTR_KEY_LAST_MONTH_BILL] == {
        "billing_month": "2026-09",
        "billing_kwh": 515,
        "data_source": "annual_billing",
    }
    assert data[SUFFIX_LATEST_DAY_KWH] == data[SUFFIX_YESTERDAY_KWH] == 25.81
    assert data[ATTR_KEY_LATEST_DAY_DATE][ATTR_KEY_LATEST_DAY_DATE] == "2026-10-03"
    assert all(data[suffix] == STATE_UNAVAILABLE for suffix in UNSUPPORTED_SUFFIXES)


@pytest.mark.parametrize(
    "rows, expected",
    [
        ([{"month": "2026-08", "charge": 470, "kwh": 658}], STATE_UNAVAILABLE),
        ([{"month": "202609", "charge": 0, "kwh": 0}], 0),
        ([{"month": "2026-09", "charge": None, "kwh": 515}], STATE_UNAVAILABLE),
    ],
)
def test_bill_must_match_exact_month_and_zero_is_valid(rows, expected):
    value = coordinator()
    value._client.get_year_month_stats.return_value = None
    value._client.get_year_month_stats.side_effect = lambda *args: (0, 0, rows)
    assert refresh(value)[SUFFIX_LAST_MONTH_COST] == expected


def test_missing_yesterday_does_not_relabel_latest_reported_day():
    value = coordinator(datetime.date(2026, 10, 5))
    data = refresh(value)
    assert data[SUFFIX_YESTERDAY_KWH] == STATE_UNAVAILABLE
    assert data[SUFFIX_LATEST_DAY_KWH] == 25.81
    assert data[ATTR_KEY_LATEST_DAY_DATE][ATTR_KEY_LATEST_DAY_DATE] == "2026-10-03"


def test_january_rollover_uses_previous_year_bill_and_december_yesterday():
    value = coordinator(datetime.date(2027, 1, 1))
    value._client.get_month_daily_usage_detail.side_effect = lambda account, ym: (
        (0, []) if ym == (2027, 1) else (20, [{"date": "2026-12-31", "kwh": 20}])
    )
    value._client.get_year_month_stats.side_effect = lambda account, year: (
        (0, 0, [])
        if year == 2027
        else (10, 20, [{"month": "2026-12", "charge": 10, "kwh": 20}])
    )
    data = refresh(value)
    assert data[SUFFIX_THIS_MONTH_KWH] == STATE_UNAVAILABLE
    assert data[SUFFIX_LAST_MONTH_COST] == 10
    assert data[ATTR_KEY_LAST_MONTH_BILL]["billing_month"] == "2026-12"
    assert data[SUFFIX_YESTERDAY_KWH] == 20
    assert data[ATTR_KEY_LATEST_DAY_DATE][ATTR_KEY_LATEST_DAY_DATE] == "2026-12-31"


def test_billing_failure_does_not_hide_calendar_and_recovers():
    value = coordinator()
    value._client.get_year_month_stats.side_effect = RuntimeError("source offline")
    data = refresh(value)
    assert data[SUFFIX_THIS_MONTH_KWH] == 65.78
    assert data[SUFFIX_LAST_MONTH_COST] == STATE_UNAVAILABLE
    value._client.get_year_month_stats.side_effect = lambda *args: (
        1,
        2,
        [{"month": "2026-09", "charge": 1, "kwh": 2}],
    )
    assert refresh(value)[SUFFIX_LAST_MONTH_COST] == 1


def test_calendar_failure_does_not_hide_bill_or_retain_stale_rows():
    value = coordinator()
    refresh(value)
    value._client.get_month_daily_usage_detail.side_effect = RuntimeError(
        "source offline"
    )
    data = refresh(value)
    assert data[SUFFIX_LAST_MONTH_COST] == 354.13
    assert data[SUFFIX_THIS_MONTH_KWH] == STATE_UNAVAILABLE
    assert data[ATTR_KEY_THIS_MONTH_BY_DAY][ATTR_KEY_THIS_MONTH_BY_DAY] == []
    assert data[SUFFIX_LATEST_DAY_KWH] == STATE_UNAVAILABLE


def test_future_and_negative_calendar_values_are_not_published():
    for rows in [
        [{"date": "2026-10-05", "kwh": 1}],
        [{"date": "2026-10-03", "kwh": -1}],
    ]:
        value = coordinator()
        value._client.get_month_daily_usage_detail.side_effect = lambda *args: (1, rows)
        assert refresh(value)[SUFFIX_THIS_MONTH_KWH] == STATE_UNAVAILABLE


def test_confirmed_corrections_work_but_do_not_inject_daily_charges():
    value = coordinator()
    value._daily_corrections = {"test": {"2026-10-03": {"kwh": 26, "charge": 99}}}
    data = refresh(value)
    assert data[SUFFIX_THIS_MONTH_KWH] == 65.97
    assert data[SUFFIX_LATEST_DAY_KWH] == 26
    assert (
        "charge" not in data[ATTR_KEY_THIS_MONTH_BY_DAY][ATTR_KEY_THIS_MONTH_BY_DAY][-1]
    )


def test_unavailable_sensor_clears_value_before_state_write():
    sensor = object.__new__(CSGBaseSensor)
    sensor._account_number = "test"
    sensor._entity_suffix = SUFFIX_THIS_MONTH_COST
    sensor._extra_state_attributes_key = ATTR_KEY_THIS_MONTH_BY_DAY
    sensor._coordinator = SimpleNamespace(
        data={"test": {SUFFIX_THIS_MONTH_COST: STATE_UNAVAILABLE}}
    )
    sensor.coordinator = SimpleNamespace(last_update_success=True)
    sensor._attr_native_value = 123
    sensor._attr_available = True
    snapshots = []
    sensor.async_write_ha_state = lambda: snapshots.append(
        (sensor._attr_available, sensor._attr_native_value)
    )
    sensor._handle_coordinator_update()
    assert snapshots == [(False, None)]
    assert not sensor.available
    assert sensor._attr_extra_state_attributes == {
        "unavailable_reason": "not_provided_by_source"
    }


def test_previous_year_bill_cache_refreshes_daily_and_current_bill_every_poll():
    value = coordinator()
    refresh(value)
    refresh(value)
    assert [
        call.args[1] for call in value._client.get_year_month_stats.call_args_list
    ].count(2025) == 1
    assert [
        call.args[1] for call in value._client.get_year_month_stats.call_args_list
    ].count(2026) == 2
    value._today += datetime.timedelta(days=1)
    refresh(value)
    assert [
        call.args[1] for call in value._client.get_year_month_stats.call_args_list
    ].count(2025) == 2


@pytest.mark.parametrize("charge,kwh", [("nan", "1"), ("1", "inf"), ("1", "-1")])
def test_invalid_billing_values_are_rejected(charge, kwh):
    client = CSGClient()
    client.api_get_fee_analyze_details = Mock(
        return_value={
            "totalBillingElectricity": kwh,
            "totalActualAmount": charge,
            "electricAndChargeList": [
                {
                    "yearMonth": "202609",
                    "actualTotalAmount": charge,
                    "billingElectricity": kwh,
                }
            ],
        }
    )
    with pytest.raises(ValueError):
        client.get_year_month_stats(ACCOUNT, 2026)
