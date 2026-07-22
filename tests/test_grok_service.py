from __future__ import annotations

from types import SimpleNamespace
import unittest

from config.grok_config import GrokConfig
from models import Influencer
from services.grok_service import GrokService


class GrokServiceTests(unittest.TestCase):
    def test_missing_api_key_returns_default_analysis(self) -> None:
        config = GrokConfig(api_key=None, model="gemini-2.5-flash")
        service = GrokService(config=config)
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

        self.assertEqual(analysis.summary, "AI analysis temporarily unavailable; using default scoring only")
        self.assertEqual(analysis.niche, "unknown")
        self.assertEqual(analysis.government_support_score, 0)

    def test_build_prompt_contains_required_analysis_context(self) -> None:
        config = GrokConfig(api_key="test-key", model="gemini-2.5-flash")
        service = GrokService(config=config, client=self._fake_client('{"detected_language":"English","niche":"Fashion","government_support_score":80,"political_orientation":"supportive","confidence":0.8,"summary":"ok","keywords":["fashion"],"reasoning":"reason"}'))
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
        self.assertIn("Analyze the following influencer profile", prompt)
        self.assertIn("Alice", prompt)
        self.assertIn("@alice", prompt)
        self.assertIn("Fashion creator", prompt)

    def test_invalid_json_returns_default_analysis(self) -> None:
        config = GrokConfig(api_key="test-key", model="gemini-2.5-flash")
        service = GrokService(config=config, client=self._fake_client("not json"))
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

        self.assertEqual(analysis.summary, "AI analysis temporarily unavailable; using default scoring only")
        self.assertEqual(analysis.reasoning, "Gemini returned invalid JSON: Expecting value: line 1 column 1 (char 0)")

    @staticmethod
    def _fake_client(content: str):
        response = SimpleNamespace(text=content)

        class FakeModels:
            def generate_content(self, *args, **kwargs):
                return response

        return SimpleNamespace(models=FakeModels())
