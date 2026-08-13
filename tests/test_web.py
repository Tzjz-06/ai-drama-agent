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
    def test_quick_create_generates_script_and_seedance_storyboard_in_one_call(self) -> None:
        from ai_drama_agent.store import LocalStore
        from ai_drama_agent.web import DramaWebHandler

        with tempfile.TemporaryDirectory() as directory:
            store = LocalStore(Path(directory) / "app_state.json")
            user = store.register("quick-create", "", "secret123")
            handler = object.__new__(DramaWebHandler)
            handler.store = store
            handler.offline_demo = True
            response: dict[str, object] = {}
            handler._send_json = response.update

            handler._handle_quick_create(
                user["id"],
                {"title": "雨夜来信", "brief": "失忆快递员收到一封来自未来的信"},
            )

            project = response["project"]
            chapter = response["chapter"]
            production = response["production"]
            self.assertEqual(len(project["chapters"]), 1)
            self.assertIn("△ ", chapter["content"])
            self.assertTrue(production["characters"])
            self.assertTrue(production["scenes"])
            self.assertTrue(production["shots"])
            self.assertIn("Seedance 2.0", production["shots"][0]["video_prompt"])
            self.assertEqual(len(store.list_projects(user["id"])), 1)

    def test_quick_progress_is_isolated_by_user_and_records_completion(self) -> None:
        from ai_drama_agent.web import DramaWebHandler

        DramaWebHandler._set_quick_progress(
            "progress-test", "user-1", 100, "创作完成", "已保存", status="completed"
        )

        progress = DramaWebHandler._get_quick_progress("progress-test")
        self.assertEqual(progress["user_id"], "user-1")
        self.assertEqual(progress["status"], "completed")
        self.assertEqual(progress["percent"], 100)

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

    def test_chat_completion_text_supports_common_relay_shapes(self) -> None:
        from ai_drama_agent.llm import _extract_chat_completion_text

        self.assertEqual(
            _extract_chat_completion_text({"choices": [{"message": {"content": "plain"}}]}),
            "plain",
        )
        self.assertEqual(
            _extract_chat_completion_text({"choices": [{"message": {"content": [{"text": "part one"}, {"text": "part two"}]}}]}),
            "part one\npart two",
        )
        self.assertEqual(
            _extract_chat_completion_text({"choices": [{"text": "legacy"}]}),
            "legacy",
        )
        self.assertEqual(_extract_chat_completion_text({"output_text": "fallback"}), "fallback")
        with self.assertRaisesRegex(RuntimeError, "choices"):
            _extract_chat_completion_text({})

    def test_script_document_contains_outline_and_content(self) -> None:
        from docx import Document

        from ai_drama_agent.web import _build_script_document

        content = _build_script_document(
            {"title": "Project Title"},
            {"title": "Episode One", "outline": "Outline text", "content": "Scene one\nDialogue two"},
        )
        document = Document(io.BytesIO(content))
        text = "\n".join(paragraph.text for paragraph in document.paragraphs)
        for expected in ("Project Title", "Episode One", "Outline text", "Scene one", "Dialogue two"):
            self.assertIn(expected, text)

    def test_production_archive_contains_script_and_storyboard_documents(self) -> None:
        from docx import Document

        from ai_drama_agent.web import _build_production_archive

        content = _build_production_archive(
            {"title": "雨夜归来", "style": "电影感国漫"},
            {"episode_no": 1, "title": "便利店", "outline": "本章梗概", "content": "第一场\n角色对白"},
            {
                "characters": [],
                "scenes": [],
                "props": [],
                "shots": [{"id": "shot_001", "video_prompt": "分镜视频提示词"}],
            },
        )
        with zipfile.ZipFile(io.BytesIO(content)) as archive:
            names = archive.namelist()
            self.assertEqual(len(names), 2)
            self.assertTrue(any(name.endswith("-剧本.docx") for name in names))
            self.assertTrue(any(name.endswith("-分镜提示词.docx") for name in names))
            script_name = next(name for name in names if name.endswith("-剧本.docx"))
            prompt_name = next(name for name in names if name.endswith("-分镜提示词.docx"))
            script_text = "\n".join(
                paragraph.text
                for paragraph in Document(io.BytesIO(archive.read(script_name))).paragraphs
            )
            prompt_text = "\n".join(
                paragraph.text
                for paragraph in Document(io.BytesIO(archive.read(prompt_name))).paragraphs
            )
        self.assertIn("角色对白", script_text)
        self.assertIn("分镜视频提示词", prompt_text)

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
