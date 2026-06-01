import json
import tempfile
import unittest
from pathlib import Path

from powerbanana.analysis_request import default_analysis_terms
from powerbanana.agent import PowerBananaAgent
from powerbanana.llm import vocabulary_advisor_from_env
from powerbanana.models import VocabularySuggestion
from powerbanana.llm_vocabulary import JsonLLMVocabularyAdvisor, OpenAIResponsesJsonClient
from powerbanana.vocabulary import NullVocabularyAdvisor


class FakeHttpResponse:
    def __init__(self, payload):
        self.payload = payload

    def __enter__(self):
        return self

    def __exit__(self, _exc_type, _exc, _traceback):
        return False

    def read(self):
        return json.dumps(self.payload).encode("utf-8")


class FakeJsonClient:
    def __init__(self, payload=None, error: Exception | None = None):
        self.payload = payload or {}
        self.error = error
        self.calls = []

    def complete_json(self, **kwargs):
        self.calls.append(kwargs)
        if self.error is not None:
            raise self.error
        return self.payload


class JsonLLMVocabularyAdvisorTests(unittest.TestCase):
    def test_json_advisor_converts_structured_payload_to_pending_suggestion(self):
        client = FakeJsonClient(
            {
                "should_suggest": True,
                "suggestion": {
                    "kind": "group_by",
                    "value": "region",
                    "terms": ["地区", "区域"],
                    "reason": "The question asks by region and the dataset has a region column.",
                    "confidence": 0.82,
                },
            }
        )
        advisor = JsonLLMVocabularyAdvisor(client=client, model="test-model")

        suggestion = advisor.suggest("哪个地区收入最高？", ["region", "revenue"], default_analysis_terms())

        self.assertIsNotNone(suggestion)
        self.assertEqual(suggestion.target_csv, "config/analysis_terms.csv")
        self.assertEqual(suggestion.kind, "group_by")
        self.assertEqual(suggestion.value, "region")
        self.assertEqual(suggestion.terms, ["地区", "区域"])
        self.assertEqual(suggestion.source, "llm_json_advisor")
        self.assertEqual(suggestion.status, "pending_user_approval")
        self.assertEqual(suggestion.confidence, 0.82)
        self.assertEqual(client.calls[0]["model"], "test-model")
        self.assertEqual(client.calls[0]["user_payload"]["question"], "哪个地区收入最高？")
        self.assertIn("region", client.calls[0]["user_payload"]["dataset_columns"])
        self.assertIn("group_by", client.calls[0]["schema"]["properties"]["suggestion"]["properties"]["kind"]["enum"])

    def test_json_advisor_returns_none_when_model_declines_to_suggest(self):
        client = FakeJsonClient({"should_suggest": False, "suggestion": None})
        advisor = JsonLLMVocabularyAdvisor(client=client, model="test-model")

        suggestion = advisor.suggest("哪个地区收入最高？", ["region", "revenue"], default_analysis_terms())

        self.assertIsNone(suggestion)

    def test_json_advisor_returns_none_for_incomplete_payload(self):
        client = FakeJsonClient({"should_suggest": True, "suggestion": {"kind": "group_by", "value": "region"}})
        advisor = JsonLLMVocabularyAdvisor(client=client, model="test-model")

        suggestion = advisor.suggest("哪个地区收入最高？", ["region", "revenue"], default_analysis_terms())

        self.assertIsNone(suggestion)

    def test_json_advisor_returns_none_when_client_fails(self):
        client = FakeJsonClient(error=RuntimeError("network down"))
        advisor = JsonLLMVocabularyAdvisor(client=client, model="test-model")

        suggestion = advisor.suggest("哪个地区收入最高？", ["region", "revenue"], default_analysis_terms())

        self.assertIsNone(suggestion)


class VocabularyAdvisorEnvTests(unittest.TestCase):
    def test_env_factory_is_disabled_by_default(self):
        advisor = vocabulary_advisor_from_env({})

        self.assertIsInstance(advisor, NullVocabularyAdvisor)

    def test_env_factory_requires_openai_api_key(self):
        with self.assertRaises(ValueError):
            vocabulary_advisor_from_env({"POWERBANANA_VOCAB_ADVISOR": "openai"})

    def test_env_factory_builds_openai_json_advisor(self):
        advisor = vocabulary_advisor_from_env(
            {
                "POWERBANANA_VOCAB_ADVISOR": "openai",
                "OPENAI_API_KEY": "test-key",
                "POWERBANANA_VOCAB_MODEL": "test-model",
                "POWERBANANA_VOCAB_BASE_URL": "https://example.test/v1",
            }
        )

        self.assertIsInstance(advisor, JsonLLMVocabularyAdvisor)
        self.assertEqual(advisor.model, "test-model")


class OpenAIResponsesJsonClientTests(unittest.TestCase):
    def test_client_posts_structured_output_request_and_parses_json_text(self):
        calls = {}

        def fake_urlopen(request, timeout):
            calls["url"] = request.full_url
            calls["timeout"] = timeout
            calls["body"] = json.loads(request.data.decode("utf-8"))
            return FakeHttpResponse({"output_text": "{\"should_suggest\": false, \"suggestion\": {}}"})

        client = OpenAIResponsesJsonClient(
            api_key="test-key",
            base_url="https://example.test/v1",
            timeout_seconds=12,
            urlopen=fake_urlopen,
        )

        result = client.complete_json(
            system_prompt="Return JSON.",
            user_payload={"question": "哪个地区收入最高？"},
            schema={"type": "object"},
            model="test-model",
            temperature=0.0,
            max_tokens=200,
        )

        self.assertEqual(result["should_suggest"], False)
        self.assertEqual(calls["url"], "https://example.test/v1/responses")
        self.assertEqual(calls["timeout"], 12)
        self.assertEqual(calls["body"]["model"], "test-model")
        self.assertEqual(calls["body"]["text"]["format"]["type"], "json_schema")
        self.assertTrue(calls["body"]["text"]["format"]["strict"])


class VocabularyAdvisorReportMetadataTests(unittest.TestCase):
    def test_agent_report_marks_llm_as_vocabulary_suggestion_only_when_advisor_is_injected(self):
        class StaticVocabularyAdvisor:
            provider = "test_provider"
            model = "test-model"
            temperature = 0.0
            max_tokens = 200

            def suggest(self, question, dataset_columns, analysis_terms):
                return VocabularySuggestion(
                    target_csv="config/analysis_terms.csv",
                    kind="group_by",
                    value="region",
                    terms=["地区"],
                    reason="test",
                    source="test",
                    confidence=0.8,
                )

        with tempfile.TemporaryDirectory() as tmpdir:
            dataset = Path(tmpdir) / "region_revenue.csv"
            dataset.write_text("region,revenue\nnorth,100\nsouth,200\n", encoding="utf-8")

            report = PowerBananaAgent(vocabulary_advisor=StaticVocabularyAdvisor()).answer(
                dataset,
                "哪个地区收入最高？",
            )

        self.assertEqual(report.status, "needs_clarification")
        self.assertEqual(report.llm_settings.provider, "test_provider")
        self.assertEqual(report.llm_settings.model, "test-model")
        self.assertEqual(report.llm_settings.mode, "vocabulary_suggestion_only")
        self.assertEqual(report.llm_settings.max_tokens, 200)


if __name__ == "__main__":
    unittest.main()
