"""本地 Web 应用的账户、项目和章节持久化。"""

from __future__ import annotations

import hashlib
import json
import os
import secrets
import shutil
import threading
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .paths import app_data_root, app_root


class StoreError(ValueError):
    """可直接展示给用户的本地数据错误。"""


class AuthError(StoreError):
    """身份认证或授权失败。"""


class LocalStore:
    """用单个 JSON 文件保存本地账户和创作项目。"""

    def __init__(self, path: Path | None = None) -> None:
        configured_path = os.getenv("AI_DRAMA_DATA_FILE")
        if path is not None:
            self.path = path
        elif configured_path:
            self.path = Path(configured_path)
        else:
            self.path = app_data_root() / "app_state.json"
            self._migrate_legacy_state()
        self._lock = threading.RLock()
        self._data = self._load()
        self._data.setdefault("tasks", {})
        self._data.setdefault("sessions", {})

    def _migrate_legacy_state(self) -> None:
        """Copy an install-directory state file once into the user data path."""
        legacy_path = app_root() / "data" / "app_state.json"
        if self.path.exists() or legacy_path == self.path or not legacy_path.is_file():
            return
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(legacy_path, self.path)
        except OSError as error:
            raise StoreError(f"无法迁移本地数据文件：{legacy_path}") from error

    def register(self, username: str, email: str, password: str) -> dict[str, str]:
        username = username.strip()
        email = email.strip().lower()
        if len(username) < 2:
            raise StoreError("用户名至少需要 2 个字符。")
        if len(password) < 6:
            raise StoreError("密码至少需要 6 个字符。")
        with self._lock:
            users = self._data["users"]
            if any(user["username"].lower() == username.lower() for user in users.values()):
                raise StoreError("用户名已存在，请换一个。")
            if email and any(user.get("email", "").lower() == email for user in users.values()):
                raise StoreError("邮箱已注册，请直接登录。")
            user_id = f"user_{secrets.token_hex(8)}"
            salt = secrets.token_bytes(16)
            users[user_id] = {
                "id": user_id,
                "username": username,
                "email": email,
                "password_hash": _hash_password(password, salt),
                "password_salt": salt.hex(),
                "created_at": _now(),
            }
            self._save()
            return _public_user(users[user_id])

    def login(self, identity: str, password: str) -> tuple[str, dict[str, str]]:
        identity = identity.strip().lower()
        with self._lock:
            user = next(
                (
                    candidate
                    for candidate in self._data["users"].values()
                    if candidate["username"].lower() == identity or candidate.get("email", "").lower() == identity
                ),
                None,
            )
            if user is None or not _verify_password(password, user["password_hash"], user["password_salt"]):
                raise AuthError("账号或密码不正确。")
            token = secrets.token_urlsafe(32)
            self._data["sessions"][_session_key(token)] = {"user_id": user["id"], "expires_at": time.time() + 60 * 60 * 24 * 7}
            self._save()
            return token, _public_user(user)

    def logout(self, token: str) -> None:
        with self._lock:
            if self._data["sessions"].pop(_session_key(token), None) is not None:
                self._save()

    def user_for_token(self, token: str) -> dict[str, str]:
        with self._lock:
            session = self._data["sessions"].get(_session_key(token))
            if not isinstance(session, dict):
                raise AuthError("登录已失效，请重新登录。")
            expires_at = session.get("expires_at")
            user_id = session.get("user_id")
            if not isinstance(expires_at, (int, float)) or expires_at <= time.time() or not isinstance(user_id, str):
                self._data["sessions"].pop(_session_key(token), None)
                self._save()
                raise AuthError("登录已失效，请重新登录。")
            user = self._data["users"].get(user_id)
            if user is None:
                raise AuthError("用户不存在，请重新登录。")
            return _public_user(user)

    def list_projects(self, user_id: str) -> list[dict[str, Any]]:
        with self._lock:
            projects = [project for project in self._data["projects"].values() if project["user_id"] == user_id]
            return [_project_summary(project) for project in sorted(projects, key=lambda item: item["updated_at"], reverse=True)]

    def create_project(self, user_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        title = _text(payload, "title", "未命名短剧")
        project_id = f"project_{secrets.token_hex(8)}"
        now = _now()
        project = {
            "id": project_id,
            "user_id": user_id,
            "title": title,
            "description": _text(payload, "description", ""),
            "style": _text(payload, "style", "电影感二维国漫"),
            "genre": _text(payload, "genre", "短剧"),
            "aspect_ratio": _text(payload, "aspect_ratio", "9:16"),
            "status": "draft",
            "created_at": now,
            "updated_at": now,
            "chapters": [],
        }
        with self._lock:
            self._data["projects"][project_id] = project
            self._save()
            return _project_summary(project)

    def get_project(self, user_id: str, project_id: str) -> dict[str, Any]:
        with self._lock:
            project = self._owned_project(user_id, project_id)
            return _project_detail(project)

    def update_project(self, user_id: str, project_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        with self._lock:
            project = self._owned_project(user_id, project_id)
            for key in ("title", "description", "style", "genre", "aspect_ratio"):
                if isinstance(payload.get(key), str) and payload[key].strip():
                    project[key] = payload[key].strip()
            project["updated_at"] = _now()
            self._save()
            return _project_summary(project)

    def delete_project(self, user_id: str, project_id: str) -> None:
        with self._lock:
            self._owned_project(user_id, project_id)
            del self._data["projects"][project_id]
            self._data["tasks"] = {
                task_id: task
                for task_id, task in self._data["tasks"].items()
                if task.get("project_id") != project_id
            }
            self._save()

    def create_chapter(self, user_id: str, project_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        with self._lock:
            project = self._owned_project(user_id, project_id)
            chapters = project["chapters"]
            episode_no = len(chapters) + 1
            chapter = {
                "id": f"chapter_{secrets.token_hex(8)}",
                "title": _text(payload, "title", f"第 {episode_no} 集"),
                "episode_no": episode_no,
                "outline": _text(payload, "outline", ""),
                "content": _text(payload, "content", ""),
                "status": "draft",
                "is_locked": False,
                "production": None,
                "created_at": _now(),
                "updated_at": _now(),
            }
            chapters.append(chapter)
            project["updated_at"] = _now()
            self._save()
            return dict(chapter)

    def get_chapter(self, user_id: str, project_id: str, chapter_id: str) -> dict[str, Any]:
        with self._lock:
            project = self._owned_project(user_id, project_id)
            return dict(self._owned_chapter(project, chapter_id))

    def update_chapter(self, user_id: str, project_id: str, chapter_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        with self._lock:
            project = self._owned_project(user_id, project_id)
            chapter = self._owned_chapter(project, chapter_id)
            for key in ("title", "outline", "content", "status"):
                if isinstance(payload.get(key), str):
                    chapter[key] = payload[key].strip()
            if isinstance(payload.get("is_locked"), bool):
                chapter["is_locked"] = payload["is_locked"]
            chapter["updated_at"] = _now()
            project["updated_at"] = chapter["updated_at"]
            self._save()
            return dict(chapter)

    def save_production(self, user_id: str, project_id: str, chapter_id: str, production: dict[str, Any]) -> dict[str, Any]:
        with self._lock:
            project = self._owned_project(user_id, project_id)
            chapter = self._owned_chapter(project, chapter_id)
            chapter["production"] = production
            chapter["status"] = "completed"
            chapter["updated_at"] = _now()
            project["status"] = "completed"
            project["updated_at"] = chapter["updated_at"]
            self._save()
            return dict(chapter)

    def update_production_asset(
        self,
        user_id: str,
        project_id: str,
        chapter_id: str,
        asset_type: str,
        asset_id: str,
        payload: dict[str, Any],
    ) -> dict[str, Any]:
        editable_fields = {
            "characters": ("name", "role", "appearance", "costume", "turnaround_prompt"),
            "scenes": ("name", "location", "time", "lighting", "layout", "environment_prompt"),
            "props": ("name", "description", "owner"),
        }
        fields = editable_fields.get(asset_type)
        if fields is None:
            raise ValueError("不支持的资产类型。")

        with self._lock:
            project = self._owned_project(user_id, project_id)
            chapter = self._owned_chapter(project, chapter_id)
            production = chapter.get("production")
            if not isinstance(production, dict):
                raise StoreError("当前章节还没有可编辑的制作包。")
            asset_list = production.get(asset_type)
            if not isinstance(asset_list, list):
                raise StoreError("当前章节没有此类资产。")
            asset = next(
                (item for item in asset_list if isinstance(item, dict) and item.get("id") == asset_id),
                None,
            )
            if asset is None:
                raise StoreError("资产不存在。")
            if "name" in payload and (
                not isinstance(payload["name"], str) or not payload["name"].strip()
            ):
                raise ValueError("资产名称不能为空。")
            for key in fields:
                if isinstance(payload.get(key), str):
                    asset[key] = payload[key].strip()
            chapter["updated_at"] = _now()
            project["updated_at"] = chapter["updated_at"]
            self._save()
            return dict(chapter)

    def update_shot_prompts(
        self,
        user_id: str,
        project_id: str,
        chapter_id: str,
        shot_id: str,
        payload: dict[str, Any],
    ) -> dict[str, Any]:
        editable_fields = (
            "first_frame_prompt",
            "video_prompt",
            "last_frame_prompt",
            "negative_prompt",
        )
        with self._lock:
            project = self._owned_project(user_id, project_id)
            chapter = self._owned_chapter(project, chapter_id)
            production = chapter.get("production")
            if not isinstance(production, dict):
                raise StoreError("当前章节还没有可编辑的制作包。")
            shots = production.get("shots")
            if not isinstance(shots, list):
                raise StoreError("当前章节没有分镜。")
            shot = next(
                (item for item in shots if isinstance(item, dict) and item.get("id") == shot_id),
                None,
            )
            if shot is None:
                raise StoreError("分镜不存在。")
            for key in editable_fields:
                if isinstance(payload.get(key), str):
                    shot[key] = payload[key].strip()
            chapter["updated_at"] = _now()
            project["updated_at"] = chapter["updated_at"]
            self._save()
            return dict(chapter)

    def _owned_project(self, user_id: str, project_id: str) -> dict[str, Any]:
        project = self._data["projects"].get(project_id)
        if project is None or project["user_id"] != user_id:
            raise StoreError("项目不存在或无权访问。")
        return project

    @staticmethod
    def _owned_chapter(project: dict[str, Any], chapter_id: str) -> dict[str, Any]:
        chapter = next((item for item in project["chapters"] if item["id"] == chapter_id), None)
        if chapter is None:
            raise StoreError("章节不存在。")
        return chapter

    def _load(self) -> dict[str, Any]:
        if not self.path.is_file():
            return {"users": {}, "projects": {}}
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as error:
            raise StoreError(f"本地数据文件无法读取：{self.path}") from error
        if not isinstance(data, dict) or not isinstance(data.get("users"), dict) or not isinstance(data.get("projects"), dict):
            raise StoreError("本地数据文件结构损坏，请备份后删除 data/app_state.json。")
        return data

    def _save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temp_path = self.path.with_suffix(".tmp")
        temp_path.write_text(json.dumps(self._data, ensure_ascii=False, indent=2), encoding="utf-8")
        temp_path.replace(self.path)


def _hash_password(password: str, salt: bytes) -> str:
    return hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, 180_000).hex()


def _session_key(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def _verify_password(password: str, expected: str, salt_hex: str) -> bool:
    try:
        salt = bytes.fromhex(salt_hex)
    except ValueError:
        return False
    return secrets.compare_digest(_hash_password(password, salt), expected)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _public_user(user: dict[str, Any]) -> dict[str, str]:
    return {"id": str(user["id"]), "username": str(user["username"]), "email": str(user.get("email", ""))}


def _text(payload: dict[str, Any], key: str, default: str) -> str:
    value = payload.get(key)
    return value.strip() if isinstance(value, str) and value.strip() else default


def _project_summary(project: dict[str, Any]) -> dict[str, Any]:
    chapters = project.get("chapters", [])
    latest = chapters[-1] if chapters else None
    production = latest.get("production") if isinstance(latest, dict) else None
    return {
        key: project[key]
        for key in ("id", "title", "description", "style", "genre", "aspect_ratio", "status", "created_at", "updated_at")
    } | {
        "chapter_count": len(chapters),
        "latest_chapter_title": latest.get("title", "") if latest else "",
        "character_count": len(production.get("characters", [])) if isinstance(production, dict) else 0,
        "scene_count": len(production.get("scenes", [])) if isinstance(production, dict) else 0,
        "shot_count": len(production.get("shots", [])) if isinstance(production, dict) else 0,
    }


def _project_detail(project: dict[str, Any]) -> dict[str, Any]:
    return dict(project)
