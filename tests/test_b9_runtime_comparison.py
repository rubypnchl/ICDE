import unittest
from pathlib import Path
import importlib.util

src = Path(__file__).resolve().parents[1] / 'src/b9_runtime_comparison.py'
spec = importlib.util.spec_from_file_location('b9_runtime_comparison', src)
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)

class B9Tests(unittest.TestCase):
    def setUp(self):
        self.rows = [{'v': '1'} for _ in range(4)] + [{'v': '0'}]
        self.good = lambda r: 'satisfied' if r['v'] == '1' else 'violated'

    def test_p95(self):
        self.assertAlmostEqual(m.percentile_linear([1,2,3,4,5], .95), 4.8)

    def test_p95_empty_refused(self):
        with self.assertRaises(m.BenchmarkError): m.percentile_linear([], .95)

    def test_p95_invalid_refused(self):
        with self.assertRaises(m.BenchmarkError): m.percentile_linear([1,-1,2], .95)

    def test_parity_exact_match(self):
        want = {'satisfied':4,'violated':1,'not_applicable':0,'abstained':0}
        self.assertEqual(m.ensure_row_parity(self.rows, self.good, self.good, want), want)

    def test_parity_detects_one_row_difference(self):
        other = lambda r: 'satisfied'
        with self.assertRaisesRegex(m.BenchmarkError,'row index 4'):
            m.ensure_row_parity(self.rows, self.good, other, {'satisfied':4,'violated':1})

    def test_parity_detects_baseline_drift(self):
        with self.assertRaisesRegex(m.BenchmarkError, 'Counts drifted'):
            m.ensure_row_parity(self.rows, self.good, self.good, {'satisfied':5})

    def test_invalid_status_refused(self):
        with self.assertRaises(m.BenchmarkError): m.count_statuses(self.rows, lambda _: 'gold')

    def test_alternating_order_and_repeats(self):
        result=m.repeated_paired_timing(self.rows,{'a':self.good,'b':self.good},repetitions=5,seed=1)
        self.assertEqual(result['order_per_repetition'][0], ['a','b'])
        self.assertEqual(result['order_per_repetition'][1], ['b','a'])
        self.assertEqual(len(result['methods']['a']['elapsed_seconds_each_run']), 5)
        self.assertEqual(result['status_counts_every_run']['violated'], 1)

    def test_timing_detects_drift(self):
        state = {'n':0}
        def flipping(row):
            state['n'] += 1
            return 'satisfied' if state['n'] < 6 else 'violated'
        with self.assertRaises(m.BenchmarkError):
            m.repeated_paired_timing(self.rows, {'a':self.good,'b':flipping}, repetitions=5,seed=1)

    def test_out_of_range_repetitions(self):
        with self.assertRaises(m.BenchmarkError):
            m.repeated_paired_timing(self.rows, {'a':self.good,'b':self.good}, repetitions=2,seed=1)

if __name__=='__main__': unittest.main()
