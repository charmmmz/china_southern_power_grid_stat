# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## [Unreleased]

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
