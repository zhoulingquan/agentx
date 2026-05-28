import unittest
from pathlib import Path

from powerbanana.evals import PlannerGoldenCaseRunner


class PlannerGoldenCaseTests(unittest.TestCase):
    def test_planner_golden_cases_pass(self):
        summary = PlannerGoldenCaseRunner(Path("evals/planner_cases")).run_all()

        self.assertGreaterEqual(summary.total, 10)
        self.assertEqual(summary.failed, 0)
        self.assertEqual(summary.passed, summary.total)


if __name__ == "__main__":
    unittest.main()
