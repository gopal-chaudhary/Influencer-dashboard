from __future__ import annotations

from types import SimpleNamespace
from typing import Any, cast
import unittest

from config.grok_config import GrokConfig
from models import Influencer
from services.grok_service import GrokConfigurationError, GrokResponseParseError, GrokService


class GrokServiceTests(unittest.TestCase):
    def test_missing_api_key_raises_configuration_error(self) -> None:
        config = GrokConfig(api_key=None, base_url="https://api.x.ai/v1", model="grok-2-latest")

        with self.assertRaises(GrokConfigurationError):
            GrokService(config=config, client=cast(Any, object()))

    def test_build_prompt_contains_required_analysis_context(self) -> None:
        config = GrokConfig(api_key="test-key", base_url="https://api.x.ai/v1", model="grok-2-latest")
        service = GrokService(config=config, client=cast(Any, self._fake_client("{}")))
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

    def test_invalid_json_raises_parse_error(self) -> None:
        config = GrokConfig(api_key="test-key", base_url="https://api.x.ai/v1", model="grok-2-latest")
        service = GrokService(config=config, client=cast(Any, self._fake_client("not json")))
        influencer = Influencer(
            name="Alice",
            handle="alice",
            platform="Instagram",
            bio="Fashion creator",
            recent_content=["recent post"],
            followers=100,
            language="English",
        )

        with self.assertRaises(GrokResponseParseError):
            service.analyze_influencer(influencer)

    @staticmethod
    def _fake_client(content: str):
        response = SimpleNamespace(
            choices=[SimpleNamespace(message=SimpleNamespace(content=content))]
        )

        class FakeCompletions:
            def create(self, *args, **kwargs):
                return response

        class FakeChat:
            completions = FakeCompletions()

        return SimpleNamespace(chat=FakeChat())
