"""Unit tests for the metrics-only read-only benchmark helper."""
import unittest
from scripts.benchmark_nhanes_verification import describe_times, validate_outcome, BenchmarkError


class RuntimeBenchmarkTests(unittest.TestCase):
    def test_nearest_rank_and_throughput(self):
        x = describe_times([0.4, 0.1, 0.5, 0.3, 0.2], 100)
        self.assertEqual(x['median_seconds'], 0.3)
        self.assertEqual(x['p95_nearest_rank_seconds'], 0.5)
        self.assertEqual(x['median_evaluated_checks_per_second'], 333.33)
        self.assertEqual(x['repetitions'], 5)

    def test_rejects_invalid_durations(self):
        for times, eligible in [([], 10), ([0.0], 10), ([float('nan')], 10), ([0.2], 0)]:
            with self.subTest(times=times, eligible=eligible), self.assertRaises(BenchmarkError):
                describe_times(times, eligible)

    def test_validates_original_outcomes(self):
        expected = {'record_count': 100, 'evaluated_records': 80, 'b3_counts': {'satisfied': 70, 'violated': 10}}
        actual = {**expected, 'pair_id': 'PAIR1', 'A': 'admit', 'B': 'admit', 'C': 'abstain', 'b4_compiler_calls': 1}
        validate_outcome(actual, expected, 'PAIR1')
        with self.assertRaises(BenchmarkError):
            validate_outcome({**actual, 'evaluated_records': 81}, expected, 'PAIR1')
        with self.assertRaises(BenchmarkError):
            validate_outcome({**actual, 'C': 'admit'}, expected, 'PAIR1')


if __name__ == '__main__':
    unittest.main()
