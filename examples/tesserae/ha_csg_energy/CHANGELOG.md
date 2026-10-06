# Changelog

All notable changes to this widget are documented here, following [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## Unreleased

## 0.2.0 - 2026-10-06

### Changed

- Restore the original title and content styling; show latest day, current month, daily average and previous-month usage as four kWh figures, with the issued bill as secondary text. Show the month beside its heading and report the day count only once in the supporting line.

- Show current-month and daily electricity usage from the Home Assistant electricity calendar sensors, with the latest reported date and average usage per reported day.
- Show the previous calendar month's issued bill with its month. Prefer a month-identified bill sensor and fall back only to the matching historical monthly bill; no estimated current-month costs are displayed.
- Show the current daily average against the previous full-month daily average beneath the daily-average figure. Incomplete prior-month data or a zero denominator never produces a misleading percentage. Trend colours and configurable thresholds measure kWh.
- Replace cost and tariff fragment choices with usage trend and monthly billing fragments. Saved `cost_trend` and `ladder` fragments render their supported replacements; old cost metric and tariff options are ignored.
- Provide migration instructions for existing canvases using the supported usage and billing display.

### Removed

- Current-month cost, daily cost, and ladder tariff display and configuration.

### Fixed

- Missing numeric readings now remain unavailable rather than displaying as zero.
- Ignore stale cost-sensor daily arrays, invalid days, and readings outside the current/previous calendar months.
- Preserve chart gaps for missing days and include month numbers on trend dates across month boundaries.
- Do not interpret saved cost thresholds as usage thresholds or silently switch an unavailable selected account to another account.
