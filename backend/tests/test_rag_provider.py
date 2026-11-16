import os
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from app import rag


class OpenRouterProviderTests(unittest.TestCase):
    @patch("openai.OpenAI")
    def test_answer_uses_openrouter_free_model(self, openai_client):
        response = SimpleNamespace(
            choices=[SimpleNamespace(message=SimpleNamespace(content="Grounded answer"))]
        )
        openai_client.return_value.chat.completions.create.return_value = response
        hits = [{"filename": "guide.pdf", "page": 2, "text": "Useful excerpt"}]

        with patch.dict(
            os.environ,
            {
                "OPENROUTER_API_KEY": "test-key",
            },
        ), patch.object(rag, "OPENROUTER_MODEL", "openrouter/free"):
            result = rag.answer("What does the guide say?", hits)

        self.assertEqual(result, "Grounded answer")
        openai_client.assert_called_once_with(
            api_key="test-key",
            base_url="https://openrouter.ai/api/v1",
        )
        request = openai_client.return_value.chat.completions.create.call_args.kwargs
        self.assertEqual(request["model"], "openrouter/free")
        self.assertEqual(request["messages"][0]["role"], "system")
        self.assertIn("[guide.pdf p.2]", request["messages"][1]["content"])

    def test_openrouter_requires_an_api_key(self):
        with patch.dict(
            os.environ,
            {},
            clear=True,
        ):
            with self.assertRaisesRegex(RuntimeError, "OPENROUTER_API_KEY is not set"):
                rag.answer("Question", [])


if __name__ == "__main__":
    unittest.main()
