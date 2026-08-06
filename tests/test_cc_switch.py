import json
import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


class CCSwitchTests(unittest.TestCase):
    def test_load_cc_switch_runtime_reads_current_codex_provider(self) -> None:
        from ai_drama_agent.cc_switch import load_cc_switch_runtime

        with tempfile.TemporaryDirectory() as directory:
            db_path = Path(directory) / "cc-switch.db"
            connection = sqlite3.connect(db_path)
            connection.execute(
                """
                CREATE TABLE providers (
                    id TEXT PRIMARY KEY,
                    app_type TEXT NOT NULL,
                    name TEXT NOT NULL,
                    settings_config TEXT NOT NULL,
                    created_at INTEGER,
                    is_current BOOLEAN NOT NULL
                )
                """
            )
            connection.execute(
                """
                CREATE TABLE proxy_config (
                    app_type TEXT PRIMARY KEY,
                    enabled INTEGER NOT NULL,
                    listen_address TEXT NOT NULL,
                    listen_port INTEGER NOT NULL
                )
                """
            )
            connection.execute(
                """
                CREATE TABLE provider_health (
                    provider_id TEXT NOT NULL,
                    app_type TEXT NOT NULL,
                    is_healthy INTEGER NOT NULL,
                    last_error TEXT
                )
                """
            )
            settings_config = json.dumps(
                {
                    "config": (
                        'model_provider = "custom"\n'
                        'model = "codex-auto-review"\n'
                        'model_reasoning_effort = "high"\n\n'
                        '[model_providers.custom]\n'
                        'name = "My Codex"\n'
                        'base_url = "https://example.com/v1"\n'
                        'wire_api = "responses"\n'
                    )
                }
            )
            connection.execute(
                """
                INSERT INTO providers (id, app_type, name, settings_config, created_at, is_current)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                ("provider-1", "codex", "My Codex", settings_config, 1, 1),
            )
            connection.execute(
                """
                INSERT INTO proxy_config (app_type, enabled, listen_address, listen_port)
                VALUES (?, ?, ?, ?)
                """,
                ("codex", 1, "127.0.0.1", 15721),
            )
            connection.execute(
                """
                INSERT INTO provider_health (provider_id, app_type, is_healthy, last_error)
                VALUES (?, ?, ?, ?)
                """,
                ("provider-1", "codex", 1, ""),
            )
            connection.commit()
            connection.close()

            with patch("ai_drama_agent.cc_switch._probe_proxy", return_value=(True, "healthy")):
                runtime = load_cc_switch_runtime(db_path=db_path, probe_proxy=True)

        self.assertEqual(runtime.provider_name, "My Codex")
        self.assertEqual(runtime.model, "codex-auto-review")
        self.assertEqual(runtime.wire_api, "responses")
        self.assertEqual(runtime.reasoning_effort, "high")
        self.assertTrue(runtime.proxy_running)
        self.assertEqual(runtime.protocol_endpoint, "http://127.0.0.1:15721/v1/responses")

    def test_cc_switch_responses_client_parses_output_text(self) -> None:
        from ai_drama_agent.cc_switch import CCSwitchRuntime
        from ai_drama_agent.llm import CCSwitchResponsesClient

        class FakeResponse:
            def __enter__(self):
                return self

            def __exit__(self, *args: object) -> None:
                return None

            def read(self) -> bytes:
                return json.dumps(
                    {
                        "output": [
                            {
                                "type": "message",
                                "content": [{"type": "output_text", "text": '{"ok": true}'}],
                            }
                        ]
                    }
                ).encode("utf-8")

        runtime = CCSwitchRuntime(
            provider_id="provider-1",
            provider_name="My Codex",
            model="codex-auto-review",
            wire_api="responses",
            provider_base_url="https://example.com/v1",
            reasoning_effort="high",
            proxy_enabled=True,
            listen_address="127.0.0.1",
            listen_port=15721,
            proxy_running=True,
            proxy_status="healthy",
            provider_healthy=True,
            provider_last_error="",
            db_path="C:\\Users\\LEGION\\.cc-switch\\cc-switch.db",
        )

        with patch("urllib.request.urlopen", return_value=FakeResponse()):
            client = CCSwitchResponsesClient.from_runtime(runtime)
            payload = client.complete_json("system", "user")

        self.assertEqual(payload, {"ok": True})

    def test_cc_switch_chat_completions_client_parses_message_content(self) -> None:
        from ai_drama_agent.cc_switch import CCSwitchRuntime
        from ai_drama_agent.llm import CCSwitchChatCompletionsClient

        class FakeResponse:
            def __enter__(self):
                return self

            def __exit__(self, *args: object) -> None:
                return None

            def read(self) -> bytes:
                return json.dumps(
                    {"choices": [{"message": {"content": '{"ok": true, "wire_api": "chat_completions"}'}}]}
                ).encode("utf-8")

        runtime = CCSwitchRuntime(
            provider_id="provider-1",
            provider_name="My Codex",
            model="codex-auto-review",
            wire_api="chat_completions",
            provider_base_url="https://example.com/v1",
            reasoning_effort="high",
            proxy_enabled=True,
            listen_address="127.0.0.1",
            listen_port=15721,
            proxy_running=True,
            proxy_status="healthy",
            provider_healthy=True,
            provider_last_error="",
            db_path="C:\\Users\\LEGION\\.cc-switch\\cc-switch.db",
        )

        with patch("urllib.request.urlopen", return_value=FakeResponse()):
            client = CCSwitchChatCompletionsClient.from_runtime(runtime)
            payload = client.complete_json("system", "user")

        self.assertEqual(payload, {"ok": True, "wire_api": "chat_completions"})


if __name__ == "__main__":
    unittest.main()
