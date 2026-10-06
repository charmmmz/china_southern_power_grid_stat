"""Sensors for the China Southern Power Grid Statistics integration."""

from __future__ import annotations

import asyncio
import datetime
import logging
import time
import traceback
from datetime import timedelta
from zoneinfo import ZoneInfo
from typing import Any

import async_timeout
from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_USERNAME, STATE_UNAVAILABLE, UnitOfEnergy
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
)

from . import CONF_UPDATED_AT
from .const import (
    ATTR_KEY_CURRENT_LADDER_START_DATE,
    ATTR_KEY_APPLIED_CORRECTIONS,
    ATTR_KEY_DATA_QUALITY,
    ATTR_KEY_LAST_MONTH_BY_DAY,
    ATTR_KEY_LAST_MONTH_BILL,
    ATTR_KEY_LAST_YEAR_BY_MONTH,
    ATTR_KEY_LATEST_DAY_DATE,
    ATTR_KEY_THIS_MONTH_BY_DAY,
    ATTR_KEY_THIS_YEAR_BY_MONTH,
    CONF_AUTH_TOKEN,
    CONF_ELE_ACCOUNTS,
    CONF_SETTINGS,
    CONF_UPDATE_INTERVAL,
    CORRECTIONS_FILENAME,
    DATA_KEY_LAST_UPDATE_DAY,
    DOMAIN,
    SETTING_UPDATE_TIMEOUT,
    STATE_UPDATE_UNCHANGED,
    SUFFIX_ARR,
    SUFFIX_BAL,
    SUFFIX_CURRENT_LADDER,
    SUFFIX_CURRENT_LADDER_REMAINING_KWH,
    SUFFIX_CURRENT_LADDER_TARIFF,
    SUFFIX_LAST_MONTH_COST,
    SUFFIX_LAST_MONTH_KWH,
    SUFFIX_LAST_YEAR_COST,
    SUFFIX_LAST_YEAR_KWH,
    SUFFIX_LATEST_DAY_COST,
    SUFFIX_LATEST_DAY_KWH,
    SUFFIX_THIS_MONTH_COST,
    SUFFIX_THIS_MONTH_KWH,
    SUFFIX_THIS_YEAR_COST,
    SUFFIX_THIS_YEAR_KWH,
    SUFFIX_YESTERDAY_KWH,
)
from .data_quality import (
    apply_daily_corrections,
    corrected_month_total,
    load_daily_corrections,
    validate_month_data,
)
from .csg_client import (
    JSON_KEY_METERING_POINT_NUMBER,
    WF_ATTR_CHARGE,
    WF_ATTR_MONTH,
    WF_ATTR_DATE,
    WF_ATTR_KWH,
    CSGAPIError,
    CSGClient,
    CSGElectricityAccount,
    NotLoggedIn,
)

_LOGGER = logging.getLogger(__name__)

# Keep existing entity IDs/history, but never populate fields the sources lack.
UNSUPPORTED_SUFFIXES = frozenset(
    {
        SUFFIX_LATEST_DAY_COST,
        SUFFIX_THIS_MONTH_COST,
        SUFFIX_CURRENT_LADDER,
        SUFFIX_CURRENT_LADDER_REMAINING_KWH,
        SUFFIX_CURRENT_LADDER_TARIFF,
    }
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
):
    """Setup sensors from a config entry created in the integrations UI."""
    if not config_entry.data[CONF_ELE_ACCOUNTS]:
        _LOGGER.info("No ele accounts in config, exit entry setup")
        return
    coordinator = CSGCoordinator(hass, config_entry.entry_id)

    all_sensors = []
    for ele_account_number, _ in config_entry.data[CONF_ELE_ACCOUNTS].items():
        sensors = [
            # balance
            CSGCostSensor(coordinator, ele_account_number, SUFFIX_BAL),
            # arrears
            CSGCostSensor(coordinator, ele_account_number, SUFFIX_ARR),
            # yesterday kwh
            CSGEnergySensor(
                coordinator,
                ele_account_number,
                SUFFIX_YESTERDAY_KWH,
            ),
            # latest day usage that is available, with extra attributes about the date
            CSGEnergySensor(
                coordinator,
                ele_account_number,
                SUFFIX_LATEST_DAY_KWH,
                extra_state_attributes_key=ATTR_KEY_LATEST_DAY_DATE,
            ),
            # latest day cost that is available, with extra attributes about the date
            CSGCostSensor(
                coordinator,
                ele_account_number,
                SUFFIX_LATEST_DAY_COST,
                extra_state_attributes_key=ATTR_KEY_LATEST_DAY_DATE,
            ),
            # this year's total energy, with extra attributes about monthly usage
            CSGEnergySensor(
                coordinator,
                ele_account_number,
                SUFFIX_THIS_YEAR_KWH,
                extra_state_attributes_key=ATTR_KEY_THIS_YEAR_BY_MONTH,
            ),
            # this year's total cost
            CSGCostSensor(
                coordinator,
                ele_account_number,
                SUFFIX_THIS_YEAR_COST,
            ),
            # this month's total energy, with extra attributes about daily usage
            CSGEnergySensor(
                coordinator,
                ele_account_number,
                SUFFIX_THIS_MONTH_KWH,
                extra_state_attributes_key=ATTR_KEY_THIS_MONTH_BY_DAY,
            ),
            # this month's total cost, with extra attributes about daily usage
            CSGCostSensor(
                coordinator,
                ele_account_number,
                SUFFIX_THIS_MONTH_COST,
                extra_state_attributes_key=ATTR_KEY_THIS_MONTH_BY_DAY,
            ),
            # current ladder, with extra attributes about start date
            CSGLadderStageSensor(
                coordinator,
                ele_account_number,
                SUFFIX_CURRENT_LADDER,
                extra_state_attributes_key=ATTR_KEY_CURRENT_LADDER_START_DATE,
            ),
            # current ladder remaining kwh
            CSGEnergySensor(
                coordinator, ele_account_number, SUFFIX_CURRENT_LADDER_REMAINING_KWH
            ),
            # current ladder tariff
            CSGCostSensor(
                coordinator, ele_account_number, SUFFIX_CURRENT_LADDER_TARIFF
            ),
            # last year's total energy, with extra attributes about monthly usage
            CSGEnergySensor(
                coordinator,
                ele_account_number,
                SUFFIX_LAST_YEAR_KWH,
                extra_state_attributes_key=ATTR_KEY_LAST_YEAR_BY_MONTH,
            ),
            # last year's total cost
            CSGCostSensor(
                coordinator,
                ele_account_number,
                SUFFIX_LAST_YEAR_COST,
            ),
            # last month's total energy, with extra attributes about daily usage
            CSGEnergySensor(
                coordinator,
                ele_account_number,
                SUFFIX_LAST_MONTH_KWH,
                extra_state_attributes_key=ATTR_KEY_LAST_MONTH_BY_DAY,
            ),
            # last month's settled bill, separate from calendar usage
            CSGCostSensor(
                coordinator,
                ele_account_number,
                SUFFIX_LAST_MONTH_COST,
                extra_state_attributes_key=ATTR_KEY_LAST_MONTH_BILL,
            ),
        ]

        all_sensors.extend(sensors)

    async_add_entities(all_sensors)
    _LOGGER.debug(f"created {len(all_sensors)} sensors for config {config_entry.title}")
    # Schedule the first update to run in the background
    config_entry.async_create_task(
        hass,
        coordinator.async_config_entry_first_refresh(),
        f"{config_entry.title}_first_update",
    )


class CSGBaseSensor(
    CoordinatorEntity,
    SensorEntity,
):
    """Base CSG sensor"""

    def __init__(
        self,
        coordinator: DataUpdateCoordinator,
        account_number: str,
        entity_suffix: str,
        extra_state_attributes_key: str | None = None,
    ) -> None:
        SensorEntity.__init__(self)
        CoordinatorEntity.__init__(self, coordinator)
        self._coordinator = coordinator
        self._account_number = account_number

        self._entity_suffix = entity_suffix
        self._attr_available = False
        self._attr_entity_registry_enabled_default = (
            entity_suffix not in UNSUPPORTED_SUFFIXES
        )
        self._attr_extra_state_attributes = {}
        self._extra_state_attributes_key = extra_state_attributes_key

    @property
    def unique_id(self) -> str | None:
        return f"{DOMAIN}.{self._account_number}.{self._entity_suffix}"

    @property
    def name(self) -> str | None:
        return f"{self._account_number}-{self._entity_suffix}"

    @property
    def should_poll(self) -> bool:
        return False

    @property
    def available(self) -> bool:
        """A healthy coordinator does not imply every individual field exists."""
        return self._attr_available and self.coordinator.last_update_success

    @property
    def device_info(self) -> DeviceInfo:
        """Return the device info."""
        return DeviceInfo(
            identifiers={(DOMAIN, self._account_number)},
            name=f"CSGAccount-{self._account_number}",
            manufacturer="CSG",
            model="CSG Virtual Electricity Meter",
        )

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        # _LOGGER.debug(
        #     "%s coordinator update triggered",
        #     self.unique_id,
        # )

        if not self._coordinator.data:
            _LOGGER.error(
                "%s coordinator has no data",
                self.unique_id,
            )
            self._attr_available = False
            self.async_write_ha_state()
            return

        account_data = self._coordinator.data.get(self._account_number)
        if account_data is None:
            _LOGGER.warning("%s not found in coordinator data", self.unique_id)
            self._attr_available = False
            self.async_write_ha_state()
            return

        new_native_value = account_data.get(self._entity_suffix)
        if new_native_value == STATE_UPDATE_UNCHANGED:
            return

        if self._extra_state_attributes_key:
            self._attr_extra_state_attributes = account_data.get(
                self._extra_state_attributes_key, {}
            )
        self._attr_available = new_native_value not in (None, STATE_UNAVAILABLE)
        self._attr_native_value = new_native_value if self._attr_available else None
        if self._entity_suffix in UNSUPPORTED_SUFFIXES:
            self._attr_extra_state_attributes = {
                "unavailable_reason": "not_provided_by_source"
            }
        # Availability must change before publishing, otherwise a stale value survives.
        self.async_write_ha_state()


class CSGEnergySensor(CSGBaseSensor):
    """Representation of a CSG Energy Sensor."""

    _attr_native_unit_of_measurement = UnitOfEnergy.KILO_WATT_HOUR
    _attr_device_class = SensorDeviceClass.ENERGY
    _attr_state_class = SensorStateClass.TOTAL
    _attr_icon = "mdi:lightning-bolt"


class CSGCostSensor(CSGBaseSensor):
    """Representation of a CSG Cost Sensor."""

    _attr_native_unit_of_measurement = "CNY"
    _attr_device_class = SensorDeviceClass.MONETARY
    _attr_state_class = SensorStateClass.TOTAL
    _attr_icon = "mdi:currency-cny"


class CSGLadderStageSensor(CSGBaseSensor):
    """Representation of a CSG Ladder Stage Sensor."""

    _attr_icon = "mdi:stairs"


class CSGCoordinator(DataUpdateCoordinator):
    """CSG custom coordinator."""

    def __init__(self, hass: HomeAssistant, config_entry_id: str) -> None:
        """Initialize coordinator."""
        self._config_entry_id = config_entry_id
        self._config = hass.config_entries.async_get_entry(self._config_entry_id).data
        super().__init__(
            hass,
            _LOGGER,
            # Name of the data. For logging purposes.
            name=f"CSG Account {self._config[CONF_USERNAME]}",
            # Polling interval. Will only be polled if there are subscribers.
            update_interval=timedelta(
                seconds=self._config[CONF_SETTINGS][CONF_UPDATE_INTERVAL]
            ),
        )
        self._client: CSGClient | None = None
        self._this_day = None
        self._this_year = None
        self._this_month_ym = None
        self._last_year = None
        self._last_month_ym = None
        self._last_year_cache = {}
        self._today = None
        self._gathered_data = {}
        self._daily_corrections = {}

    async def _async_load_daily_corrections(self) -> None:
        """Load optional user-confirmed corrections before every refresh."""
        path = self.hass.config.path(CORRECTIONS_FILENAME)
        try:
            self._daily_corrections = await self.hass.async_add_executor_job(
                load_daily_corrections, path
            )
        except (OSError, ValueError) as err:
            self._daily_corrections = {}
            _LOGGER.error("Unable to load %s: %s", CORRECTIONS_FILENAME, err)

    def _prepare_month_source(
        self,
        account_number: str,
        source: str,
        total_kwh: float | str,
        by_day: list | str,
    ) -> tuple[float | str, list | str, list[str]]:
        """Apply confirmed corrections, then reject impossible API values."""
        applied_dates: list[str] = []
        if isinstance(by_day, list):
            by_day, applied_dates = apply_daily_corrections(
                by_day,
                self._daily_corrections.get(account_number, {}),
            )
            by_day = [
                {WF_ATTR_DATE: row[WF_ATTR_DATE], WF_ATTR_KWH: row[WF_ATTR_KWH]}
                for row in by_day
            ]
            if applied_dates:
                total_kwh = corrected_month_total(by_day)
                _LOGGER.warning(
                    "Applied confirmed daily corrections for account %s from %s: %s",
                    account_number,
                    source,
                    ", ".join(applied_dates),
                )

        validation_error = validate_month_data(total_kwh, by_day)
        if validation_error:
            _LOGGER.error(
                "Rejected invalid monthly consumption for account %s from %s: %s",
                account_number,
                source,
                validation_error,
            )
            return STATE_UNAVAILABLE, STATE_UNAVAILABLE, []
        return total_kwh, by_day, applied_dates

    async def _async_refresh_client(self):
        """Refresh the client, update the user data.
        It cannot re-login if the session is invalidated.
        """
        _LOGGER.debug("Refreshing client")
        self._client = await self.hass.async_add_executor_job(
            CSGClient.load,
            {
                CONF_AUTH_TOKEN: self._config[CONF_AUTH_TOKEN],
            },
        )
        logged_in = await self.hass.async_add_executor_job(
            self._client.verify_login,
        )
        if not logged_in:
            _LOGGER.warning(f"{self._config[CONF_USERNAME]}: Login expired")
            raise ConfigEntryAuthFailed("Login expired")

        _LOGGER.debug(f"{self._config[CONF_USERNAME]}: Session still valid")
        await self.hass.async_add_executor_job(self._client.initialize)

    async def _async_fetch(self, func: callable, *args, **kwargs) -> (bool, tuple):
        """Wrapper to fetch data from API. Return (success, result) with timeout.
        Also handle all exceptions here to avoid task group being cancelled.
        """
        try:
            async with async_timeout.timeout(SETTING_UPDATE_TIMEOUT):
                return True, await self.hass.async_add_executor_job(
                    func, *args, **kwargs
                )

        except asyncio.TimeoutError as err:
            _LOGGER.error("Timeout fetching data in function: %s", func.__name__)
            return False, (func.__name__, err)
        except NotLoggedIn as err:
            _LOGGER.error(
                "Session invalidated unexpectedly in function: %s", func.__name__
            )
            return False, (func.__name__, err)
        except CSGAPIError as err:
            _LOGGER.error(
                "Error fetching data in coordinator: API error, function %s, %s",
                func.__name__,
                err,
            )
            return False, (func.__name__, err)
        except Exception as err:  # pylint: disable=broad-except
            _LOGGER.error("Unexpected exception: %s", err)
            _LOGGER.error(traceback.format_exc())
            return False, (func.__name__, err)

    async def _async_update_bal_arr(self, account: CSGElectricityAccount):
        """Update balance and arrears"""
        success, result = await self._async_fetch(
            self._client.get_balance_and_arrears, account
        )
        if success:
            balance, arrears = result
            _LOGGER.debug(
                "Updated balance and arrears for account %s: %s",
                account.account_number,
                result,
            )
        else:
            balance, arrears = STATE_UNAVAILABLE, STATE_UNAVAILABLE
            _LOGGER.error(
                "Error updating balance and arrears for account %s: %s",
                account.account_number,
                result,
            )
        self._gathered_data[account.account_number][SUFFIX_BAL] = balance
        self._gathered_data[account.account_number][SUFFIX_ARR] = arrears

    async def _async_update_year_stats(
        self, account: CSGElectricityAccount, *, previous=False
    ):
        """Refresh bills; cache the preceding calendar year for at most one day."""
        year = self._last_year if previous else self._this_year
        cache_key = (account.account_number, year)
        cached = self._last_year_cache.get(cache_key)
        if previous and cached and cached[0] == self._today:
            success, result = True, cached[1]
        else:
            success, result = await self._async_fetch(
                self._client.get_year_month_stats, account, year
            )
            if previous and success:
                self._last_year_cache[cache_key] = (self._today, result)
        if success:
            cost, kwh, by_month = result
        else:
            cost, kwh, by_month = STATE_UNAVAILABLE, STATE_UNAVAILABLE, []
        attr = ATTR_KEY_LAST_YEAR_BY_MONTH if previous else ATTR_KEY_THIS_YEAR_BY_MONTH
        data = self._gathered_data[account.account_number]
        data[SUFFIX_LAST_YEAR_COST if previous else SUFFIX_THIS_YEAR_COST] = cost
        data[SUFFIX_LAST_YEAR_KWH if previous else SUFFIX_THIS_YEAR_KWH] = kwh
        data[attr] = {attr: by_month, "data_source": "annual_billing"}

    async def _async_update_month_usage(
        self, account: CSGElectricityAccount, *, previous=False
    ):
        """Refresh calendar energy, independent of bill availability."""
        year_month = self._last_month_ym if previous else self._this_month_ym
        attr = ATTR_KEY_LAST_MONTH_BY_DAY if previous else ATTR_KEY_THIS_MONTH_BY_DAY
        suffix = SUFFIX_LAST_MONTH_KWH if previous else SUFFIX_THIS_MONTH_KWH
        success, result = await self._async_fetch(
            self._client.get_month_daily_usage_detail, account, year_month
        )
        total, rows, corrections = STATE_UNAVAILABLE, [], []
        if success:
            total, rows, corrections = self._prepare_month_source(
                account.account_number, "electricity calendar", *result
            )
            # No reported days is absence, not evidence of zero consumption.
            if not isinstance(rows, list) or not rows:
                total, rows = STATE_UNAVAILABLE, []
            elif any(row[WF_ATTR_DATE] > self._today.isoformat() for row in rows):
                _LOGGER.error("Rejected future dated electricity calendar data")
                total, rows, corrections = STATE_UNAVAILABLE, [], []
        data = self._gathered_data[account.account_number]
        data[suffix] = total
        data[attr] = {
            attr: rows,
            "data_source": "electricity_calendar",
            "usage_month": f"{year_month[0]}-{year_month[1]:02d}",
            ATTR_KEY_LATEST_DAY_DATE: rows[-1][WF_ATTR_DATE] if rows else None,
            "reported_days": len(rows),
            ATTR_KEY_DATA_QUALITY: (
                "unavailable"
                if total == STATE_UNAVAILABLE
                else "corrected"
                if corrections
                else "api"
            ),
            ATTR_KEY_APPLIED_CORRECTIONS: corrections,
        }

    def _update_last_month_bill(self, account: CSGElectricityAccount):
        """Match only the previous calendar month's bill, including January rollover."""
        data = self._gathered_data[account.account_number]
        year, month = self._last_month_ym
        billing_month = f"{year}-{month:02d}"
        attr = (
            ATTR_KEY_THIS_YEAR_BY_MONTH
            if year == self._this_year
            else ATTR_KEY_LAST_YEAR_BY_MONTH
        )
        rows = data[attr][attr]
        matching = [
            row
            for row in rows
            if str(row.get(WF_ATTR_MONTH))
            in (billing_month, billing_month.replace("-", ""))
        ]
        bill = matching[0] if len(matching) == 1 else {}
        charge = bill.get(WF_ATTR_CHARGE)
        data[SUFFIX_LAST_MONTH_COST] = (
            charge if charge is not None else STATE_UNAVAILABLE
        )
        data[ATTR_KEY_LAST_MONTH_BILL] = {
            "billing_month": billing_month,
            "billing_kwh": bill.get(WF_ATTR_KWH),
            "data_source": "annual_billing",
        }

    def _update_latest_day(self, account: CSGElectricityAccount):
        """Derive latest and yesterday from actual reported dates, without extra calls."""
        data = self._gathered_data[account.account_number]
        rows = (
            data[ATTR_KEY_LAST_MONTH_BY_DAY][ATTR_KEY_LAST_MONTH_BY_DAY]
            + data[ATTR_KEY_THIS_MONTH_BY_DAY][ATTR_KEY_THIS_MONTH_BY_DAY]
        )
        rows.sort(key=lambda row: row[WF_ATTR_DATE])
        latest = rows[-1] if rows else {}
        data[SUFFIX_LATEST_DAY_KWH] = latest.get(WF_ATTR_KWH, STATE_UNAVAILABLE)
        data[ATTR_KEY_LATEST_DAY_DATE] = {
            ATTR_KEY_LATEST_DAY_DATE: latest.get(WF_ATTR_DATE),
            "data_source": "electricity_calendar",
        }
        yesterday = (self._today - timedelta(days=1)).isoformat()
        data[SUFFIX_YESTERDAY_KWH] = next(
            (row[WF_ATTR_KWH] for row in rows if row[WF_ATTR_DATE] == yesterday),
            STATE_UNAVAILABLE,
        )

    def _update_states(self):
        # CSG calendar days always use China time, independent of the HA host zone.
        self._today = datetime.datetime.now(ZoneInfo("Asia/Shanghai")).date()
        previous = self._today.replace(day=1) - timedelta(days=1)
        self._this_day = self._today.day
        self._this_year = self._today.year
        self._this_month_ym = (self._today.year, self._today.month)
        self._last_year = self._today.year - 1
        self._last_month_ym = (previous.year, previous.month)

    async def _async_update_account_data(self, account: CSGElectricityAccount):
        start_time = time.time()
        data = self._gathered_data[account.account_number]
        data.update({suffix: STATE_UNAVAILABLE for suffix in UNSUPPORTED_SUFFIXES})
        # Each source handles its own request failure. Programming errors must surface.
        await asyncio.gather(
            self._async_update_bal_arr(account),
            self._async_update_year_stats(account),
            self._async_update_year_stats(account, previous=True),
            self._async_update_month_usage(account),
            self._async_update_month_usage(account, previous=True),
        )
        self._update_last_month_bill(account)
        self._update_latest_day(account)
        _LOGGER.debug("Account update took %.2f seconds", time.time() - start_time)

    async def _async_update_data(self) -> dict[str, Any]:
        """Fetch data from API endpoint.

        This is the place to pre-process the data to lookup tables
        so entities can quickly look up their data.
        """
        self.update_interval = timedelta(
            seconds=self._config[CONF_SETTINGS][CONF_UPDATE_INTERVAL]
        )
        self._update_states()
        self._gathered_data = {}
        await self._async_load_daily_corrections()
        # _LOGGER.debug("Coordinator update interval: %d", self.update_interval.seconds)
        _LOGGER.debug("Coordinator update started")
        start_time = time.time()

        metering_point_data = {}
        config_entry_need_update = False
        await self._async_refresh_client()
        new_config = self._config.copy()
        for account_number, account_data in self._config[CONF_ELE_ACCOUNTS].items():
            self._gathered_data[account_number] = {}
            account = CSGElectricityAccount.load(account_data)
            # handling the addition of metering point number
            if not account.metering_point_number:
                if not metering_point_data:
                    ok, data = await self._async_fetch(
                        self._client.api_get_metering_point,
                        account.area_code,
                        account.ele_customer_id,
                    )
                    if ok:
                        metering_point_data = data
                if metering_point_data:
                    for mp in metering_point_data:
                        if mp["eleCustNumber"] == account.account_number:
                            config_entry_need_update = True
                            account.metering_point_number = mp[
                                JSON_KEY_METERING_POINT_NUMBER
                            ]
                            new_config[CONF_ELE_ACCOUNTS][account_number] = (
                                account.dump()
                            )
                            break

            await self._async_update_account_data(account)
        if config_entry_need_update:
            new_config[CONF_UPDATED_AT] = str(int(time.time() * 1000))
            self.hass.config_entries.async_update_entry(
                self.hass.config_entries.async_get_entry(self._config_entry_id),
                data=new_config,
            )
            _LOGGER.debug("Updated accounts with metering point number")
        _LOGGER.debug("Coordinator update took %s seconds", time.time() - start_time)
        self.hass.data[DOMAIN][self._config_entry_id][DATA_KEY_LAST_UPDATE_DAY] = (
            self._this_day
        )
        return self._gathered_data
