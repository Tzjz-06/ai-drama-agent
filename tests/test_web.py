import base64
import http.client
import io
import json
import tempfile
import unittest
import zipfile
from http import HTTPStatus
from pathlib import Path
from unittest.mock import patch


class WebTests(unittest.TestCase):
    def test_api_helpers(self) -> None:
        from ai_drama_agent.web import _optional_text, _positive_int, _required_text

        self.assertEqual(_required_text({"title": "测试"}, "title"), "测试")
        with self.assertRaises(ValueError):
            _required_text({"title": "   "}, "title")
        self.assertEqual(_optional_text({}, "style", "默认风格"), "默认风格")
        self.assertEqual(_positive_int("24", 12), 24)
        self.assertEqual(_positive_int("-1", 12), 12)

    def test_base64_upload_body_limit_accepts_maximum_document(self) -> None:
        from ai_drama_agent.web import MAX_BODY_BYTES, MAX_UPLOAD_BYTES

        encoded_size = ((MAX_UPLOAD_BYTES + 2) // 3) * 4
        self.assertGreater(MAX_BODY_BYTES, encoded_size)

    def test_error_payload_shape(self) -> None:
        payload = json.loads(json.dumps({"error": "字段 title 不能为空。"}, ensure_ascii=False))
        self.assertEqual(payload["error"], "字段 title 不能为空。")
        self.assertEqual(HTTPStatus.BAD_REQUEST, 400)

    def test_rule_based_mode_label_value(self) -> None:
        payload = json.loads(
            json.dumps({"mode": "offline-rule-based"}, ensure_ascii=False)
        )
        self.assertEqual(payload["mode"], "offline-rule-based")

    def test_real_model_requires_explicit_api_key(self) -> None:
        from ai_drama_agent.llm import OpenAICompatibleClient

        with self.assertRaisesRegex(RuntimeError, "尚未配置真实模型 API Key"):
            OpenAICompatibleClient.from_config("", "https://api.openai.com/v1", "gpt-4.1")

    def test_reasoning_effort_is_added_only_when_explicit(self) -> None:
        from ai_drama_agent.llm import OpenAICompatibleClient

        class FakeResponse:
            def __enter__(self):
                return self

            def __exit__(self, *args: object) -> None:
                return None

            def read(self) -> bytes:
                return b'{"choices":[{"message":{"content":"{}"}}]}'

        captured: list[dict[str, object]] = []
        captured_request_headers: list[dict[str, str]] = []

        def fake_urlopen(request, timeout):
            captured.append(json.loads(request.data.decode("utf-8")))
            captured_request_headers.append(dict(request.header_items()))
            return FakeResponse()

        with patch("urllib.request.urlopen", side_effect=fake_urlopen):
            OpenAICompatibleClient.from_config("key", "https://example.com/v1", "o3", "high").complete_json("s", "u")
            OpenAICompatibleClient.from_config("key", "https://example.com/v1", "gpt-4.1", "auto").complete_json("s", "u")

        self.assertEqual(captured[0]["reasoning_effort"], "high")
        self.assertNotIn("reasoning_effort", captured[1])
        normalized_headers = {key.lower(): value for key, value in captured_request_headers[0].items()}
        self.assertIn("user-agent", normalized_headers)
        self.assertIn("accept", normalized_headers)

    def test_model_http_error_is_user_readable(self) -> None:
        from ai_drama_agent.llm import _format_http_error

        message = _format_http_error(401, '{"error":{"message":"Incorrect API key"}}')
        self.assertIn("Incorrect API key", message)
        self.assertIn("请检查 API Key", message)

    def test_cloudflare_1010_is_reported_as_upstream_access_denied(self) -> None:
        from ai_drama_agent.llm import _format_http_error

        detail = """
        <!doctype html>
        <html>
        <head><title>Access denied | api.qlhazycoder.top used Cloudflare to restrict access</title></head>
        <body>
        <p>The owner of this website (api.qlhazycoder.top) has banned your access based on your browser's signature.</p>
        <h1>Error 1010</h1>
        </body>
        </html>
        """.strip()
        message = _format_http_error(403, detail)
        self.assertIn("Cloudflare", message)
        self.assertIn("api.qlhazycoder.top", message)
        self.assertIn("Error 1010", message)
        self.assertIn("上游风控或封禁", message)
        self.assertNotIn("当前 API Key 没有访问该模型或接口的权限", message)
        self.assertNotIn("<html>", message)

    def test_proxy_message_with_html_cause_is_compacted(self) -> None:
        from ai_drama_agent.llm import _format_http_error

        detail = (
            "CC Switch local proxy failed while handling Codex endpoint /responses. "
            "Provider: My Codex; model: codex-auto-review; upstream_status: HTTP 403; "
            "cause: <!doctype html><html><head><title>Access denied | api.qlhazycoder.top used "
            "Cloudflare to restrict access</title></head><body><p>The owner of this website "
            "(api.qlhazycoder.top) has banned your access based on your browser's signature.</p>"
            "<h1>Error 1010</h1></body></html>"
        )
        message = _format_http_error(403, detail)
        self.assertIn("CC Switch local proxy failed", message)
        self.assertIn("Cloudflare", message)
        self.assertIn("api.qlhazycoder.top", message)
        self.assertLess(len(message), 420)

    def test_model_http_error_hides_oversized_provider_payload(self) -> None:
        from ai_drama_agent.llm import _format_http_error

        message = _format_http_error(500, "x" * 800)
        self.assertLess(len(message), 560)
        self.assertTrue(message.endswith("..."))

    def test_remote_disconnect_is_user_readable(self) -> None:
        from ai_drama_agent.llm import OpenAICompatibleClient

        with patch("urllib.request.urlopen", side_effect=http.client.RemoteDisconnected("closed")):
            with self.assertRaisesRegex(RuntimeError, "远端提前断开"):
                OpenAICompatibleClient.from_config(
                    "key",
                    "https://example.com/v1",
                    "gpt-4.1",
                ).complete_json("s", "u")

    def test_task_queue_uses_asynq_gateway(self) -> None:
        from ai_drama_agent.task_queue import AsynqGateway

        class FakeResponse:
            def __enter__(self):
                return self

            def __exit__(self, *args: object) -> None:
                return None

            def read(self) -> bytes:
                return b'{"ok":true}'

        captured = []

        def fake_urlopen(request, timeout):
            captured.append(request)
            return FakeResponse()

        with patch("urllib.request.urlopen", side_effect=fake_urlopen):
            AsynqGateway("http://queue.test").enqueue({"id": "task_1", "type": "video"})

        self.assertEqual(captured[0].full_url, "http://queue.test/enqueue")
        self.assertEqual(json.loads(captured[0].data.decode("utf-8"))["type"], "video")

    def test_media_provider_key_is_not_persisted_in_local_task_data(self) -> None:
        from ai_drama_agent.store import LocalStore
        from ai_drama_agent.web import DramaWebHandler

        with tempfile.TemporaryDirectory() as directory:
            store = LocalStore(Path(directory) / "app_state.json")
            user = store.register("media-test", "", "secret123")
            project = store.create_project(user["id"], {"title": "媒体配置测试"})
            chapter = store.create_chapter(user["id"], project["id"], {"title": "第一集"})
            handler = object.__new__(DramaWebHandler)
            handler.store = store
            response: dict[str, object] = {}
            handler._send_json = response.update

            with patch("ai_drama_agent.web.LocalMediaRunner.submit") as submit:
                handler._handle_task_create(
                    user["id"],
                    project["id"],
                    chapter["id"],
                    {
                        "type": "video",
                        "shot_id": "SH001",
                        "prompt": "test prompt",
                        "provider_config": {
                            "category": "video",
                            "api_url": "https://video.example.test/generate",
                            "model": "video-v1",
                            "api_key": "secret-provider-key",
                        },
                    },
                )

            task_id = str(response["task"]["id"])  # type: ignore[index]
            persisted_payload = store._data["tasks"][task_id]["payload"]
            self.assertNotIn("provider_config", persisted_payload)
            submitted_task, submitted_provider = submit.call_args.args
            self.assertEqual(submitted_task["id"], task_id)
            self.assertEqual(submitted_provider["api_key"], "secret-provider-key")
            self.assertEqual(submitted_provider["provider"], "compatible")

    def test_media_provider_requires_endpoint_and_model(self) -> None:
        from ai_drama_agent.web import _resolve_media_provider

        with self.assertRaises(ValueError):
            _resolve_media_provider(
                {"category": "image", "api_url": "", "model": ""},
                task_type="frame_image",
                environment_url="",
                environment_key="",
            )

    def test_openai_media_provider_does_not_require_endpoint(self) -> None:
        from ai_drama_agent.web import _resolve_media_provider

        provider = _resolve_media_provider(
            {
                "category": "video",
                "provider": "openai_sora",
                "api_key": "customer-key",
                "model": "sora-2",
            },
            task_type="video",
            environment_url="",
            environment_key="",
        )

        self.assertEqual(provider["provider"], "openai_sora")
        self.assertEqual(provider["api_url"], "")

    def test_local_media_urls_are_owned_by_local_runner(self) -> None:
        from ai_drama_agent.local_media import LocalMediaRunner

        self.assertEqual(
            LocalMediaRunner._task_id_from_media_url("/api/media/tasks/task_123/file"),
            "task_123",
        )
        self.assertEqual(LocalMediaRunner._task_id_from_media_url("https://example.test/video.mp4"), "")

    def test_local_media_runner_migrates_legacy_media_once(self) -> None:
        from ai_drama_agent.local_media import LocalMediaRunner
        from ai_drama_agent.store import LocalStore

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            legacy_media = root / "bundle" / "data" / "media"
            user_data = root / "local-app-data" / "FrameForgeStudio"
            legacy_media.mkdir(parents=True)
            (legacy_media / "task_123.png").write_bytes(b"legacy-media")
            store = LocalStore(user_data / "app_state.json")

            with patch("ai_drama_agent.local_media.app_root", return_value=root / "bundle"):
                runner = LocalMediaRunner(store)
                self.assertEqual(runner.media_file("task_123").read_bytes(), b"legacy-media")

                runner.media_root.joinpath("task_123.png").write_bytes(b"new-media")
                (legacy_media / "task_123.png").write_bytes(b"legacy-changed")
                second_runner = LocalMediaRunner(store)
                self.assertEqual(second_runner.media_file("task_123").read_bytes(), b"new-media")

    def test_import_txt_script(self) -> None:
        from ai_drama_agent.web import _extract_uploaded_script

        payload = {
            "filename": "scene.txt",
            "content_base64": base64.b64encode("雨夜，林默推门而入。".encode("utf-8")).decode("ascii"),
        }
        self.assertEqual(_extract_uploaded_script(payload), "雨夜，林默推门而入。")

    def test_import_docx_script(self) -> None:
        from ai_drama_agent.web import _extract_uploaded_script

        xml = """
        <w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
          <w:body>
            <w:p><w:r><w:t>第一幕</w:t></w:r></w:p>
            <w:p><w:r><w:t>角色走进房间。</w:t></w:r></w:p>
          </w:body>
        </w:document>
        """.strip()
        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, "w") as archive:
            archive.writestr("word/document.xml", xml)

        payload = {
            "filename": "scene.docx",
            "content_base64": base64.b64encode(buffer.getvalue()).decode("ascii"),
        }
        self.assertEqual(_extract_uploaded_script(payload), "第一幕\n角色走进房间。")

    def test_prompt_document_contains_all_shot_prompt_types(self) -> None:
        from docx import Document

        from ai_drama_agent.web import _build_prompt_document

        content = _build_prompt_document(
            {"title": "雨夜归来", "style": "电影感国漫"},
            {"episode_no": 1, "title": "便利店", "production": {}},
            {
                "characters": [{"name": "林默", "turnaround_prompt": "角色提示词"}],
                "scenes": [{"name": "便利店", "environment_prompt": "场景提示词"}],
                "props": [{"name": "雨伞", "description": "道具提示词"}],
                "shots": [
                    {
                        "id": "shot_001",
                        "shot_size": "近景",
                        "camera_position": "平视",
                        "duration_seconds": 3,
                        "first_frame_prompt": "首帧提示词",
                        "video_prompt": "视频提示词",
                        "last_frame_prompt": "尾帧提示词",
                        "negative_prompt": "负面提示词",
                    }
                ],
            },
        )

        document = Document(io.BytesIO(content))
        text = "\n".join(paragraph.text for paragraph in document.paragraphs)
        for expected in ("角色提示词", "场景提示词", "道具提示词", "首帧提示词", "视频提示词", "尾帧提示词", "负面提示词"):
            self.assertIn(expected, text)

    def test_pdf_always_mode_skips_native_text_layer(self) -> None:
        from ai_drama_agent.web import _extract_uploaded_script

        payload = {
            "filename": "scene.pdf",
            "ocr_mode": "always",
            "content_base64": base64.b64encode(b"fake-pdf").decode("ascii"),
        }
        with patch("ai_drama_agent.web._extract_pdf_text", return_value="OCR 剧本") as extractor:
            self.assertEqual(_extract_uploaded_script(payload), "OCR 剧本")
        extractor.assert_called_once_with(b"fake-pdf", mode="always")


if __name__ == "__main__":
    unittest.main()
