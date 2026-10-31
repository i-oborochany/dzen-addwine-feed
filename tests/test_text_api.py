import importlib.util
import os
from pathlib import Path
import unittest
from unittest.mock import Mock, patch

import requests

spec = importlib.util.spec_from_file_location("dzen_text_api", Path(__file__).parents[1] / "scripts" / "claude_api.py")
client = importlib.util.module_from_spec(spec)
spec.loader.exec_module(client)


def completed(text):
    return {"id": "resp_test", "status": "completed", "output": [
        {"type": "reasoning", "summary": []},
        {"type": "message", "content": [{"type": "output_text", "text": text}]},
    ]}


class TextApiContractTests(unittest.TestCase):
    def setUp(self):
        self.environment = patch.dict(os.environ, {"OPENAI_API_KEY": "sk-unit-test-secret"}, clear=True)
        self.environment.start()
        self.addCleanup(self.environment.stop)
        self.post = patch.object(client.requests, "post").start()
        self.addCleanup(patch.stopall)
        self.response = Mock(status_code=200)
        self.response.json.return_value = completed('{"title": "Статья", "body": "Текст"}')
        self.post.return_value = self.response

    def test_preserves_prompts_limits_and_json_contract_without_anthropic_key(self):
        self.assertEqual(client.generate_json("JSON: редакционные правила", "Тема без изменений", 500, 0.3),
                         {"title": "Статья", "body": "Текст"})
        payload = self.post.call_args.kwargs["json"]
        self.assertEqual(payload["input"], [
            {"role": "system", "content": "JSON: редакционные правила"},
            {"role": "user", "content": "Тема без изменений"},
        ])
        # JSON mode checks the input messages, including the system message.
        self.assertIn("json", " ".join(m["content"] for m in payload["input"]).lower())
        self.assertEqual(payload["max_output_tokens"], 500)
        self.assertEqual(payload["temperature"], 0.3)
        self.assertFalse(payload["store"])

    def test_reads_all_text_blocks_after_non_message_items(self):
        data = completed('{"title":')
        data["output"][1]["content"].append({"type": "output_text", "text": '"Статья"}'})
        self.response.json.return_value = data
        self.assertEqual(client.generate_json("JSON", "Тема"), {"title": "Статья"})

    def test_incomplete_response_cannot_become_partial_article(self):
        data = completed('{"title":"Частичная статья"}')
        data.update(status="incomplete", incomplete_details={"reason": "max_output_tokens"})
        self.response.json.return_value = data
        with self.assertRaisesRegex(RuntimeError, "max_output_tokens"):
            client.generate_json("JSON", "Тема")

    def test_refusal_cannot_become_article(self):
        data = completed('{}')
        data["output"][1]["content"].insert(0, {"type": "refusal", "refusal": "Declined"})
        self.response.json.return_value = data
        with self.assertRaisesRegex(RuntimeError, "отказался"):
            client.generate_json("JSON", "Тема")

    def test_empty_invalid_and_non_object_responses_fail(self):
        for text in ["", "not JSON", "[]"]:
            with self.subTest(text=text):
                self.response.json.return_value = completed(text)
                with self.assertRaises(RuntimeError):
                    client.generate_json("JSON", "Тема")

    def test_network_timeout_is_not_replayed(self):
        self.post.side_effect = requests.exceptions.ReadTimeout("response unknown")
        with self.assertRaises(requests.exceptions.ReadTimeout):
            client.generate_json("JSON", "Тема")
        self.assertEqual(self.post.call_count, 1)

    def test_error_never_exposes_api_key(self):
        self.response.status_code = 401
        self.response.json.return_value = {"error": {"message": "Incorrect API key sk-unit-test-secret"}}
        with self.assertRaises(RuntimeError) as raised:
            client.generate_json("JSON", "Тема")
        self.assertNotIn("sk-unit-test-secret", str(raised.exception))
        self.assertIn("401", str(raised.exception))
        self.assertEqual(self.post.call_count, 1)

    def test_anthropic_key_does_not_authorize_openai(self):
        with patch.dict(os.environ, {"ANTHROPIC_API_KEY": "not-used"}, clear=True):
            with self.assertRaisesRegex(RuntimeError, "OPENAI_API_KEY"):
                client.generate_json("JSON", "Тема")
        self.post.assert_not_called()


if __name__ == "__main__":
    unittest.main()
