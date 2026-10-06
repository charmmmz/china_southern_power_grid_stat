from __future__ import annotations

import importlib.util
import json
import unittest
from datetime import date
from pathlib import Path

PLUGIN_ROOT = Path(__file__).resolve().parents[1]
PREFIX = 'sensor.csgaccount_11112222_33334444'


def load_server():
    spec = importlib.util.spec_from_file_location('ha_csg_energy_server', PLUGIN_ROOT / 'server.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    module._today = lambda: date(2026, 10, 4)
    return module


def state(suffix, value, **attrs):
    return {'entity_id': f'{PREFIX}_{suffix}', 'state': str(value), 'attributes': attrs}


class FakeCore:
    def __init__(self, states):
        self.states = states

    def get_states(self):
        return self.states

    def coerce_error(self, err):
        return str(err)


def fixture():
    current = [{'date': '2026-10-01', 'kwh': 16.85}, {'date': '2026-10-02', 'kwh': 23.12}, {'date': '2026-10-03', 'kwh': 25.81}]
    previous = [{'date': '2026-09-01', 'kwh': 10}, {'date': '2026-09-02', 'kwh': 20}, {'date': '2026-09-03', 'kwh': 30}, {'date': '2026-09-30', 'kwh': 15}]
    return [state('this_month_total_usage', 65.78, this_month_by_day=current),
            state('last_month_total_usage', 515.12, last_month_by_day=previous),
            state('last_month_total_cost', 354.13, billing_month='2026-09', billing_kwh=515),
            state('latest_day_kwh', 25.81, latest_day_date='2026-10-03'),
            state('this_month_total_cost', 'unavailable', this_month_by_day=[{'date': '2026-10-03', 'charge': 99, 'kwh': 999}]),
            state('latest_day_cost', 'unavailable'), state('current_ladder', 2),
            state('this_year_total_usage', 100, this_year_by_month=[{'month': '2026-09', 'charge': 354.13, 'kwh': 515}]),
            state('balance', 0), state('arrears', 354.13)]


class WidgetTests(unittest.TestCase):
    def fetch(self, states=None, options=None):
        server = load_server()
        server._core = lambda: FakeCore(fixture() if states is None else states)
        return server.fetch(options or {}, {}, ctx={})

    def test_usage_and_issued_bill_from_separate_sources(self):
        data = self.fetch()
        self.assertEqual(data['latest'], {'date': '2026-10-03', 'kwh': 25.81})
        self.assertEqual(data['month']['total_kwh'], 65.78)
        self.assertEqual(data['month']['average_daily_kwh'], 21.93)
        self.assertEqual(data['previous_month']['total_cost'], 354.13)
        self.assertEqual(data['previous_month']['total_kwh'], 515.12)
        self.assertNotIn('total_cost', data['month'])
        self.assertNotIn('ladder', data)
        self.assertNotIn('charge', data['latest'])
        self.assertEqual(data['billing']['balance'], 0)

    def test_stale_cost_arrays_are_never_used(self):
        rows = fixture()
        rows[0]['attributes'] = {}
        data = self.fetch(rows)
        self.assertEqual(data['current_month_days'], [])
        self.assertEqual(data['latest']['kwh'], 25.81)
        self.assertNotIn('999', json.dumps(data))

    def test_missing_bill_with_stale_month_is_not_a_zero_or_old_bill(self):
        rows = fixture()
        rows[2]['attributes']['billing_month'] = '2026-08'
        rows[7]['attributes'] = {}
        data = self.fetch(rows)
        self.assertIsNone(data['previous_month']['total_cost'])
        self.assertEqual(data['previous_month']['billing_month'], '')

    def test_year_bill_can_recover_old_sensor_but_never_estimates(self):
        rows = fixture()
        rows[2]['state'] = '-0.35'
        rows[2]['attributes'] = {}
        self.assertEqual(self.fetch(rows)['previous_month']['total_cost'], 354.13)

    def test_comparison_matches_day_numbers_despite_gaps(self):
        rows = fixture()
        rows[0]['attributes']['this_month_by_day'].pop(1)
        comp = self.fetch(rows)['month']['comparison']
        self.assertEqual(comp['days'], 2)
        self.assertEqual(comp['current_kwh'], 42.66)
        self.assertEqual(comp['previous_kwh'], 40)
        self.assertEqual(comp['delta_pct'], 6.6)

    def test_daily_average_uses_the_entire_previous_month(self):
        rows = fixture()
        rows[1]['attributes']['last_month_by_day'] = [
            {'date': f'2026-09-{day:02d}', 'kwh': 22.12 if day == 30 else 17}
            for day in range(1, 31)
        ]
        data = self.fetch(rows)
        self.assertEqual(data['month']['average_comparison'], {
            'current_daily_kwh': 21.93, 'previous_daily_kwh': 17.17, 'delta_pct': 27.7,
        })
        self.assertEqual(data['previous_month']['average_daily_kwh'], 17.17)

    def test_incomplete_previous_month_has_no_average_comparison(self):
        comparison = self.fetch()['month']['average_comparison']
        self.assertEqual(comparison['current_daily_kwh'], 21.93)
        self.assertIsNone(comparison['previous_daily_kwh'])
        self.assertIsNone(comparison['delta_pct'])

    def test_zero_previous_average_is_not_divided_or_missing(self):
        rows = fixture()
        rows[1]['attributes']['last_month_by_day'] = [
            {'date': f'2026-09-{day:02d}', 'kwh': 0} for day in range(1, 31)
        ]
        comparison = self.fetch(rows)['month']['average_comparison']
        self.assertEqual(comparison['previous_daily_kwh'], 0)
        self.assertIsNone(comparison['delta_pct'])

    def test_zero_kwh_remains_zero_in_latest_fallback(self):
        rows = fixture()
        rows[3]['state'] = '0'
        rows[3]['attributes']['latest_day_date'] = '2026-10-04'
        data = self.fetch(rows)
        self.assertEqual(data['latest']['kwh'], 0)

    def test_invalid_missing_negative_and_wrong_month_rows_are_omitted(self):
        rows = fixture()
        rows[0]['attributes']['this_month_by_day'] += [
            {'date': '2026-10-32', 'kwh': 5}, {'date': '2026-10-04', 'kwh': None},
            {'date': '2026-10-04', 'kwh': -1}, {'date': '2026-09-02', 'kwh': 55},
            {'date': '2026-10-05', 'kwh': 55}]
        self.assertEqual(len(self.fetch(rows)['current_month_days']), 3)

    def test_window_is_days_not_record_count(self):
        data = self.fetch(options={'window': '7'})
        self.assertEqual([r['date'] for r in data['series']], ['2026-09-30', '2026-10-01', '2026-10-02', '2026-10-03'])

    def test_legacy_cost_thresholds_not_reused_for_energy(self):
        data = self.fetch(options={'metric': 'cost', 'threshold_mode': 'manual', 'low_threshold': 999, 'high_threshold': 9999})
        self.assertEqual(data['thresholds']['mode'], 'auto')
        self.assertLess(data['thresholds']['high'], 50)
        self.assertEqual(data['thresholds']['unit'], 'kWh')

    def test_explicit_energy_thresholds(self):
        data = self.fetch(options={'threshold_mode': 'manual', 'low_kwh_threshold': 8, 'high_kwh_threshold': 20})
        self.assertEqual(data['thresholds'], {'mode': 'manual', 'low': 8.0, 'high': 20.0, 'unit': 'kWh'})

    def test_masking_and_invalid_selected_account(self):
        self.assertNotIn('11112222', json.dumps(self.fetch()))
        self.assertEqual(self.fetch()['account_label'], 'CSG •••• 4444')
        self.assertIn('error', self.fetch(options={'account': 'missing'}))

    def test_no_accounts(self):
        self.assertTrue(self.fetch([])['empty'])

    def test_options_and_schema_only_advertise_supported_features(self):
        manifest = json.loads((PLUGIN_ROOT / 'plugin.json').read_text())
        names = {o['name'] for o in manifest['cell_options']}
        self.assertFalse(names & {'metric', 'show_ladder', 'low_threshold', 'high_threshold'})
        self.assertEqual([f['id'] for f in manifest['fragments']], ['full', 'summary', 'trend', 'billing'])
        self.assertNotIn('requires', manifest)


if __name__ == '__main__':
    unittest.main()
