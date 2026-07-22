from __future__ import annotations

from types import SimpleNamespace
import unittest

from config.gemini_config import GeminiConfig
from models import Influencer
from services.gemini_service import GeminiService


class GeminiServiceTests(unittest.TestCase):
    def test_missing_api_key_returns_default_analysis(self) -> None:
        config = GeminiConfig(api_key=None, model="gemini-2.5-flash")
        service = GeminiService(config=config)
        influencer = Influencer(
            name="Alice",
            handle="alice",
            platform="Instagram",
            bio="Fashion creator",
            recent_content=["recent post"],
            followers=100,
            language="English",
        )

        analysis = service.analyze_influencer(influencer)

        self.assertEqual(
            analysis.summary,
            "AI analysis temporarily unavailable; using default scoring only",
        )
        self.assertEqual(analysis.niche, "unknown")
        self.assertEqual(analysis.government_support_score, 0)

    def test_batch_analysis_returns_mapping(self) -> None:
        config = GeminiConfig(api_key="test-key", model="gemini-2.5-flash")
        service = GeminiService(
            config=config,
            client=self._fake_interactions_client(
                SimpleNamespace(output_text='{"results":[{"handle":"alice","detected_language":"English","niche":"Fashion","government_support_score":80,"political_orientation":"supportive","confidence":0.8,"summary":"ok","keywords":["fashion"],"reasoning":"reason"}]}')
            ),
        )
        influencer = Influencer(
            name="Alice",
            handle="alice",
            platform="Instagram",
            bio="Fashion creator",
            recent_content=["recent post"],
            followers=100,
            language="English",
        )

        analyses = service.analyze_influencers([influencer])

        self.assertIn("alice", analyses)
        self.assertEqual(analyses["alice"].niche, "Fashion")

    def test_build_prompt_contains_required_analysis_context(self) -> None:
        config = GeminiConfig(api_key="test-key", model="gemini-2.5-flash")
        service = GeminiService(
            config=config,
            client=self._fake_interactions_client(
                SimpleNamespace(output_text='{"results":[{"handle":"alice","detected_language":"English","niche":"Fashion","government_support_score":80,"political_orientation":"supportive","confidence":0.8,"summary":"ok","keywords":["fashion"],"reasoning":"reason"}]}')
            ),
        )
        influencer = Influencer(
            name="Alice",
            handle="alice",
            platform="Instagram",
            bio="Fashion creator",
            recent_content=["recent post"],
            followers=100,
            language="English",
        )

        prompt = service._build_prompt(influencer)

        self.assertIn("Return JSON only", prompt)
        self.assertIn("Analyze the following influencer profiles", prompt)
        self.assertIn("Alice", prompt)
        self.assertIn("Handle: alice", prompt)
        self.assertIn("Fashion creator", prompt)

    def test_invalid_json_returns_default_analysis(self) -> None:
        config = GeminiConfig(api_key="test-key", model="gemini-2.5-flash")
        response = SimpleNamespace(output_text="not json")
        service = GeminiService(config=config, client=self._fake_interactions_client(response))
        influencer = Influencer(
            name="Alice",
            handle="alice",
            platform="Instagram",
            bio="Fashion creator",
            recent_content=["recent post"],
            followers=100,
            language="English",
        )

        analysis = service.analyze_influencer(influencer)

        self.assertEqual(
            analysis.summary,
            "AI analysis temporarily unavailable; using default scoring only",
        )
        self.assertEqual(
            analysis.reasoning,
            "Expecting value: line 1 column 1 (char 0)",
        )

    def test_interactions_create_returns_output_text(self) -> None:
        config = GeminiConfig(api_key="test-key", model="gemini-2.5-flash")
        response = SimpleNamespace(output_text='{"results":[{"handle":"alice","detected_language":"English","niche":"Fashion","government_support_score":80,"political_orientation":"supportive","confidence":0.8,"summary":"ok","keywords":["fashion"],"reasoning":"reason"}]}')
        service = GeminiService(config=config, client=self._fake_interactions_client(response))
        influencer = Influencer(
            name="Alice",
            handle="alice",
            platform="Instagram",
            bio="Fashion creator",
            recent_content=["recent post"],
            followers=100,
            language="English",
        )

        analyses = service.analyze_influencers([influencer])

        self.assertIn("alice", analyses)
        self.assertEqual(analyses["alice"].niche, "Fashion")

    def test_interactions_create_uses_extra_body_for_model_fields(self) -> None:
        config = GeminiConfig(api_key="test-key", model="gemini-2.5-flash")
        captured: dict[str, object] = {}
        response = SimpleNamespace(output_text='{"results":[{"handle":"alice","detected_language":"English","niche":"Fashion","government_support_score":80,"political_orientation":"supportive","confidence":0.8,"summary":"ok","keywords":["fashion"],"reasoning":"reason"}]}')

        def create(**kwargs: object) -> object:
            captured.update(kwargs)
            return response

        service = GeminiService(config=config, client=self._fake_interactions_client_with_create(create))
        influencer = Influencer(
            name="Alice",
            handle="alice",
            platform="Instagram",
            bio="Fashion creator",
            recent_content=["recent post"],
            followers=100,
            language="English",
        )

        service.analyze_influencers([influencer])

        self.assertEqual(captured.get("model"), "gemini-2.5-flash")
        self.assertEqual(captured.get("input"), service._build_prompt(influencer))
        self.assertEqual(captured.get("timeout"), config.timeout_seconds)
        self.assertNotIn("extra_body", captured)

    @staticmethod
    def _fake_client(content: str):
        response = SimpleNamespace(text=content)

        class FakeModels:
            def generate_content(self, *args, **kwargs):
                return response

        return SimpleNamespace(models=FakeModels())

    @staticmethod
    def _fake_interactions_client(response: Any):
        class FakeInteractions:
            def create(self, **kwargs):
                return response

        return SimpleNamespace(interactions=FakeInteractions())

    @staticmethod
    def _fake_interactions_client_with_create(create_callable):
        class FakeInteractions:
            def create(self, **kwargs):
                return create_callable(**kwargs)

        return SimpleNamespace(interactions=FakeInteractions())
