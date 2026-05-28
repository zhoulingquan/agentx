import csv
import io
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch

from powerbanana import cli


class PowerBananaCliTests(unittest.TestCase):
    def write_csv(self):
        handle = tempfile.NamedTemporaryFile("w", newline="", suffix=".csv", delete=False)
        with handle:
            writer = csv.DictWriter(handle, fieldnames=["channel", "visits", "orders"])
            writer.writeheader()
            writer.writerows(
                [
                    {"channel": "email", "visits": "100", "orders": "20"},
                    {"channel": "ads", "visits": "200", "orders": "30"},
                ]
            )
        return Path(handle.name)

    def test_logo_is_yellow_ascii_power_banana(self):
        output = cli.yellow_logo()

        self.assertIn("\033[33m", output)
        self.assertIn("POWER BANANA", output)
        self.assertTrue(output.endswith("\033[0m"))

    def test_interactive_mode_prompts_and_answers_until_exit(self):
        path = self.write_csv()
        user_input = iter([str(path), "Which channel has the highest conversion rate?", "q"])
        stdout = io.StringIO()

        with patch("builtins.input", lambda _prompt="": next(user_input)), redirect_stdout(stdout):
            exit_code = cli.main(["--interactive"])

        text = stdout.getvalue()
        self.assertEqual(exit_code, 0)
        self.assertIn("POWER BANANA", text)
        self.assertIn("email has the highest conversion_rate at 20.00%.", text)

    def test_single_run_mode_still_outputs_json(self):
        path = self.write_csv()
        stdout = io.StringIO()

        with redirect_stdout(stdout):
            exit_code = cli.main([str(path), "Which channel has the highest conversion rate?"])

        self.assertEqual(exit_code, 0)
        self.assertIn('"agent_name": "PowerBanana"', stdout.getvalue())
