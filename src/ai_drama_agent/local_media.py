"""桌面版内置媒体任务执行器。

客户只在界面选择服务商并填写自己的 Key。任务线程和供应商协议均留在本机，
不依赖 Docker、Redis 或外置 Worker。
"""

from __future__ import annotations

import base64
import json
import mimetypes
import shutil
import subprocess
import threading
import time
import urllib.error
import urllib.request
import uuid
from pathlib import Path
from typing import Any
from urllib.parse import quote

import imageio_ffmpeg

from .store import LocalStore
from .paths import app_root

UPSTREAM_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/138.0.0.0 Safari/537.36"
)


class LocalMediaError(RuntimeError):
    """可直接展示给客户的媒体任务错误。"""


class LocalMediaRunner:
    """在桌面应用进程内执行图片和视频任务。"""

    def __init__(self, store: LocalStore) -> None:
        self.store = store
        self.media_root = store.path.parent / "media"
        self._migrate_legacy_media()

    def _migrate_legacy_media(self) -> None:
        legacy_root = app_root() / "data" / "media"
        if self.media_root.exists() or legacy_root == self.media_root or not legacy_root.is_dir():
            return
        try:
            self.media_root.parent.mkdir(parents=True, exist_ok=True)
            shutil.copytree(legacy_root, self.media_root)
        except OSError as error:
            raise LocalMediaError(f"无法迁移本地媒体文件：{legacy_root}") from error

    def submit(self, task: dict[str, Any], provider: dict[str, str] | None = None) -> None:
        thread = threading.Thread(
            target=self._run,
            args=(task, dict(provider) if provider is not None else None),
            name=f"media-{task['id']}",
            daemon=True,
        )
        thread.start()

    def test_connection(self, provider: dict[str, str]) -> dict[str, Any]:
        provider_id = provider["provider"]
        api_key = provider["api_key"]
        model = provider["model"]
        started_at = time.perf_counter()
        if provider_id in {"openai_image", "openai_sora"}:
            request = urllib.request.Request(
                f"https://api.openai.com/v1/models/{model}",
                headers={"Authorization": f"Bearer {api_key}", "User-Agent": UPSTREAM_USER_AGENT},
                method="GET",
            )
            self._open(request, timeout=20).read()
            status_code = 200
        elif provider_id == "compatible":
            endpoint = provider["api_url"]
            probe_endpoint = endpoint.rstrip("/")
            if probe_endpoint.endswith("/v1"):
                probe_endpoint = f"{probe_endpoint}/models/{quote(model, safe='')}"
            request = urllib.request.Request(
                probe_endpoint,
                headers={"Authorization": f"Bearer {api_key}", "User-Agent": UPSTREAM_USER_AGENT} if api_key else {"User-Agent": UPSTREAM_USER_AGENT},
                method="GET",
            )
            try:
                response = self._open(request, timeout=20)
                status_code = response.status
                response.close()
            except urllib.error.HTTPError as error:
                if error.code not in {405, 501}:
                    raise LocalMediaError(self._http_error("服务商", error)) from error
                status_code = error.code
        else:  # pragma: no cover - 由 Web 边界校验覆盖
            raise LocalMediaError("不支持的媒体服务商。")
        return {
            "model": model,
            "status_code": status_code,
            "elapsed_ms": round((time.perf_counter() - started_at) * 1000),
        }

    def media_file(self, task_id: str) -> Path:
        for extension in (".png", ".jpg", ".webp", ".mp4"):
            candidate = self.media_root / f"{task_id}{extension}"
            if candidate.is_file():
                return candidate
        raise FileNotFoundError(task_id)

    def _run(self, task: dict[str, Any], provider: dict[str, str] | None) -> None:
        user_id = str(task["user_id"])
        task_id = str(task["id"])
        try:
            if self.store.is_task_cancelled(user_id, task_id):
                return
            self.store.update_task(user_id, task_id, {"status": "running", "progress": 5, "message": "本地任务引擎已启动"})
            if task["type"] in {"frame_image", "asset_image"} and provider is not None:
                result = self._generate_image(task, provider)
            elif task["type"] == "video" and provider is not None:
                result = self._generate_video(task, provider)
            elif task["type"] == "merge":
                result = self._merge_video_clips(task)
            else:
                raise LocalMediaError("当前桌面版本暂不支持该媒体任务类型。")
            if self.store.is_task_cancelled(user_id, task_id):
                return
            self.store.update_task(
                user_id,
                task_id,
                {"status": "completed", "progress": 100, "message": "媒体生成完成", "result": result},
            )
        except Exception as error:
            if self.store.is_task_cancelled(user_id, task_id):
                return
            self.store.update_task(
                user_id,
                task_id,
                {"status": "failed", "progress": 0, "message": self._message(error)},
            )

    def _generate_image(self, task: dict[str, Any], provider: dict[str, str]) -> dict[str, str]:
        if provider["provider"] == "openai_image":
            response = self._json_request(
                "https://api.openai.com/v1/images/generations",
                provider["api_key"],
                {
                    "model": provider["model"],
                    "prompt": self._prompt(task),
                    "size": "1024x1792",
                    "quality": "standard",
                    "response_format": "url",
                },
            )
            data = response.get("data")
            if not isinstance(data, list) or not data or not isinstance(data[0], dict):
                raise LocalMediaError("OpenAI 图片服务没有返回图片结果。")
            image_url = data[0].get("url")
            if not isinstance(image_url, str) or not image_url:
                raise LocalMediaError("OpenAI 图片服务没有返回可下载的图片地址。")
            return self._download_public_media(str(task["id"]), image_url, ".png")
        if provider["provider"] == "compatible":
            return self._generate_openai_compatible(task, provider, "images/generations", ".png")
        return self._generate_compatible(task, provider, "图片")

    def _generate_video(self, task: dict[str, Any], provider: dict[str, str]) -> dict[str, str]:
        if provider["provider"] == "openai_sora":
            task_id = str(task["id"])
            self.store.update_task(str(task["user_id"]), task_id, {"progress": 10, "message": "正在提交 Sora 视频任务"})
            response = self._multipart_request(
                "https://api.openai.com/v1/videos",
                provider["api_key"],
                {
                    "model": provider["model"],
                    "prompt": self._prompt(task),
                    "size": "720x1280",
                    "seconds": self._video_seconds(task),
                },
            )
            video_id = response.get("id")
            if not isinstance(video_id, str) or not video_id:
                raise LocalMediaError("Sora 没有返回视频任务编号。")
            return self._wait_for_sora(task, provider["api_key"], video_id)
        if provider["provider"] == "compatible":
            return self._generate_openai_compatible(task, provider, "videos", ".mp4")
        return self._generate_compatible(task, provider, "视频")

    def _wait_for_sora(self, task: dict[str, Any], api_key: str, video_id: str) -> dict[str, str]:
        deadline = time.monotonic() + 25 * 60
        user_id = str(task["user_id"])
        task_id = str(task["id"])
        while time.monotonic() < deadline:
            request = urllib.request.Request(
                f"https://api.openai.com/v1/videos/{video_id}",
                headers={"Authorization": f"Bearer {api_key}", "User-Agent": UPSTREAM_USER_AGENT},
                method="GET",
            )
            response = self._read_json(self._open(request, timeout=30).read())
            status = str(response.get("status", ""))
            if status == "completed":
                content_request = urllib.request.Request(
                    f"https://api.openai.com/v1/videos/{video_id}/content",
                    headers={"Authorization": f"Bearer {api_key}", "User-Agent": UPSTREAM_USER_AGENT},
                    method="GET",
                )
                content = self._open(content_request, timeout=120).read()
                return self._write_media(task_id, content, ".mp4")
            if status in {"failed", "cancelled"}:
                message = response.get("error", {}).get("message") if isinstance(response.get("error"), dict) else ""
                raise LocalMediaError(str(message or "Sora 视频任务失败。"))
            progress = response.get("progress")
            if isinstance(progress, int):
                self.store.update_task(user_id, task_id, {"progress": max(10, min(95, progress)), "message": "Sora 正在生成视频"})
            time.sleep(2)
        raise LocalMediaError("Sora 视频生成超时，请稍后重新提交。")

    def _generate_compatible(self, task: dict[str, Any], provider: dict[str, str], label: str) -> dict[str, str]:
        payload: dict[str, Any] = {"prompt": self._prompt(task), "model": provider["model"]}
        task_payload = task.get("payload")
        if isinstance(task_payload, dict):
            for key in ("negative_prompt", "duration_seconds", "shot_id"):
                if key in task_payload:
                    payload[key] = task_payload[key]
        response = self._json_request(provider["api_url"], provider["api_key"], payload)
        url = self._response_url(response)
        if not url:
            raise LocalMediaError(f"{label}兼容接口没有返回 url。")
        return {"url": url}

    def _generate_openai_compatible(
        self,
        task: dict[str, Any],
        provider: dict[str, str],
        suffix: str,
        extension: str,
    ) -> dict[str, str]:
        endpoint = provider["api_url"].strip().rstrip("/")
        if endpoint.endswith("/v1"):
            endpoint = f"{endpoint}/{suffix}"
        elif endpoint.endswith(("/images/generations", "/videos")):
            pass
        else:
            endpoint = f"{endpoint}/v1/{suffix}"
        payload: dict[str, Any] = {"model": provider["model"], "prompt": self._prompt(task)}
        task_payload = task.get("payload")
        if isinstance(task_payload, dict):
            for key in ("negative_prompt", "duration_seconds", "shot_id"):
                if key in task_payload:
                    payload[key] = task_payload[key]
        response = self._json_request(endpoint, provider["api_key"], payload)
        url = self._response_url(response)
        if url:
            if url.startswith("data:"):
                return self._write_media(str(task["id"]), self._decode_data_url(url), extension)
            return self._download_public_media(str(task["id"]), url, extension)
        data = response.get("data")
        if isinstance(data, list) and data and isinstance(data[0], dict):
            encoded = data[0].get("b64_json")
            if isinstance(encoded, str) and encoded:
                try:
                    content = base64.b64decode(encoded, validate=True)
                except (ValueError, base64.binascii.Error) as error:
                    raise LocalMediaError("Provider returned invalid base64 media data.") from error
                return self._write_media(str(task["id"]), content, extension)
        media_id = response.get("id")
        if suffix == "videos" and isinstance(media_id, str) and media_id:
            return self._wait_for_compatible_video(task, provider, endpoint, media_id)
        raise LocalMediaError("Provider response did not contain a usable media result.")

    @staticmethod
    def _decode_data_url(value: str) -> bytes:
        try:
            _, encoded = value.split(",", 1)
            return base64.b64decode(encoded, validate=True)
        except (ValueError, base64.binascii.Error) as error:
            raise LocalMediaError("Provider returned an invalid data URL.") from error

    def _wait_for_compatible_video(
        self,
        task: dict[str, Any],
        provider: dict[str, str],
        endpoint: str,
        media_id: str,
    ) -> dict[str, str]:
        deadline = time.monotonic() + 25 * 60
        while time.monotonic() < deadline:
            request = urllib.request.Request(
                f"{endpoint}/{media_id}",
                headers={"Authorization": f"Bearer {provider['api_key']}", "User-Agent": UPSTREAM_USER_AGENT},
                method="GET",
            )
            response = self._read_json(self._open(request, timeout=30).read())
            status = str(response.get("status", "")).lower()
            if status in {"completed", "succeeded", "success"}:
                content_url = response.get("url")
                if not isinstance(content_url, str) or not content_url:
                    content_url = f"{endpoint}/{media_id}/content"
                return self._download_authorized_media(
                    str(task["id"]), content_url, provider["api_key"], ".mp4"
                )
            if status in {"failed", "cancelled", "canceled"}:
                raise LocalMediaError("Provider video task failed.")
            time.sleep(2)
        raise LocalMediaError("Provider video task timed out.")

    def _merge_video_clips(self, task: dict[str, Any]) -> dict[str, str]:
        payload = task.get("payload")
        clips = payload.get("clips") if isinstance(payload, dict) else None
        if not isinstance(clips, list) or not clips:
            raise LocalMediaError("请先完成至少一个视频片段，再开始合成。")
        paths: list[Path] = []
        for clip in clips:
            raw_url = clip.get("path") if isinstance(clip, dict) else None
            if not isinstance(raw_url, str):
                raise LocalMediaError("视频合成任务包含无效片段。")
            task_id = self._task_id_from_media_url(raw_url)
            if not task_id:
                raise LocalMediaError("仅支持合成当前桌面应用生成的视频片段。")
            paths.append(self.media_file(task_id))
        task_id = str(task["id"])
        self.media_root.mkdir(parents=True, exist_ok=True)
        output = self.media_root / f"{task_id}.mp4"
        command = [imageio_ffmpeg.get_ffmpeg_exe(), "-y"]
        for path in paths:
            command.extend(("-i", str(path)))
        command.extend((
            "-filter_complex",
            f"concat=n={len(paths)}:v=1:a=1[outv][outa]",
            "-map", "[outv]", "-map", "[outa]", "-c:v", "libx264", "-c:a", "aac", str(output),
        ))
        result = subprocess.run(command, capture_output=True, text=True, timeout=20 * 60, check=False)
        if result.returncode != 0:
            detail = (result.stderr or result.stdout).strip()
            raise LocalMediaError(f"视频合成失败：{detail[:500] or 'FFmpeg 执行失败。'}")
        return {"url": f"/api/media/tasks/{task_id}/file"}

    def _download_public_media(self, task_id: str, url: str, fallback_extension: str) -> dict[str, str]:
        response = self._open(
            urllib.request.Request(url, headers={"User-Agent": UPSTREAM_USER_AGENT}, method="GET"),
            timeout=120,
        )
        extension = mimetypes.guess_extension(response.headers.get_content_type()) or fallback_extension
        return self._write_media(task_id, response.read(), extension)

    def _download_authorized_media(
        self, task_id: str, url: str, api_key: str, fallback_extension: str
    ) -> dict[str, str]:
        request = urllib.request.Request(
            url,
            headers={"Authorization": f"Bearer {api_key}", "User-Agent": UPSTREAM_USER_AGENT},
            method="GET",
        )
        response = self._open(request, timeout=120)
        extension = mimetypes.guess_extension(response.headers.get_content_type()) or fallback_extension
        return self._write_media(task_id, response.read(), extension)

    def _write_media(self, task_id: str, content: bytes, extension: str) -> dict[str, str]:
        self.media_root.mkdir(parents=True, exist_ok=True)
        path = self.media_root / f"{task_id}{extension}"
        path.write_bytes(content)
        return {"url": f"/api/media/tasks/{task_id}/file"}

    @staticmethod
    def _prompt(task: dict[str, Any]) -> str:
        payload = task.get("payload")
        prompt = payload.get("prompt") if isinstance(payload, dict) else None
        if not isinstance(prompt, str) or not prompt.strip():
            raise LocalMediaError("媒体任务缺少提示词。")
        return prompt.strip()

    @staticmethod
    def _video_seconds(task: dict[str, Any]) -> str:
        payload = task.get("payload")
        seconds = payload.get("duration_seconds") if isinstance(payload, dict) else None
        duration = float(seconds) if isinstance(seconds, int | float) else 4.0
        for supported in (4, 8, 12, 20):
            if duration <= supported:
                return str(supported)
        return "20"

    @staticmethod
    def _response_url(payload: dict[str, Any]) -> str:
        value = payload.get("url")
        if isinstance(value, str) and value.strip():
            return value.strip()
        data = payload.get("data")
        if isinstance(data, list) and data and isinstance(data[0], dict):
            value = data[0].get("url")
            if isinstance(value, str) and value.strip():
                return value.strip()
        return ""

    @staticmethod
    def _task_id_from_media_url(url: str) -> str:
        parts = [part for part in url.split("?")[0].split("/") if part]
        if len(parts) == 5 and parts[:3] == ["api", "media", "tasks"] and parts[-1] == "file":
            return parts[3]
        return ""

    def _json_request(self, url: str, api_key: str, payload: dict[str, Any]) -> dict[str, Any]:
        request = urllib.request.Request(
            url,
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {api_key}",
                "User-Agent": UPSTREAM_USER_AGENT,
            },
            method="POST",
        )
        return self._read_json(self._open(request, timeout=120).read())

    def _multipart_request(self, url: str, api_key: str, fields: dict[str, str]) -> dict[str, Any]:
        boundary = f"----Jiaozi{uuid.uuid4().hex}"
        chunks: list[bytes] = []
        for key, value in fields.items():
            chunks.extend((
                f"--{boundary}\r\n".encode(),
                f'Content-Disposition: form-data; name="{key}"\r\n\r\n'.encode(),
                value.encode("utf-8"),
                b"\r\n",
            ))
        chunks.append(f"--{boundary}--\r\n".encode())
        request = urllib.request.Request(
            url,
            data=b"".join(chunks),
            headers={
                "Content-Type": f"multipart/form-data; boundary={boundary}",
                "Authorization": f"Bearer {api_key}",
                "User-Agent": UPSTREAM_USER_AGENT,
            },
            method="POST",
        )
        return self._read_json(self._open(request, timeout=120).read())

    @staticmethod
    def _read_json(content: bytes) -> dict[str, Any]:
        try:
            value = json.loads(content.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as error:
            raise LocalMediaError("服务商返回了无法识别的响应。") from error
        if not isinstance(value, dict):
            raise LocalMediaError("服务商返回了无效响应。")
        return value

    @staticmethod
    def _open(request: urllib.request.Request, timeout: int):
        try:
            return urllib.request.urlopen(request, timeout=timeout)
        except urllib.error.HTTPError as error:
            raise LocalMediaError(LocalMediaRunner._http_error("服务商", error)) from error
        except urllib.error.URLError as error:
            raise LocalMediaError(f"无法连接服务商：{error.reason}") from error

    @staticmethod
    def _http_error(label: str, error: urllib.error.HTTPError) -> str:
        detail = error.read(2048).decode("utf-8", errors="replace").strip()
        return f"{label}返回 HTTP {error.code}{f'：{detail}' if detail else ''}"

    @staticmethod
    def _message(error: Exception) -> str:
        return str(error) if isinstance(error, LocalMediaError) else "媒体任务执行失败，请检查网络和 API 配置。"
