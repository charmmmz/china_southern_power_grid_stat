# Home Assistant · China Southern Grid

Version 0.2.0 is distributed with the HA integration v1.3.0 release. The manifest contains synthetic demonstration data, never an electricity account number or captured household readings. Requires the repaired integration (v1.3.0+) and an existing Tesserae `ha_core` connection.

The widget reads the configured `ha_core` connection. Current-month usage and daily trends come from `this_month_total_usage.attributes.this_month_by_day`; previous daily usage comes from `last_month_total_usage.attributes.last_month_by_day`. Each row is `{date, kwh}`. Latest readings carry their actual reported date; averages use reported days. The daily-average card compares the current reported-day average with the previous full calendar-month average. The previous month must have every daily row; otherwise the comparison is withheld. A zero prior average is displayed but has no percentage change. The old matching-day comparison remains in the data payload for existing bindings.

The previous month's issued amount comes from `last_month_total_cost` only when `billing_month` matches the previous calendar month, or from its matching `this_year_by_month` bill. Calendar usage and billed usage can differ slightly due to rounding; the four main figures are calendar kWh: latest day, current month, daily average, and previous month. The issued bill is a smaller secondary line under previous-month usage. No amount is estimated, and current-month costs, daily costs, and tariff tiers are unsupported.

Fragments: `full`, `summary`, `trend`, `billing`. Old `cost_trend` and `ladder` fragments remain render aliases for `trend` and `billing`. The old `metric`, `show_ladder`, `low_threshold`, and `high_threshold` options no longer affect output. Manual usage thresholds use `low_kwh_threshold` / `high_kwh_threshold` in kWh. Missing values display as unavailable, never zero.

## Validation and deployment

Run `python3 -m unittest discover -s tests` and `node --test tests/test_client.mjs`. Copy the three widget files into the Studio workspace, lint, and register the existing `ha_csg_energy` widget. Registration hot reloads the widget without restarting Tesserae. Preserve a backup of the installed widget and affected canvases first.

Migrate the energy elements in your existing canvases: replace `ENERGY//COST` with `ENERGY//USAGE`; remove obsolete cost, tariff, and cost-threshold options; retain account, usage-window, comparison, and layout choices. Re-probe live data, render the affected pages, and check render reports. Registration and canvas updates do not explicitly push a physical display; displays on a normal refresh schedule may later consume the updated pages.

The module preserves the original amber title rail, warm paper surfaces, ruled metric row, serif display figures, and shaded usage chart.
