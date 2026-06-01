import tempfile
import unittest
from pathlib import Path

from powerbanana.analysis_request import AnalysisRequestParser, AnalysisTermStore, default_analysis_terms


class AnalysisRequestTests(unittest.TestCase):
    def test_default_terms_extract_revenue_request(self):
        request = AnalysisRequestParser(default_analysis_terms()).parse(
            "Which channel has the highest revenue?"
        )

        self.assertEqual(request.metric, "revenue")
        self.assertEqual(request.group_by, "channel")
        self.assertEqual(request.aggregation, "sum")
        self.assertEqual(request.rank_direction, "highest")
        self.assertEqual(request.required_columns, ["channel", "revenue"])

    def test_default_terms_extract_lowest_orders_request(self):
        request = AnalysisRequestParser(default_analysis_terms()).parse(
            "Which channel has the fewest orders?"
        )

        self.assertEqual(request.metric, "orders")
        self.assertEqual(request.group_by, "channel")
        self.assertEqual(request.aggregation, "sum")
        self.assertEqual(request.rank_direction, "lowest")
        self.assertEqual(request.required_columns, ["channel", "orders"])

    def test_strict_parse_leaves_unknown_group_by_for_vocabulary_suggestion(self):
        parser = AnalysisRequestParser(default_analysis_terms())

        request = parser.parse_optional(
            "Which region has the highest revenue?",
            allow_default_group_by=False,
        )

        self.assertIsNone(request)

    def test_user_csv_terms_can_extend_metric_vocabulary(self):
        handle = tempfile.NamedTemporaryFile("w", suffix=".csv", delete=False, encoding="utf-8", newline="")
        with handle:
            handle.write(
                "kind,value,terms,aggregation,required_columns\n"
                "metric,revenue,net sales|revenue,sum,channel|revenue\n"
                "group_by,channel,channel,\n"
                "rank_direction,highest,highest|top,\n"
            )

        terms = AnalysisTermStore().load_csv(Path(handle.name))
        request = AnalysisRequestParser(terms).parse("Top channel by net sales")

        self.assertEqual(request.metric, "revenue")
        self.assertEqual(request.rank_direction, "highest")


if __name__ == "__main__":
    unittest.main()
