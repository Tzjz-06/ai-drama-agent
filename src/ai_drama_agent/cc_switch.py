"""CC-Switch 本机运行态读取与代理探测。"""

from __future__ import annotations

import json
import os
import socket
import sqlite3
import tomllib
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Any


DEFAULT_CC_SWITCH_DB = Path.home() / ".cc-switch" / "cc-switch.db"


@dataclass(frozen=True)
class CCSwitchRuntime:
    provider_id: str
    provider_name: str
    model: str
    wire_api: str
    provider_base_url: str
    reasoning_effort: str
    proxy_enabled: bool
    listen_address: str
    listen_port: int
    proxy_running: bool
    proxy_status: str
    provider_healthy: bool
    provider_last_error: str
    db_path: str

    @property
    def proxy_base_url(self) -> str:
        return f"http://{self.listen_address}:{self.listen_port}"

    @property
    def protocol_endpoint(self) -> str:
        if self.wire_api == "responses":
            return f"{self.proxy_base_url}/v1/responses"
        return f"{self.proxy_base_url}/v1/chat/completions"

    def to_public_dict(self) -> dict[str, Any]:
        return {
            "available": True,
            "provider_id": self.provider_id,
            "provider_name": self.provider_name,
            "model": self.model,
            "wire_api": self.wire_api,
            "provider_base_url": self.provider_base_url,
            "reasoning_effort": self.reasoning_effort,
            "proxy_enabled": self.proxy_enabled,
            "listen_address": self.listen_address,
            "listen_port": self.listen_port,
            "proxy_base_url": self.proxy_base_url,
            "proxy_running": self.proxy_running,
            "proxy_status": self.proxy_status,
            "provider_healthy": self.provider_healthy,
            "provider_last_error": self.provider_last_error,
            "protocol_endpoint": self.protocol_endpoint,
            "db_path": self.db_path,
        }


def load_cc_switch_runtime(
    *,
    db_path: Path | None = None,
    probe_proxy: bool = True,
) -> CCSwitchRuntime:
    resolved_db = db_path or _resolve_db_path()
    if not resolved_db.is_file():
        raise RuntimeError(f"找不到 CC-Switch 配置数据库：{resolved_db}")

    connection = sqlite3.connect(resolved_db)
    try:
        provider_row = connection.execute(
            """
            SELECT id, name, settings_config
            FROM providers
            WHERE app_type = 'codex' AND is_current = 1
            ORDER BY created_at DESC
            LIMIT 1
            """
        ).fetchone()
        if provider_row is None:
            raise RuntimeError("CC-Switch 当前没有启用中的 Codex 供应商。")

        proxy_row = connection.execute(
            """
            SELECT enabled, listen_address, listen_port
            FROM proxy_config
            WHERE app_type = 'codex'
            LIMIT 1
            """
        ).fetchone()
        if proxy_row is None:
            raise RuntimeError("CC-Switch 缺少 Codex 代理配置。")

        provider_health_row = connection.execute(
            """
            SELECT is_healthy, last_error
            FROM provider_health
            WHERE provider_id = ? AND app_type = 'codex'
            LIMIT 1
            """,
            (str(provider_row[0]),),
        ).fetchone()
    finally:
        connection.close()

    provider_id = str(provider_row[0])
    provider_name = str(provider_row[1])
    settings_payload = _parse_settings_config(str(provider_row[2]))
    proxy_enabled = bool(int(proxy_row[0]))
    listen_address = str(proxy_row[1] or "127.0.0.1")
    listen_port = int(proxy_row[2] or 15721)

    proxy_status = "disabled"
    proxy_running = False
    if proxy_enabled and probe_proxy:
        proxy_running, proxy_status = _probe_proxy(
            f"http://{listen_address}:{listen_port}/health"
        )

    provider_healthy = True
    provider_last_error = ""
    if provider_health_row is not None:
        provider_healthy = bool(int(provider_health_row[0]))
        provider_last_error = str(provider_health_row[1] or "")

    runtime = CCSwitchRuntime(
        provider_id=provider_id,
        provider_name=provider_name,
        model=settings_payload["model"],
        wire_api=settings_payload["wire_api"],
        provider_base_url=settings_payload["provider_base_url"],
        reasoning_effort=settings_payload["reasoning_effort"],
        proxy_enabled=proxy_enabled,
        listen_address=listen_address,
        listen_port=listen_port,
        proxy_running=proxy_running,
        proxy_status=proxy_status,
        provider_healthy=provider_healthy,
        provider_last_error=provider_last_error,
        db_path=str(resolved_db),
    )
    return runtime


def _resolve_db_path() -> Path:
    override = os.getenv("AI_DRAMA_CC_SWITCH_DB", "").strip()
    return Path(override) if override else DEFAULT_CC_SWITCH_DB


def _parse_settings_config(settings_config: str) -> dict[str, str]:
    try:
        payload = json.loads(settings_config)
    except json.JSONDecodeError as error:
        raise RuntimeError("CC-Switch 当前供应商配置不是合法 JSON。") from error
    if not isinstance(payload, dict):
        raise RuntimeError("CC-Switch 当前供应商配置结构异常。")

    config_text = str(payload.get("config") or "")
    try:
        config = tomllib.loads(config_text) if config_text.strip() else {}
    except tomllib.TOMLDecodeError as error:
        raise RuntimeError("CC-Switch 当前供应商 TOML 配置无法解析。") from error

    if not isinstance(config, dict):
        raise RuntimeError("CC-Switch 当前供应商 TOML 配置结构异常。")

    model = str(config.get("model") or "").strip()
    if not model:
        raise RuntimeError("CC-Switch 当前供应商未声明模型名称。")

    reasoning_effort = str(config.get("model_reasoning_effort") or "").strip().lower()
    model_provider = str(config.get("model_provider") or "custom").strip()
    providers = config.get("model_providers")
    providers_dict = providers if isinstance(providers, dict) else {}
    provider_config = providers_dict.get(model_provider)
    if not isinstance(provider_config, dict):
        raise RuntimeError("CC-Switch 当前供应商缺少 model_providers 配置。")

    wire_api = str(provider_config.get("wire_api") or "").strip()
    provider_base_url = str(provider_config.get("base_url") or "").strip().rstrip("/")
    if not wire_api:
        raise RuntimeError("CC-Switch 当前供应商缺少 wire_api 配置。")
    if not provider_base_url:
        raise RuntimeError("CC-Switch 当前供应商缺少 base_url 配置。")

    return {
        "model": model,
        "wire_api": wire_api,
        "provider_base_url": provider_base_url,
        "reasoning_effort": reasoning_effort,
    }


def _probe_proxy(health_url: str) -> tuple[bool, str]:
    request = urllib.request.Request(health_url, method="GET")
    try:
        with urllib.request.urlopen(request, timeout=5) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as error:
        return False, f"http_{error.code}"
    except urllib.error.URLError as error:
        return False, _reason_text(error.reason)
    except (TimeoutError, socket.timeout):
        return False, "timeout"
    except json.JSONDecodeError:
        return True, "healthy"

    status = str(payload.get("status") or "healthy")
    return True, status


def _reason_text(reason: object) -> str:
    if isinstance(reason, str) and reason:
        return reason
    if isinstance(reason, OSError) and reason.strerror:
        return reason.strerror
    return str(reason) if reason else "unreachable"
