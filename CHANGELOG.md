# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## [Unreleased]

### Fixed

- Restore daily and monthly energy readings using the electricity calendar when legacy daily endpoints return no data.
- Read the previous calendar month's cost from its settled bill, including across January; keep calendar and billed kWh separate with explicit dates and sources.
- Publish unavailable fields immediately instead of retaining stale values or reporting a healthy source as available for every sensor.
- Reject duplicate, out-of-month, future or invalid calendar data; preserve genuine zero readings and user-confirmed energy corrections.

### Changed

- Stop polling daily cost, ladder and dedicated yesterday endpoints. Existing unsupported entities retain their history as unavailable; new installations disable them by default.
- Keep previous-month readings updating after day 3, cache previous-year bills for no more than one day, and bound network requests with timeouts.
- Expose calendar coverage dates and the previous bill's month and billed consumption for accurate dashboards; missing values are never estimated.

## [1.2.1] - 2026-08-23

### Fixed

- Restore the integration options flow on newer Home Assistant versions where `OptionsFlow.config_entry` is read-only.
- Reject impossible negative monthly or daily consumption returned by China Southern Power Grid instead of publishing it to Home Assistant.
- Prevent rejected cost-detail rows from being merged back into otherwise valid usage data.
- Select the daily detail source containing the newest settlement date instead of treating the largest monthly total as the newest response.
- Support user-confirmed daily corrections from `/config/china_southern_power_grid_stat_corrections.json` and expose applied correction dates on monthly sensor attributes.

### Changed

- Point installation and documentation links to the maintained fork.

[Unreleased]: https://github.com/charmmmz/china_southern_power_grid_stat/compare/v1.2.1...HEAD
[1.2.1]: https://github.com/charmmmz/china_southern_power_grid_stat/compare/v1.2.0...v1.2.1
