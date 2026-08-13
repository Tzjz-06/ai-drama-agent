"""FrameForge Studio 的本地 Web 服务。"""

from __future__ import annotations

import argparse
import base64
import binascii
import io
import json
import mimetypes
import os
import threading
import time
import urllib.error
import urllib.request
import zipfile
from docx import Document
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import quote, urlparse
from xml.etree import ElementTree

try:
    from pypdf import PdfReader
except ImportError:  # pragma: no cover - 仅在运行环境缺少 PDF 依赖时触发
    PdfReader = None

from .cc_switch import load_cc_switch_runtime
from .llm import (
    CCSwitchChatCompletionsClient,
    CCSwitchResponsesClient,
    OpenAICompatibleClient,
    build_cc_switch_client,
)
from .models import DramaProject, GenerationOptions
from .ocr import extract_scanned_script
from .paths import web_root
from .prompts import QUICK_SCRIPT_SYSTEM_PROMPT, build_quick_script_prompt
from .pipeline import (
    DramaAgent,
    build_default_agent,
    render_characters,
    render_continuity_report,
    render_production_package,
    render_production_system,
    render_scenes,
    render_story_bible,
    render_storyboard,
)
from .store import AuthError, LocalStore, StoreError


WEB_ROOT = web_root()
MAX_UPLOAD_BYTES = 12 * 1024 * 1024
# Uploads are transported as Base64 JSON, which is larger than the original file.
MAX_BODY_BYTES = ((MAX_UPLOAD_BYTES + 2) // 3) * 4 + 16 * 1024
SUPPORTED_DOCUMENTS = {".txt", ".pdf", ".docx", ".png", ".jpg", ".jpeg"}


class DramaWebHandler(BaseHTTPRequestHandler):
    """处理页面资源、剧本文档导入和分镜生成 API。"""

    offline_demo = False
    store = LocalStore()
    _quick_progress: dict[str, dict[str, Any]] = {}
    _quick_progress_lock = threading.Lock()

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        if parsed.path == "/":
            self._serve_file(WEB_ROOT / "index.html")
            return

        if parsed.path == "/api/runtime":
            cc_switch = _cc_switch_runtime_payload()
            self._send_json(
                {
                    "offline_demo": self.offline_demo,
                    "environment_model_configured": bool(os.getenv("AI_DRAMA_API_KEY")),
                    "environment_model": os.getenv("AI_DRAMA_MODEL", "gpt-4.1"),
                    "cc_switch": cc_switch,
                }
            )
            return

        if parsed.path == "/api/auth/me":
            try:
                self._send_json({"user": self._require_user()})
            except AuthError as error:
                self._json_error(HTTPStatus.UNAUTHORIZED, str(error))
            return

        if parsed.path.startswith("/api/progress/"):
            progress_id = parsed.path.removeprefix("/api/progress/").strip("/")
            try:
                user = self._require_user()
                progress = self._get_quick_progress(progress_id)
                if not progress or progress.get("user_id") != user["id"]:
                    self._json_error(HTTPStatus.NOT_FOUND, "进度记录不存在")
                    return
                self._send_json(
                    {"progress": {key: value for key, value in progress.items() if key != "user_id"}}
                )
            except AuthError as error:
                self._json_error(HTTPStatus.UNAUTHORIZED, str(error))
            return

        if parsed.path == "/api/projects":
            try:
                user = self._require_user()
                self._send_json({"projects": self.store.list_projects(user["id"])})
            except AuthError as error:
                self._json_error(HTTPStatus.UNAUTHORIZED, str(error))
            return

        if parsed.path.startswith("/api/projects/"):
            try:
                user = self._require_user()
                parts = _route_parts(parsed.path)
                if len(parts) == 3:
                    self._send_json({"project": self.store.get_project(user["id"], parts[2])})
                    return
                if len(parts) == 5 and parts[3] == "chapters":
                    self._send_json(
                        {"chapter": self.store.get_chapter(user["id"], parts[2], parts[4])}
                    )
                    return
                if len(parts) == 6 and parts[3] == "chapters" and parts[5] == "prompts.docx":
                    self._handle_prompt_document(user["id"], parts[2], parts[4])
                    return
                if len(parts) == 6 and parts[3] == "chapters" and parts[5] == "script.docx":
                    self._handle_script_document(user["id"], parts[2], parts[4])
                    return
                if len(parts) == 6 and parts[3] == "chapters" and parts[5] == "production.zip":
                    self._handle_production_archive(user["id"], parts[2], parts[4])
                    return
            except AuthError as error:
                self._json_error(HTTPStatus.UNAUTHORIZED, str(error))
                return
            except StoreError as error:
                self._json_error(HTTPStatus.NOT_FOUND, str(error))
                return

        if parsed.path.startswith("/assets/"):
            relative_path = parsed.path.removeprefix("/assets/")
            requested = (WEB_ROOT / "assets" / relative_path).resolve()
            assets_root = (WEB_ROOT / "assets").resolve()
            if assets_root not in requested.parents:
                self._json_error(HTTPStatus.NOT_FOUND, "资源不存在。")
                return
            self._serve_file(requested)
            return

        self._json_error(HTTPStatus.NOT_FOUND, "页面不存在。")

    def do_POST(self) -> None:
        path = urlparse(self.path).path
        try:
            payload = self._read_json()
            if path == "/api/auth/register":
                self._handle_register(payload)
                return
            if path == "/api/auth/login":
                self._handle_login(payload)
                return
            if path == "/api/auth/logout":
                self.store.logout(self._auth_token())
                self._send_json({"ok": True})
                return
            if path == "/api/model/test":
                self._require_user()
                self._handle_model_test(payload)
                return
            if path == "/api/projects":
                user = self._require_user()
                self._send_json({"project": self.store.create_project(user["id"], payload)})
                return
            if path == "/api/projects/quick-create":
                user = self._require_user()
                self._handle_quick_create(user["id"], payload)
                return
            if path.startswith("/api/projects/"):
                user = self._require_user()
                parts = _route_parts(path)
                if len(parts) == 4 and parts[3] == "chapters":
                    self._send_json(
                        {"chapter": self.store.create_chapter(user["id"], parts[2], payload)}
                    )
                    return
                if len(parts) == 6 and parts[3] == "chapters" and parts[5] == "generate":
                    self._handle_project_generate(user["id"], parts[2], parts[4], payload)
                    return
                if len(parts) == 6 and parts[3] == "chapters" and parts[5] == "draft":
                    self._handle_chapter_draft(user["id"], parts[2], parts[4], payload)
                    return
            if path == "/api/import-script":
                self._handle_import_script(payload)
                return
            if path == "/api/generate":
                self._handle_generate(payload)
                return
            self._json_error(HTTPStatus.NOT_FOUND, "接口不存在。")
        except AuthError as error:
            self._json_error(HTTPStatus.UNAUTHORIZED, str(error))
        except StoreError as error:
            self._json_error(HTTPStatus.NOT_FOUND, str(error))
        except ValueError as error:
            self._json_error(HTTPStatus.BAD_REQUEST, str(error))
        except Exception as error:
            self._json_error(HTTPStatus.INTERNAL_SERVER_ERROR, str(error))

    def do_PATCH(self) -> None:
        try:
            payload = self._read_json()
            path = urlparse(self.path).path
            user = self._require_user()
            parts = _route_parts(path)
            if len(parts) == 3 and parts[1] == "projects":
                self._send_json(
                    {"project": self.store.update_project(user["id"], parts[2], payload)}
                )
                return
            if len(parts) == 5 and parts[1] == "projects" and parts[3] == "chapters":
                self._send_json(
                    {
                        "chapter": self.store.update_chapter(
                            user["id"], parts[2], parts[4], payload
                        )
                    }
                )
                return
            if (
                len(parts) == 8
                and parts[1] == "projects"
                and parts[3] == "chapters"
                and parts[5] == "assets"
            ):
                self._send_json(
                    {
                        "chapter": self.store.update_production_asset(
                            user["id"],
                            parts[2],
                            parts[4],
                            parts[6],
                            parts[7],
                            payload,
                        )
                    }
                )
                return
            if (
                len(parts) == 7
                and parts[1] == "projects"
                and parts[3] == "chapters"
                and parts[5] == "shots"
            ):
                self._send_json(
                    {
                        "chapter": self.store.update_shot_prompts(
                            user["id"], parts[2], parts[4], parts[6], payload
                        )
                    }
                )
                return
            self._json_error(HTTPStatus.NOT_FOUND, "接口不存在。")
        except AuthError as error:
            self._json_error(HTTPStatus.UNAUTHORIZED, str(error))
        except StoreError as error:
            self._json_error(HTTPStatus.NOT_FOUND, str(error))
        except ValueError as error:
            self._json_error(HTTPStatus.BAD_REQUEST, str(error))
        except Exception as error:
            self._json_error(HTTPStatus.INTERNAL_SERVER_ERROR, str(error))

    def do_DELETE(self) -> None:
        try:
            path = urlparse(self.path).path
            user = self._require_user()
            parts = _route_parts(path)
            if len(parts) == 3 and parts[1] == "projects":
                self.store.delete_project(user["id"], parts[2])
                self._send_json({"ok": True})
                return
            self._json_error(HTTPStatus.NOT_FOUND, "接口不存在。")
        except AuthError as error:
            self._json_error(HTTPStatus.UNAUTHORIZED, str(error))
        except StoreError as error:
            self._json_error(HTTPStatus.NOT_FOUND, str(error))
        except ValueError as error:
            self._json_error(HTTPStatus.BAD_REQUEST, str(error))
        except Exception as error:
            self._json_error(HTTPStatus.INTERNAL_SERVER_ERROR, str(error))

    def log_message(self, format: str, *args: object) -> None:
        print(f"[web] {self.address_string()} - {format % args}")

    def _handle_import_script(self, payload: dict[str, Any]) -> None:
        filename = _required_text(payload, "filename")
        script = _extract_uploaded_script(payload)
        self._send_json(
            {
                "script": script,
                "filename": filename,
                "source_label": f"{filename} · {len(script)} 字",
            }
        )

    def _handle_generate(self, payload: dict[str, Any]) -> None:
        project, files = self._run_generation(payload)
        self._send_json(
            {
                "project": project.to_dict(),
                "files": files,
                "mode": project.metadata.get("generation_mode", "unknown"),
            }
        )

    def _handle_quick_create(self, user_id: str, payload: dict[str, Any]) -> None:
        brief = _required_text(payload, "brief")
        title = _optional_text(payload, "title", "一句话短剧")
        genre = _optional_text(payload, "genre", "短剧")
        style = _optional_text(payload, "style", "电影感二维国漫")
        aspect_ratio = _optional_text(payload, "aspect_ratio", "9:16")
        progress_id = _optional_text(payload, "progress_id", "")[:128]
        if progress_id:
            self._set_quick_progress(
                progress_id, user_id, 5, "准备创作", "正在校验输入并准备制作流程"
            )
        project = self.store.create_project(
            user_id,
            {
                "title": title,
                "description": brief,
                "genre": genre,
                "style": style,
                "aspect_ratio": aspect_ratio,
            },
        )
        try:
            if progress_id:
                self._set_quick_progress(
                    progress_id, user_id, 15, "创建项目和章节", "正在建立项目与首章"
                )
            chapter = self.store.create_chapter(
                user_id,
                project["id"],
                {"title": "第 1 集"},
            )
            if progress_id:
                self._set_quick_progress(
                    progress_id, user_id, 25, "创作完整剧本", "正在根据一句话梗概扩写完整剧本"
                )
            draft = self._draft_quick_script(payload, project, chapter, brief)
            chapter = self.store.update_chapter(
                user_id,
                project["id"],
                chapter["id"],
                {
                    "title": str(draft.get("title") or chapter["title"]),
                    "outline": str(draft.get("outline") or brief),
                    "content": str(draft.get("content") or ""),
                    "status": "draft",
                },
            )
            if not chapter["content"].strip():
                raise RuntimeError("模型没有返回章节正文。")
            if progress_id:
                self._set_quick_progress(
                    progress_id, user_id, 50, "完整剧本已完成", "剧本正文已生成，准备拆解制作资产"
                )
                self._set_quick_progress(
                    progress_id, user_id, 60, "生成资产与分镜", "正在生成角色、场景、道具和分镜提示词"
                )
            generated, files = self._run_generation(
                {
                    **payload,
                    "script": chapter["content"],
                    "title": f"{project['title']} · {chapter['title']}",
                    "style": style,
                    "aspect_ratio": aspect_ratio,
                    "fps": 24,
                    "target_model": "seedance-2.0",
                }
            )
            chapter = self.store.save_production(
                user_id, project["id"], chapter["id"], generated.to_dict()
            )
            if progress_id:
                self._set_quick_progress(
                    progress_id,
                    user_id,
                    100,
                    "资产与分镜已完成",
                    "剧本、资产和分镜提示词已生成并保存",
                    status="completed",
                )
            self._send_json(
                {
                    "project": self.store.get_project(user_id, project["id"]),
                    "chapter": chapter,
                    "production": generated.to_dict(),
                    "files": files,
                    "mode": generated.metadata.get("generation_mode", "unknown"),
                }
            )
        except Exception as error:
            if progress_id:
                current = self._get_quick_progress(progress_id) or {}
                self._set_quick_progress(
                    progress_id,
                    user_id,
                    current.get("percent"),
                    current.get("stage", "创作失败"),
                    "当前阶段未完成",
                    status="failed",
                    error=str(error),
                )
            self.store.delete_project(user_id, project["id"])
            raise

    @classmethod
    def _set_quick_progress(
        cls,
        progress_id: str,
        user_id: str,
        percent: int | None,
        stage: str,
        message: str,
        *,
        status: str = "running",
        error: str = "",
    ) -> None:
        now = time.time()
        with cls._quick_progress_lock:
            cls._quick_progress[progress_id] = {
                "user_id": user_id,
                "status": status,
                "percent": percent,
                "stage": stage,
                "message": message,
                "error": error,
                "updated_at": now,
            }
            cutoff = now - 3600
            for stale_id, item in list(cls._quick_progress.items()):
                if item.get("updated_at", now) < cutoff:
                    cls._quick_progress.pop(stale_id, None)

    @classmethod
    def _get_quick_progress(cls, progress_id: str) -> dict[str, Any] | None:
        with cls._quick_progress_lock:
            item = cls._quick_progress.get(progress_id)
            return dict(item) if item else None

    def _draft_quick_script(
        self,
        payload: dict[str, Any],
        project: dict[str, Any],
        chapter: dict[str, Any],
        brief: str,
    ) -> dict[str, Any]:
        if self.offline_demo:
            return _offline_quick_script(brief, project["title"])
        return self._build_client(payload).complete_json(
            QUICK_SCRIPT_SYSTEM_PROMPT,
            build_quick_script_prompt(
                brief=brief,
                title=project["title"],
                genre=project["genre"],
                style=project["style"],
                episode_no=int(chapter["episode_no"]),
            ),
        )

    def _run_generation(self, payload: dict[str, Any]) -> tuple[DramaProject, dict[str, str]]:
        script = _required_text(payload, "script")
        title = _required_text(payload, "title")
        options = GenerationOptions(
            title=title,
            visual_style=_optional_text(payload, "style", "电影感二维国漫，细腻光影"),
            aspect_ratio=_optional_text(payload, "aspect_ratio", "16:9"),
            fps=_positive_int(payload.get("fps"), 24),
            target_model=_optional_text(payload, "target_model", "model-agnostic"),
        )
        project = self._build_agent(payload).run(script, options)
        files = {
            "production_package.md": render_production_package(project),
            "production_system.md": render_production_system(project),
            "story_bible.md": render_story_bible(project),
            "characters.md": render_characters(project),
            "scenes.md": render_scenes(project),
            "storyboard.md": render_storyboard(project),
            "continuity_report.md": render_continuity_report(project),
            "project.json": json.dumps(project.to_dict(), ensure_ascii=False, indent=2),
        }
        return project, files

    def _handle_project_generate(
        self, user_id: str, project_id: str, chapter_id: str, payload: dict[str, Any]
    ) -> None:
        project = self.store.get_project(user_id, project_id)
        chapter = self.store.get_chapter(user_id, project_id, chapter_id)
        generation_payload = dict(payload)
        generation_payload["title"] = f"{project['title']} · {chapter['title']}"
        generated, files = self._run_generation(generation_payload)
        saved_chapter = self.store.save_production(
            user_id, project_id, chapter_id, generated.to_dict()
        )
        self._send_json(
            {
                "project": generated.to_dict(),
                "chapter": saved_chapter,
                "files": files,
                "mode": generated.metadata.get("generation_mode", "unknown"),
            }
        )

    def _handle_chapter_draft(
        self, user_id: str, project_id: str, chapter_id: str, payload: dict[str, Any]
    ) -> None:
        if self.offline_demo:
            raise StoreError("AI 起草必须连接真实模型，离线调试模式不可用。")
        brief = _required_text(payload, "brief")
        project = self.store.get_project(user_id, project_id)
        chapter = self.store.get_chapter(user_id, project_id, chapter_id)
        client = self._build_client(payload)
        result = client.complete_json(
            QUICK_SCRIPT_SYSTEM_PROMPT,
            build_quick_script_prompt(
                brief=brief,
                title=project["title"],
                genre=project["genre"],
                style=project["style"],
                episode_no=int(chapter["episode_no"]),
            ),
        )
        update = {
            "title": str(result.get("title") or chapter["title"]),
            "outline": str(result.get("outline") or ""),
            "content": str(result.get("content") or ""),
            "status": "draft",
        }
        if not update["content"].strip():
            raise RuntimeError("模型没有返回章节正文。")
        saved = self.store.update_chapter(user_id, project_id, chapter_id, update)
        self._send_json({"chapter": saved})

    def _handle_model_test(self, payload: dict[str, Any]) -> None:
        client = self._build_client(payload)
        started_at = time.perf_counter()
        result = client.complete_json(
            "你是模型连接检测器。只返回 JSON 对象。",
            '返回 {"ok": true}，不要添加其他字段或解释。',
        )
        if result.get("ok") is not True:
            raise RuntimeError("模型接口已响应，但没有按要求返回连接检测结果。")
        self._send_json(
            {
                "ok": True,
                "mode": _model_mode(payload),
                "model": client.model,
                "base_url": _client_base_url(client),
                "provider": getattr(client, "provider_name", ""),
                "wire_api": getattr(client, "wire_api", "chat_completions"),
                "elapsed_ms": round((time.perf_counter() - started_at) * 1000),
            }
        )

    def _handle_prompt_document(self, user_id: str, project_id: str, chapter_id: str) -> None:
        project = self.store.get_project(user_id, project_id)
        chapter = self.store.get_chapter(user_id, project_id, chapter_id)
        production = chapter.get("production")
        if not isinstance(production, dict):
            raise ValueError("请先生成制作包，再导出全部提示词。")
        content = _build_prompt_document(project, chapter, production)
        filename = f"{project['title']}-{chapter['title']}-全部提示词.docx"
        encoded_filename = quote(filename)
        self.send_response(HTTPStatus.OK)
        self.send_header(
            "Content-Type",
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        )
        self.send_header("Content-Disposition", f"attachment; filename*=UTF-8''{encoded_filename}")
        self.send_header("Content-Length", str(len(content)))
        self.end_headers()
        self.wfile.write(content)

    def _handle_script_document(self, user_id: str, project_id: str, chapter_id: str) -> None:
        project = self.store.get_project(user_id, project_id)
        chapter = self.store.get_chapter(user_id, project_id, chapter_id)
        content = _build_script_document(project, chapter)
        filename = f"{project['title']}-{chapter['title']}-剧本.docx"
        encoded_filename = quote(filename)
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", "application/vnd.openxmlformats-officedocument.wordprocessingml.document")
        self.send_header("Content-Disposition", f"attachment; filename*=UTF-8''{encoded_filename}")
        self.send_header("Content-Length", str(len(content)))
        self.end_headers()
        self.wfile.write(content)

    def _handle_production_archive(self, user_id: str, project_id: str, chapter_id: str) -> None:
        project = self.store.get_project(user_id, project_id)
        chapter = self.store.get_chapter(user_id, project_id, chapter_id)
        production = chapter.get("production")
        if not isinstance(production, dict):
            raise ValueError("请先生成制作包，再一键导出剧本和分镜。")
        content = _build_production_archive(project, chapter, production)
        filename = f"{project['title']}-{chapter['title']}-剧本和分镜.zip"
        encoded_filename = quote(filename)
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", "application/zip")
        self.send_header("Content-Disposition", f"attachment; filename*=UTF-8''{encoded_filename}")
        self.send_header("Content-Length", str(len(content)))
        self.end_headers()
        self.wfile.write(content)

    def _handle_register(self, payload: dict[str, Any]) -> None:
        username = _required_text(payload, "username")
        password = _required_text(payload, "password")
        email = _optional_text(payload, "email", "")
        self._send_json({"user": self.store.register(username, email, password)})

    def _handle_login(self, payload: dict[str, Any]) -> None:
        identity = _required_text(payload, "identity")
        password = _required_text(payload, "password")
        token, user = self.store.login(identity, password)
        self._send_json({"token": token, "user": user})

    def _auth_token(self) -> str:
        header = self.headers.get("Authorization", "")
        return header.removeprefix("Bearer ").strip()

    def _require_user(self) -> dict[str, str]:
        token = self._auth_token()
        if not token:
            raise AuthError("请先登录。")
        return self.store.user_for_token(token)

    def _build_agent(self, payload: dict[str, Any]) -> DramaAgent:
        if self.offline_demo:
            return build_default_agent(offline_demo=True)

        return build_default_agent(client=self._build_client(payload))

    def _build_client(
        self, payload: dict[str, Any]
    ) -> OpenAICompatibleClient | CCSwitchResponsesClient | CCSwitchChatCompletionsClient:
        if _model_mode(payload) == "cc_switch":
            runtime = load_cc_switch_runtime(probe_proxy=True)
            return build_cc_switch_client(runtime)
        config = payload.get("model_config")
        if config is not None and not isinstance(config, dict):
            raise ValueError("model_config 必须是对象。")
        config_dict = config if isinstance(config, dict) else {}
        return OpenAICompatibleClient.from_config(
            api_key=_optional_text(config_dict, "api_key", os.getenv("AI_DRAMA_API_KEY", "")),
            base_url=_optional_text(
                config_dict,
                "base_url",
                os.getenv("AI_DRAMA_BASE_URL", "https://api.openai.com/v1"),
            ),
            model=_optional_text(config_dict, "model", os.getenv("AI_DRAMA_MODEL", "gpt-4.1")),
            reasoning_effort=_optional_text(
                config_dict,
                "reasoning_effort",
                os.getenv("AI_DRAMA_REASONING_EFFORT", ""),
            ),
        )

    def _read_json(self) -> dict[str, Any]:
        content_length = int(self.headers.get("Content-Length", "0"))
        if content_length <= 0:
            raise ValueError("请求内容为空。")
        if content_length > MAX_BODY_BYTES:
            raise ValueError("单次请求不能超过 16MB（上传文件按 Base64 编码后计算）。")

        raw = self.rfile.read(content_length)
        try:
            data = json.loads(raw.decode("utf-8"))
        except json.JSONDecodeError as error:
            raise ValueError("请求不是合法 JSON。") from error
        if not isinstance(data, dict):
            raise ValueError("请求顶层结构必须是对象。")
        return data

    def _serve_file(self, file_path: Path) -> None:
        if not file_path.is_file():
            self._json_error(HTTPStatus.NOT_FOUND, "文件不存在。")
            return

        content = file_path.read_bytes()
        content_type = mimetypes.guess_type(file_path.name)[0] or "application/octet-stream"
        if file_path.suffix == ".html":
            content_type = "text/html; charset=utf-8"
        elif file_path.suffix == ".css":
            content_type = "text/css; charset=utf-8"
        elif file_path.suffix == ".js":
            content_type = "text/javascript; charset=utf-8"

        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(content)))
        self.end_headers()
        self.wfile.write(content)

    def _send_json(self, payload: dict[str, Any]) -> None:
        content = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(content)))
        self.end_headers()
        self.wfile.write(content)

    def _json_error(self, status: HTTPStatus, message: str) -> None:
        content = json.dumps({"error": message}, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(content)))
        self.end_headers()
        self.wfile.write(content)


def _build_prompt_document(
    project: dict[str, Any], chapter: dict[str, Any], production: dict[str, Any]
) -> bytes:
    """Render the existing production data as a portable Word prompt sheet."""
    document = Document()
    document.add_heading("全部提示词", level=0)
    document.add_paragraph(f"项目：{project.get('title', '')}")
    document.add_paragraph(f"章节：第 {chapter.get('episode_no', '')} 集 {chapter.get('title', '')}")
    document.add_paragraph(f"视觉风格：{project.get('style', '')}")

    _append_prompt_section(document, "角色提示词", production.get("characters"), "turnaround_prompt")
    _append_prompt_section(document, "场景提示词", production.get("scenes"), "environment_prompt")
    _append_prompt_section(document, "道具提示词", production.get("props"), "description")

    document.add_heading("分镜提示词", level=1)
    shots = production.get("shots")
    if not isinstance(shots, list) or not shots:
        document.add_paragraph("暂无分镜提示词。")
    else:
        for index, shot in enumerate(shots, start=1):
            if not isinstance(shot, dict):
                continue
            shot_id = str(shot.get("id") or f"镜头 {index}")
            document.add_heading(f"{index:02d}. {shot_id}", level=2)
            document.add_paragraph(
                f"镜头信息：{shot.get('shot_size', '待确认')} / "
                f"{shot.get('camera_position', '待确认')} / "
                f"{shot.get('duration_seconds', '待确认')} 秒"
            )
            _append_prompt_field(document, "首帧提示词", shot.get("first_frame_prompt"))
            _append_prompt_field(document, "视频提示词", shot.get("video_prompt"))
            _append_prompt_field(document, "尾帧提示词", shot.get("last_frame_prompt"))
            _append_prompt_field(document, "负面提示词", shot.get("negative_prompt"))

    buffer = io.BytesIO()
    document.save(buffer)
    return buffer.getvalue()


def _build_script_document(project: dict[str, Any], chapter: dict[str, Any]) -> bytes:
    """Render the saved chapter as a portable Word screenplay document."""
    document = Document()
    document.add_heading(str(project.get("title") or "短剧项目"), level=0)
    document.add_heading(str(chapter.get("title") or "章节剧本"), level=1)
    outline = str(chapter.get("outline") or "").strip()
    if outline:
        document.add_heading("本章梗概", level=2)
        document.add_paragraph(outline)
    document.add_heading("剧本正文", level=2)
    content = str(chapter.get("content") or "").strip()
    for paragraph in content.splitlines():
        document.add_paragraph(paragraph)
    buffer = io.BytesIO()
    document.save(buffer)
    return buffer.getvalue()


def _build_production_archive(
    project: dict[str, Any], chapter: dict[str, Any], production: dict[str, Any]
) -> bytes:
    """Package the screenplay and storyboard prompt documents into one download."""
    project_title = str(project.get("title") or "短剧项目")
    chapter_title = str(chapter.get("title") or "章节")
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr(
            f"{project_title}-{chapter_title}-剧本.docx",
            _build_script_document(project, chapter),
        )
        archive.writestr(
            f"{project_title}-{chapter_title}-分镜提示词.docx",
            _build_prompt_document(project, chapter, production),
        )
    return buffer.getvalue()


def _append_prompt_section(document: Document, title: str, items: object, prompt_key: str) -> None:
    document.add_heading(title, level=1)
    if not isinstance(items, list) or not items:
        document.add_paragraph("暂无提示词。")
        return
    for index, item in enumerate(items, start=1):
        if not isinstance(item, dict):
            continue
        name = str(item.get("name") or item.get("id") or f"项目 {index}")
        document.add_heading(f"{index:02d}. {name}", level=2)
        _append_prompt_field(document, "提示词", item.get(prompt_key))


def _append_prompt_field(document: Document, label: str, value: object) -> None:
    text = str(value).strip() if value is not None else ""
    paragraph = document.add_paragraph()
    paragraph.add_run(f"{label}：").bold = True
    paragraph.add_run(text or "待确认")


def _extract_uploaded_script(payload: dict[str, Any]) -> str:
    filename = _required_text(payload, "filename")
    encoded = _required_text(payload, "content_base64")

    try:
        raw = base64.b64decode(encoded, validate=True)
    except (ValueError, binascii.Error) as error:
        raise ValueError("上传文件内容不是合法的 Base64。") from error

    if len(raw) > MAX_UPLOAD_BYTES:
        raise ValueError("剧本文档不能超过 12MB。")

    suffix = Path(filename).suffix.lower()
    ocr_mode = _optional_text(payload, "ocr_mode", "auto").lower()
    if ocr_mode not in {"auto", "always"}:
        raise ValueError("ocr_mode 必须是 auto 或 always。")
    if suffix == ".txt":
        script = _decode_text(raw)
    elif suffix == ".docx":
        script = _extract_docx_text(raw)
    elif suffix == ".pdf":
        script = _extract_pdf_text(raw, mode=ocr_mode)
    elif suffix in {".png", ".jpg", ".jpeg"}:
        script = extract_scanned_script(raw, suffix)
    elif suffix == ".doc":
        raise ValueError("暂不支持旧版 .doc，请另存为 .docx 后上传。")
    else:
        supported = "、".join(sorted(SUPPORTED_DOCUMENTS))
        raise ValueError(f"暂不支持该文件类型，请上传 {supported}。")

    script = script.strip()
    if not script:
        raise ValueError("文档中没有读取到可用文字。")
    return script


def _decode_text(raw: bytes) -> str:
    for encoding in ("utf-8-sig", "utf-8", "gb18030"):
        try:
            return raw.decode(encoding)
        except UnicodeDecodeError:
            continue
    raise ValueError("TXT 文件编码无法识别，请另存为 UTF-8 后上传。")


def _extract_docx_text(raw: bytes) -> str:
    try:
        with zipfile.ZipFile(io.BytesIO(raw)) as archive:
            xml_content = archive.read("word/document.xml")
    except (KeyError, zipfile.BadZipFile) as error:
        raise ValueError("Word 文件结构损坏或不是有效的 .docx。") from error

    try:
        root = ElementTree.fromstring(xml_content)
    except ElementTree.ParseError as error:
        raise ValueError("Word 文件内容无法解析。") from error

    namespace = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
    paragraphs: list[str] = []
    for paragraph in root.iter(f"{namespace}p"):
        text = "".join(node.text or "" for node in paragraph.iter(f"{namespace}t"))
        if text.strip():
            paragraphs.append(text.strip())
    return "\n".join(paragraphs)


def _extract_pdf_text(raw: bytes, mode: str = "auto") -> str:
    native_text = ""
    if mode != "always" and PdfReader is not None:
        try:
            reader = PdfReader(io.BytesIO(raw))
            pages = [page.extract_text() or "" for page in reader.pages]
            native_text = "\n\n".join(page.strip() for page in pages if page.strip())
        except Exception:
            native_text = ""
    if len(native_text.strip()) >= 40:
        return native_text
    return extract_scanned_script(raw, ".pdf")


def _offline_quick_script(brief: str, title: str) -> dict[str, str]:
    content = f"""第1集
1-1 夜 外 主场景
道具：关键线索（待确认）
出场人物：主角（待命名）

△ 【开场特写·快速推近】关键线索骤然闯入画面，环境声瞬间收紧；主角猛地停步，视线锁住前方。
△ 【中景跟拍】主角向线索靠近 → 伸手前短暂停顿 → 环顾四周，呼吸变得急促。
主角（内心独白）：这件事不该出现在这里。
△ 【近景微推】线索揭示与“{brief}”直接相关的异常，主角眼神由怀疑转为警觉。
△ 【反应特写】远处传来脚步声，主角迅速收起线索并转身，身体挡住关键物。
神秘人（画外音）：既然看见了，就别想当作什么都没发生。
△ 【低机位拉远】主角与黑暗中的来人形成对峙，冷光切开画面，风声与脚步声叠加。
△ 【结尾定格】神秘人抬手指向主角身后；主角回头，瞳孔骤缩，画面停在即将揭晓的瞬间。
"""
    return {
        "title": "第 1 集 · 线索出现",
        "outline": f"围绕“{brief}”直接制造冲突，主角发现异常线索，并在结尾遭遇新的威胁。",
        "content": content,
    }


def run_server(host: str, port: int, offline_demo: bool) -> None:
    if not (WEB_ROOT / "index.html").is_file():
        raise RuntimeError(f"找不到 Web 页面目录：{WEB_ROOT}")

    DramaWebHandler.offline_demo = offline_demo
    server = ThreadingHTTPServer((host, port), DramaWebHandler)
    print(f"FrameForge Studio Web 已启动：http://{host}:{port}")
    print("按 Ctrl+C 停止服务。")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n正在停止 Web 服务。")
    finally:
        server.server_close()


def main() -> None:
    parser = argparse.ArgumentParser(description="启动 FrameForge Studio Web 界面。")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--offline-demo", action="store_true")
    args = parser.parse_args()
    run_server(args.host, args.port, args.offline_demo)


def _required_text(payload: dict[str, Any], key: str) -> str:
    value = payload.get(key)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"字段 {key} 不能为空。")
    return value.strip()


def _optional_text(payload: dict[str, Any], key: str, default: str) -> str:
    value = payload.get(key)
    return value.strip() if isinstance(value, str) and value.strip() else default


def _positive_int(value: object, default: int) -> int:
    try:
        parsed = int(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return default
    return parsed if parsed > 0 else default


def _route_parts(path: str) -> list[str]:
    return [part for part in path.split("/") if part]


def _model_mode(payload: dict[str, Any]) -> str:
    config = payload.get("model_config")
    if config is None:
        return "manual"
    if not isinstance(config, dict):
        raise ValueError("model_config 必须是对象。")
    mode = _optional_text(config, "mode", "manual").lower()
    if mode not in {"manual", "cc_switch"}:
        raise ValueError("model_config.mode 必须是 manual 或 cc_switch。")
    return mode


def _client_base_url(client: Any) -> str:
    if hasattr(client, "base_url"):
        return str(client.base_url)
    if hasattr(client, "proxy_base_url"):
        return str(client.proxy_base_url)
    return ""


def _compact_provider_detail(detail: str) -> str:
    compact = " ".join(detail.split())
    return compact[:300] + ("..." if len(compact) > 300 else "")


def _cc_switch_runtime_payload() -> dict[str, Any]:
    try:
        return load_cc_switch_runtime(probe_proxy=True).to_public_dict()
    except RuntimeError as error:
        return {
            "available": False,
            "provider_id": "",
            "provider_name": "",
            "model": "",
            "wire_api": "",
            "provider_base_url": "",
            "reasoning_effort": "",
            "proxy_enabled": False,
            "listen_address": "",
            "listen_port": 0,
            "proxy_base_url": "",
            "proxy_running": False,
            "proxy_status": "unavailable",
            "provider_healthy": False,
            "provider_last_error": "",
            "protocol_endpoint": "",
            "db_path": "",
            "error": str(error),
        }


if __name__ == "__main__":
    main()
