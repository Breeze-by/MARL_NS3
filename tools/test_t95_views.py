"""T95 boundary, censoring and local-union checks; no ROS nodes or simulator."""
import argparse
from contextlib import redirect_stdout
import io
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
import unittest
from unittest.mock import patch
import numpy as np
from analyze_t95_views import View, analyze, union_latest


def measurement(coverage, valid=True):
    return dict(coverage=coverage, map_quality_valid=valid, map_quality_warnings=[])


class T95ViewsTests(unittest.TestCase):
    def test_observation_time_not_header_time(self):
        view = View('central', 10., 190., 180.)
        view.observe(20., measurement(.96), [dict(header_stamp_sim=1.)])
        self.assertEqual(view.summary()['T95_sim_s'], 10.)

    def test_latest_baseline_and_quality_gate(self):
        view = View('R', 10., 190., 180.)
        view.observe(8., measurement(.97), [])
        view.observe(9., measurement(.50), [])
        view.observe(11., measurement(.99, False), [])
        view.observe(12., measurement(.95), [])
        self.assertEqual(view.summary()['T95_sim_s'], 2.)
        self.assertEqual(view.rows()[0]['observation_sim'], 9.)
        self.assertEqual(view.rows()[0]['elapsed_sim_s'], 0.)

    def test_initially_complete_and_missing_sources(self):
        view = View('local', 10., 190., 180.)
        view.observe(9., measurement(.96), [])
        self.assertEqual(view.summary()['T95_sim_s'], 0.)
        self.assertEqual(view.summary(['tb3'])['status'], 'missing_data')
        self.assertIsNone(view.summary(['tb3'])['T95_sim_s'])

    def test_unreached_budget_and_early_failure_not_imputed(self):
        for end, status in ((190., 'not_reached_within_budget'), (25., 'not_reached_early_stop')):
            view = View('R', 10., end, 180.)
            view.observe(12., measurement(.94), [])
            view.observe(end + .1, measurement(1.), [])
            self.assertEqual(view.summary()['status'], status)
            self.assertIsNone(view.summary()['T95_sim_s'])
            self.assertFalse(view.summary()['task_coverage_complete'])
        self.assertEqual(View('C', 10., 190., 180.).summary()['status'], 'missing_data')

    def test_latest_union_and_free_precedence(self):
        samples = {'tb1': np.array([[0, -1, 100]]), 'tb2': np.array([[100, 0, -1]])}
        self.assertEqual(union_latest(samples).tolist(), [[0, 0, 100]])
        samples['tb1'] = np.array([[-1, -1, 100]])
        self.assertEqual(union_latest(samples).tolist(), [[100, 0, 100]])

    def test_missing_central_callback_clock_is_not_header_fallback(self):
        with TemporaryDirectory() as temporary:
            case = Path(temporary)
            (case / 'events.jsonl').write_text(json.dumps(dict(kind='exploration_command', sim=10.))
                                             + '\n' + json.dumps(dict(kind='smoke_bound', sim=190.)))
            (case / 'result.json').write_text(json.dumps(dict(error=None, run_integrity=True)))
            capture = case / 'central-map-capture'
            capture.mkdir()
            (capture / 'index.json').write_text(json.dumps(dict(samples=[dict(
                source_stamp_ns=20_000_000_000, last_observed_R_clock_ns=21_000_000_000)])))
            args = argparse.Namespace(case=case, positions='0,0;0,0;0,0', world=None, assets=None,
                                      budget_s=180., central_capture=None, output=case / 'output')
            reference = SimpleNamespace(reference_free=np.ones((1, 1), dtype=bool), resolution=1.)
            with patch('analyze_t95_views.load_reference', return_value=(reference, [0] * 4)), \
                 patch('analyze_t95_views.map_records', return_value=iter(())), redirect_stdout(io.StringIO()):
                analyze(args)
            central = json.loads((args.output / 'result.json').read_text())['views']['central_merged']
            self.assertEqual(central['status'], 'missing_data')
            self.assertEqual(central['missing_sources'], ['capture_node_sim_ns'])
            self.assertIsNone(central['T95_sim_s'])


if __name__ == '__main__':
    unittest.main()
