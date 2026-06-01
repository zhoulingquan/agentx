import csv
import io
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch

from powerbanana import cli
from powerbanana.models import VocabularySuggestion
from powerbanana.vocabulary import VocabularySuggestionRepository


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

    def write_region_revenue_csv(self, path: Path) -> None:
        path.write_text(
            "region,revenue\n"
            "north,500\n"
            "south,900\n",
            encoding="utf-8",
        )

    def write_pending_suggestion(self, store_path: Path) -> None:
        VocabularySuggestionRepository(store_path).save_pending(
            VocabularySuggestion(
                target_csv="config/analysis_terms.csv",
                kind="group_by",
                value="region",
                terms=["地区", "区域"],
                reason="missing_group_by_term",
                source="fake_llm",
                confidence=0.8,
            )
        )

    def write_terms_csv(self, path: Path) -> None:
        path.write_text(
            "kind,value,terms,aggregation,required_columns\n"
            "metric,revenue,revenue|收入,sum,region|revenue\n"
            "group_by,channel,channel|渠道,,\n"
            "rank_direction,highest,highest|最高,,\n",
            encoding="utf-8",
        )

    def fake_region_advisor(self):
        class FakeRegionAdvisor:
            provider = "test"
            model = "fake"
            temperature = 0.0
            max_tokens = 0

            def suggest(self, question, dataset_columns, analysis_terms):
                return VocabularySuggestion(
                    target_csv="config/analysis_terms.csv",
                    kind="group_by",
                    value="region",
                    terms=["地区", "区域"],
                    reason="test suggestion",
                    source="fake",
                    confidence=0.8,
                )

        return FakeRegionAdvisor()

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

    def test_no_args_defaults_to_interactive_mode(self):
        user_input = iter(["q"])
        stdout = io.StringIO()

        with patch("builtins.input", lambda _prompt="": next(user_input)), redirect_stdout(stdout):
            exit_code = cli.main([])

        self.assertEqual(exit_code, 0)
        self.assertIn("POWER BANANA", stdout.getvalue())

    def test_single_run_mode_still_outputs_json(self):
        path = self.write_csv()
        stdout = io.StringIO()

        with redirect_stdout(stdout):
            exit_code = cli.main([str(path), "Which channel has the highest conversion rate?"])

        self.assertEqual(exit_code, 0)
        self.assertIn('"agent_name": "PowerBanana"', stdout.getvalue())

    def test_dockerfile_starts_powerbanana_console_script(self):
        dockerfile = Path("Dockerfile").read_text(encoding="utf-8")

        self.assertIn("pip install", dockerfile)
        self.assertIn('CMD ["powerbanana"]', dockerfile)

    def test_vocab_list_prints_pending_suggestions(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            store_path = Path(tmpdir) / "vocabulary_suggestions.jsonl"
            self.write_pending_suggestion(store_path)
            stdout = io.StringIO()

            with redirect_stdout(stdout):
                exit_code = cli.main(["vocab", "list", "--store", str(store_path)])

            text = stdout.getvalue()
            self.assertEqual(exit_code, 0)
            self.assertIn("vocab_000001", text)
            self.assertIn("pending_user_approval", text)
            self.assertIn("group_by=region", text)

    def test_main_without_explicit_argv_dispatches_vocab_subcommands_from_sys_argv(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            store_path = Path(tmpdir) / "vocabulary_suggestions.jsonl"
            self.write_pending_suggestion(store_path)
            stdout = io.StringIO()

            with patch("sys.argv", ["powerbanana", "vocab", "list", "--store", str(store_path)]):
                with redirect_stdout(stdout):
                    exit_code = cli.main()

            self.assertEqual(exit_code, 0)
            self.assertIn("vocab_000001", stdout.getvalue())

    def test_vocab_approve_appends_terms_and_updates_status(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            store_path = Path(tmpdir) / "vocabulary_suggestions.jsonl"
            terms_path = Path(tmpdir) / "analysis_terms.csv"
            drafts_dir = Path(tmpdir) / "drafts"
            self.write_pending_suggestion(store_path)
            self.write_terms_csv(terms_path)
            stdout = io.StringIO()

            with redirect_stdout(stdout):
                exit_code = cli.main(
                    [
                        "vocab",
                        "approve",
                        "vocab_000001",
                        "--store",
                        str(store_path),
                        "--analysis-terms",
                        str(terms_path),
                        "--golden-drafts",
                        str(drafts_dir),
                        "--note",
                        "approved by test",
                    ]
                )

            self.assertEqual(exit_code, 0)
            text = stdout.getvalue()
            self.assertIn("approved vocab_000001", text)
            self.assertIn("validation=passed", text)
            self.assertIn("golden_case_draft=", text)
            self.assertIn("group_by,region,地区|区域,,", terms_path.read_text(encoding="utf-8"))
            record = VocabularySuggestionRepository(store_path).get_record("vocab_000001")
            self.assertEqual(record.status, "approved")
            self.assertTrue(Path(record.golden_case_draft_path).exists())

    def test_vocab_approve_dry_run_prints_csv_line_without_mutation(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            store_path = Path(tmpdir) / "vocabulary_suggestions.jsonl"
            terms_path = Path(tmpdir) / "analysis_terms.csv"
            self.write_pending_suggestion(store_path)
            self.write_terms_csv(terms_path)
            original = terms_path.read_text(encoding="utf-8")
            stdout = io.StringIO()

            with redirect_stdout(stdout):
                exit_code = cli.main(
                    [
                        "vocab",
                        "approve",
                        "vocab_000001",
                        "--dry-run",
                        "--store",
                        str(store_path),
                        "--analysis-terms",
                        str(terms_path),
                    ]
                )

            text = stdout.getvalue()
            self.assertEqual(exit_code, 0)
            self.assertIn("dry-run vocab_000001", text)
            self.assertIn("would append group_by,region,地区|区域,,", text)
            self.assertEqual(terms_path.read_text(encoding="utf-8"), original)
            self.assertEqual(VocabularySuggestionRepository(store_path).get_record("vocab_000001").status, "pending_user_approval")

    def test_vocab_suggest_dry_run_prints_candidate_without_recording(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            store_path = root / "vocabulary_suggestions.jsonl"
            terms_path = root / "analysis_terms.csv"
            self.write_terms_csv(terms_path)
            stdout = io.StringIO()

            with patch("powerbanana.cli.vocabulary_advisor_from_env", return_value=self.fake_region_advisor()):
                with redirect_stdout(stdout):
                    exit_code = cli.main(
                        [
                            "vocab",
                            "suggest",
                            "--question",
                            "哪个地区收入最高？",
                            "--columns",
                            "region,revenue",
                            "--analysis-terms",
                            str(terms_path),
                            "--store",
                            str(store_path),
                            "--dry-run",
                        ]
                    )

            text = stdout.getvalue()
            self.assertEqual(exit_code, 0)
            self.assertIn("dry-run suggestion", text)
            self.assertIn("group_by=region", text)
            self.assertIn("validation=passed", text)
            self.assertIn("would append group_by,region,地区|区域,,", text)
            self.assertFalse(store_path.exists())

    def test_vocab_suggest_can_read_columns_from_dataset_and_record_pending(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            store_path = root / "vocabulary_suggestions.jsonl"
            terms_path = root / "analysis_terms.csv"
            dataset_path = root / "region_revenue.csv"
            self.write_terms_csv(terms_path)
            self.write_region_revenue_csv(dataset_path)
            stdout = io.StringIO()

            with patch("powerbanana.cli.vocabulary_advisor_from_env", return_value=self.fake_region_advisor()):
                with redirect_stdout(stdout):
                    exit_code = cli.main(
                        [
                            "vocab",
                            "suggest",
                            "--question",
                            "哪个地区收入最高？",
                            "--dataset",
                            str(dataset_path),
                            "--analysis-terms",
                            str(terms_path),
                            "--store",
                            str(store_path),
                        ]
                    )

            text = stdout.getvalue()
            self.assertEqual(exit_code, 0)
            self.assertIn("recorded vocab_000001", text)
            record = VocabularySuggestionRepository(store_path).get_record("vocab_000001")
            self.assertEqual(record.suggestion.value, "region")
            self.assertEqual(record.status, "pending_user_approval")

    def test_vocab_reject_updates_status_without_csv_mutation(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            store_path = Path(tmpdir) / "vocabulary_suggestions.jsonl"
            terms_path = Path(tmpdir) / "analysis_terms.csv"
            self.write_pending_suggestion(store_path)
            self.write_terms_csv(terms_path)
            original = terms_path.read_text(encoding="utf-8")
            stdout = io.StringIO()

            with redirect_stdout(stdout):
                exit_code = cli.main(
                    [
                        "vocab",
                        "reject",
                        "vocab_000001",
                        "--store",
                        str(store_path),
                        "--note",
                        "not useful",
                    ]
                )

            self.assertEqual(exit_code, 0)
            self.assertIn("rejected vocab_000001", stdout.getvalue())
            self.assertEqual(terms_path.read_text(encoding="utf-8"), original)
            self.assertEqual(VocabularySuggestionRepository(store_path).get_record("vocab_000001").status, "rejected")

    def test_vocab_promote_golden_creates_valid_planner_case(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            store_path = root / "vocabulary_suggestions.jsonl"
            terms_path = root / "analysis_terms.csv"
            drafts_dir = root / "drafts"
            cases_dir = root / "planner_cases"
            self.write_pending_suggestion(store_path)
            self.write_terms_csv(terms_path)
            stdout = io.StringIO()
            with redirect_stdout(stdout):
                approve_exit = cli.main(
                    [
                        "vocab",
                        "approve",
                        "vocab_000001",
                        "--store",
                        str(store_path),
                        "--analysis-terms",
                        str(terms_path),
                        "--golden-drafts",
                        str(drafts_dir),
                    ]
                )

            self.assertEqual(approve_exit, 0)
            stdout = io.StringIO()
            with redirect_stdout(stdout):
                promote_exit = cli.main(
                    [
                        "vocab",
                        "promote-golden",
                        "vocab_000001",
                        "--store",
                        str(store_path),
                        "--planner-cases",
                        str(cases_dir),
                        "--analysis-terms",
                        str(terms_path),
                        "--question",
                        "哪个地区收入最高？",
                        "--matched-signal",
                        "收入",
                        "--expected-metric",
                        "revenue",
                    ]
                )

            text = stdout.getvalue()
            self.assertEqual(promote_exit, 0)
            self.assertIn("promoted planner golden case", text)
            self.assertTrue((cases_dir / "region_group_by_metric_analysis.json").exists())

    def test_vocab_promote_e2e_golden_creates_valid_golden_case(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            store_path = root / "vocabulary_suggestions.jsonl"
            terms_path = root / "analysis_terms.csv"
            drafts_dir = root / "drafts"
            cases_dir = root / "golden_cases"
            dataset_path = root / "region_revenue_source.csv"
            self.write_pending_suggestion(store_path)
            self.write_terms_csv(terms_path)
            self.write_region_revenue_csv(dataset_path)
            stdout = io.StringIO()
            with redirect_stdout(stdout):
                approve_exit = cli.main(
                    [
                        "vocab",
                        "approve",
                        "vocab_000001",
                        "--store",
                        str(store_path),
                        "--analysis-terms",
                        str(terms_path),
                        "--golden-drafts",
                        str(drafts_dir),
                    ]
                )

            self.assertEqual(approve_exit, 0)
            stdout = io.StringIO()
            with redirect_stdout(stdout):
                promote_exit = cli.main(
                    [
                        "vocab",
                        "promote-e2e-golden",
                        "vocab_000001",
                        "--store",
                        str(store_path),
                        "--golden-cases",
                        str(cases_dir),
                        "--analysis-terms",
                        str(terms_path),
                        "--dataset",
                        str(dataset_path),
                        "--question",
                        "哪个地区收入最高？",
                        "--expected-metric",
                        "revenue",
                    ]
                )

            text = stdout.getvalue()
            self.assertEqual(promote_exit, 0)
            self.assertIn("promoted e2e golden case", text)
            self.assertTrue((cases_dir / "region_group_by_metric_question.json").exists())
            self.assertTrue((cases_dir / "region_group_by_metric_question.csv").exists())
