"""模型适配器和离线动态解析适配器。"""

from __future__ import annotations

import json
import os
import re
import socket
from http.client import RemoteDisconnected
import urllib.error
import urllib.request
from dataclasses import dataclass
from html import unescape
from typing import Any, Protocol

from .cc_switch import CCSwitchRuntime
from .reasoner import RuleBasedClient

ALLOWED_REASONING_EFFORTS = {"", "auto", "minimal", "low", "medium", "high", "xhigh"}


class LLMClient(Protocol):
    def complete_json(self, system_prompt: str, user_prompt: str) -> dict[str, Any]:
        """返回模型生成的 JSON 对象。"""


@dataclass
class OpenAICompatibleClient:
    api_key: str
    base_url: str
    model: str
    timeout_seconds: int = 180
    reasoning_effort: str = ""

    @classmethod
    def from_environment(cls) -> "OpenAICompatibleClient":
        return cls.from_config(
            api_key=os.getenv("AI_DRAMA_API_KEY", ""),
            base_url=os.getenv("AI_DRAMA_BASE_URL", "https://api.openai.com/v1"),
            model=os.getenv("AI_DRAMA_MODEL", "gpt-4.1"),
            reasoning_effort=os.getenv("AI_DRAMA_REASONING_EFFORT", ""),
        )

    @classmethod
    def from_config(
        cls,
        api_key: str,
        base_url: str,
        model: str,
        reasoning_effort: str = "",
    ) -> "OpenAICompatibleClient":
        if not api_key.strip():
            raise RuntimeError(
                "尚未配置真实模型 API Key。请在左侧模型设置中填写 API Key；只有显式启动 --offline-demo 才会使用离线调试模式。"
            )
        if not base_url.strip():
            raise RuntimeError("模型 Base URL 不能为空。")
        if not model.strip():
            raise RuntimeError("模型名称不能为空。")
        normalized_effort = reasoning_effort.strip().lower()
        if normalized_effort not in ALLOWED_REASONING_EFFORTS:
            raise RuntimeError("推理强度必须是 auto、minimal、low、medium、high 或 xhigh。")
        return cls(
            api_key=api_key.strip(),
            base_url=base_url.strip().rstrip("/"),
            model=model.strip(),
            reasoning_effort=normalized_effort,
        )

    def complete_json(self, system_prompt: str, user_prompt: str) -> dict[str, Any]:
        payload = {
            "model": self.model,
            "temperature": 0.2,
            "response_format": {"type": "json_object"},
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
        }
        if self.reasoning_effort not in {"", "auto"}:
            payload["reasoning_effort"] = self.reasoning_effort
        request = urllib.request.Request(
            f"{self.base_url}/chat/completions",
            data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
            headers=_default_json_headers(self.api_key),
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=self.timeout_seconds) as response:
                body = json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as error:
            detail = error.read().decode("utf-8", errors="replace")
            raise RuntimeError(_format_http_error(error.code, detail)) from error
        except urllib.error.URLError as error:
            raise RuntimeError(f"模型接口连接失败: {error.reason}") from error
        except RemoteDisconnected as error:
            raise RuntimeError("模型接口连接被远端提前断开，请检查上游供应商或中转站稳定性。") from error
        except (TimeoutError, socket.timeout) as error:
            raise RuntimeError("模型接口连接超时，请检查 Base URL、网络或供应商服务状态。") from error

        return _parse_json_object(
            _extract_chat_completion_text(body),
            "模型",
        )


@dataclass
class CCSwitchResponsesClient:
    proxy_base_url: str
    model: str
    provider_name: str
    wire_api: str
    timeout_seconds: int = 180
    reasoning_effort: str = ""

    @classmethod
    def from_runtime(cls, runtime: CCSwitchRuntime) -> "CCSwitchResponsesClient":
        if not runtime.proxy_enabled:
            raise RuntimeError("CC-Switch Codex 代理未启用，请先在 CC-Switch 中开启本地代理。")
        if not runtime.proxy_running:
            raise RuntimeError(
                f"CC-Switch 本地代理不可用：{runtime.proxy_base_url}（{runtime.proxy_status}）。"
            )
        if runtime.wire_api != "responses":
            raise RuntimeError(
                f"当前 CC-Switch 协议是 {runtime.wire_api}，饺子短剧暂时只支持 Responses 协议。"
            )
        if not runtime.model:
            raise RuntimeError("CC-Switch 当前供应商没有可用模型。")
        return cls(
            proxy_base_url=runtime.proxy_base_url,
            model=runtime.model,
            provider_name=runtime.provider_name,
            wire_api=runtime.wire_api,
            reasoning_effort=runtime.reasoning_effort,
        )

    def complete_json(self, system_prompt: str, user_prompt: str) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "model": self.model,
            "instructions": system_prompt,
            "input": user_prompt,
            "text": {"format": {"type": "json_object"}},
        }
        if self.reasoning_effort not in {"", "auto"}:
            payload["reasoning"] = {"effort": self.reasoning_effort}
        request = urllib.request.Request(
            f"{self.proxy_base_url}/v1/responses",
            data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
            headers=_default_json_headers(),
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=self.timeout_seconds) as response:
                body = json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as error:
            detail = error.read().decode("utf-8", errors="replace")
            raise RuntimeError(_format_http_error(error.code, detail)) from error
        except urllib.error.URLError as error:
            raise RuntimeError(f"CC-Switch 代理连接失败: {error.reason}") from error
        except RemoteDisconnected as error:
            raise RuntimeError("CC-Switch 代理连接被远端提前断开，请检查本地代理或上游供应商稳定性。") from error
        except (TimeoutError, socket.timeout) as error:
            raise RuntimeError("CC-Switch 代理调用超时，请检查本地代理或上游供应商状态。") from error

        return _parse_json_object(
            _extract_responses_json_text(body),
            "CC-Switch Responses 接口",
        )


@dataclass
class CCSwitchChatCompletionsClient:
    proxy_base_url: str
    model: str
    provider_name: str
    wire_api: str
    timeout_seconds: int = 180
    reasoning_effort: str = ""

    @classmethod
    def from_runtime(cls, runtime: CCSwitchRuntime) -> "CCSwitchChatCompletionsClient":
        if not runtime.proxy_enabled:
            raise RuntimeError("CC-Switch Codex 代理未启用，请先在 CC-Switch 中开启本地代理。")
        if not runtime.proxy_running:
            raise RuntimeError(
                f"CC-Switch 本地代理不可用：{runtime.proxy_base_url}（{runtime.proxy_status}）。"
            )
        if runtime.wire_api not in {"chat_completions", "chat-completions"}:
            raise RuntimeError(
                f"当前 CC-Switch 协议是 {runtime.wire_api}，无法按 Chat Completions 协议调用。"
            )
        if not runtime.model:
            raise RuntimeError("CC-Switch 当前供应商没有可用模型。")
        return cls(
            proxy_base_url=runtime.proxy_base_url,
            model=runtime.model,
            provider_name=runtime.provider_name,
            wire_api=runtime.wire_api,
            reasoning_effort=runtime.reasoning_effort,
        )

    def complete_json(self, system_prompt: str, user_prompt: str) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "model": self.model,
            "temperature": 0.2,
            "response_format": {"type": "json_object"},
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
        }
        if self.reasoning_effort not in {"", "auto"}:
            payload["reasoning_effort"] = self.reasoning_effort
        request = urllib.request.Request(
            f"{self.proxy_base_url}/v1/chat/completions",
            data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
            headers=_default_json_headers(),
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=self.timeout_seconds) as response:
                body = json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as error:
            detail = error.read().decode("utf-8", errors="replace")
            raise RuntimeError(_format_http_error(error.code, detail)) from error
        except urllib.error.URLError as error:
            raise RuntimeError(f"CC-Switch 代理连接失败: {error.reason}") from error
        except RemoteDisconnected as error:
            raise RuntimeError("CC-Switch 代理连接被远端提前断开，请检查本地代理或上游供应商稳定性。") from error
        except (TimeoutError, socket.timeout) as error:
            raise RuntimeError("CC-Switch 代理调用超时，请检查本地代理或上游供应商状态。") from error

        return _parse_json_object(
            _extract_chat_completion_text(body),
            "CC-Switch Chat Completions 接口",
        )


def build_cc_switch_client(
    runtime: CCSwitchRuntime,
) -> "CCSwitchResponsesClient | CCSwitchChatCompletionsClient":
    if runtime.wire_api == "responses":
        return CCSwitchResponsesClient.from_runtime(runtime)
    if runtime.wire_api in {"chat_completions", "chat-completions"}:
        return CCSwitchChatCompletionsClient.from_runtime(runtime)
    raise RuntimeError(
        f"当前 CC-Switch 协议是 {runtime.wire_api}，饺子短剧暂不支持该协议。"
    )


def _strip_json_fence(content: str) -> str:
    cleaned = content.strip().lstrip("\ufeff")
    if cleaned.startswith("```") and cleaned.endswith("```"):
        lines = cleaned.splitlines()
        return "\n".join(lines[1:-1]).strip()
    return cleaned


def _parse_json_object(content: str, source: str) -> dict[str, Any]:
    cleaned = _strip_json_fence(content)
    decoder = json.JSONDecoder(strict=False)
    try:
        parsed = decoder.decode(cleaned)
    except json.JSONDecodeError as initial_error:
        candidates: list[tuple[int, dict[str, Any]]] = []
        for match in re.finditer(r"\{", cleaned):
            try:
                candidate, end = decoder.raw_decode(cleaned, match.start())
            except json.JSONDecodeError:
                continue
            if isinstance(candidate, dict):
                candidates.append((end - match.start(), candidate))
        if candidates:
            return max(candidates, key=lambda item: item[0])[1]

        detail = f"第 {initial_error.lineno} 行第 {initial_error.colno} 列"
        if _looks_like_truncated_json(cleaned, initial_error):
            raise RuntimeError(
                f"{source}返回的 JSON 内容不完整（{detail}），上游供应商可能截断了输出。"
            ) from initial_error
        raise RuntimeError(f"{source}未返回合法 JSON（{detail}）。") from initial_error
    if not isinstance(parsed, dict):
        raise RuntimeError(f"{source}返回的 JSON 顶层结构不是对象。")
    return parsed


def _looks_like_truncated_json(content: str, error: json.JSONDecodeError) -> bool:
    if error.msg.startswith("Unterminated string"):
        return True
    if error.pos >= max(0, len(content) - 2):
        return True
    return content.count("{") > content.count("}") or content.count("[") > content.count("]")


def _extract_responses_json_text(payload: dict[str, Any]) -> str:
    output_text = payload.get("output_text")
    if isinstance(output_text, str) and output_text.strip():
        return output_text

    output = payload.get("output")
    if isinstance(output, list):
        parts: list[str] = []
        for item in output:
            if not isinstance(item, dict):
                continue
            content = item.get("content")
            if not isinstance(content, list):
                continue
            for block in content:
                if not isinstance(block, dict):
                    continue
                text = block.get("text")
                if isinstance(text, str) and text.strip():
                    parts.append(text)
        if parts:
            return "\n".join(parts)

    raise RuntimeError("CC-Switch Responses 响应缺少可解析的 output_text。")


def _extract_chat_completion_text(payload: dict[str, Any]) -> str:
    """Read text from OpenAI-compatible chat responses with common relay variants."""
    choices = payload.get("choices")
    if isinstance(choices, list) and choices:
        first_choice = choices[0]
        if isinstance(first_choice, dict):
            message = first_choice.get("message")
            if isinstance(message, dict):
                content = message.get("content")
                if isinstance(content, str) and content.strip():
                    return content
                if isinstance(content, list):
                    parts = [
                        block.get("text")
                        for block in content
                        if isinstance(block, dict) and isinstance(block.get("text"), str)
                    ]
                    if parts:
                        return "\n".join(parts)
            text = first_choice.get("text")
            if isinstance(text, str) and text.strip():
                return text

    output_text = payload.get("output_text")
    if isinstance(output_text, str) and output_text.strip():
        return output_text

    raise RuntimeError(
        "模型响应中未找到可解析文本（支持 choices[0].message.content、choices[0].text 或 output_text）。"
    )


def _default_json_headers(api_key: str = "") -> dict[str, str]:
    headers = {
        "Content-Type": "application/json",
        "Accept": "application/json",
        # Some upstream relays block Python's default urllib user-agent.
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/138.0.0.0 Safari/537.36",
    }
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
    return headers


def _format_http_error(status_code: int, detail: str) -> str:
    message, hint_override = _extract_error_message(detail)
    suffix = f"：{message}" if message else "。"
    hints = {
        401: "请检查 API Key 是否正确或已过期",
        403: "当前 API Key 没有访问该模型或接口的权限",
        404: "请检查 Base URL 和模型名称是否正确",
        429: "请求频率或账户额度已达到供应商限制",
        522: "上游站点连接超时，常见于中转站或源站网络不稳定",
        524: "上游站点处理超时，常见于长提示词或中转站处理窗口过短",
    }
    hint = hint_override or hints.get(status_code)
    return f"模型接口返回 HTTP {status_code}{suffix}{f' {hint}。' if hint else ''}"


def _extract_error_message(detail: str) -> tuple[str, str | None]:
    message = ""
    try:
        payload = json.loads(detail)
        error = payload.get("error") if isinstance(payload, dict) else None
        if isinstance(error, dict):
            message = str(error.get("message") or "").strip()
        elif isinstance(error, str):
            message = error.strip()
        if not message and isinstance(payload, dict):
            message = str(payload.get("message") or "").strip()
    except json.JSONDecodeError:
        message = detail.strip()
    return _sanitize_provider_message(message)


def _sanitize_provider_message(message: str) -> tuple[str, str | None]:
    cleaned = message.strip()
    if not cleaned:
        return "", None

    if "cause:" in cleaned.lower():
        prefix, separator, cause = cleaned.rpartition("cause:")
        summarized_cause, hint = _sanitize_provider_message(cause)
        if summarized_cause:
            merged = f"{prefix.strip()} {separator} {summarized_cause}".strip()
            return _truncate_message(merged), hint

    if _looks_like_html(cleaned):
        return _summarize_html_error(cleaned)

    return _truncate_message(cleaned), None


def _looks_like_html(message: str) -> bool:
    lowered = message.lower()
    return "<html" in lowered or "<!doctype html" in lowered or "<title>" in lowered


def _summarize_html_error(message: str) -> tuple[str, str | None]:
    title_match = re.search(r"<title>(.*?)</title>", message, flags=re.IGNORECASE | re.DOTALL)
    title = _plain_text(title_match.group(1)) if title_match else ""

    paragraph_matches = re.findall(r"<p[^>]*>(.*?)</p>", message, flags=re.IGNORECASE | re.DOTALL)
    paragraphs = [_plain_text(item) for item in paragraph_matches]
    paragraphs = [item for item in paragraphs if item]

    merged_text = " ".join([title, *paragraphs]).strip()
    host_match = re.search(r"\(([^)]+)\)\s+has banned your access", merged_text, flags=re.IGNORECASE)
    host = host_match.group(1) if host_match else ""

    if "cloudflare" in merged_text.lower() and (
        "error 1010" in merged_text.lower() or "access denied" in merged_text.lower()
    ):
        site = f"上游站点 {host}" if host else "上游站点"
        message = (
            f"{site} 被 Cloudflare 拒绝访问（Error 1010 / Access denied），"
            "通常是源站按浏览器签名、IP 或地区触发风控。"
        )
        hint = "这更像上游风控或封禁，不是饺子短剧本地配置错误"
        return message, hint

    summary = title or (paragraphs[0] if paragraphs else "上游返回了 HTML 错误页。")
    return _truncate_message(summary), None


def _plain_text(value: str) -> str:
    without_scripts = re.sub(r"<script.*?</script>", " ", value, flags=re.IGNORECASE | re.DOTALL)
    without_styles = re.sub(r"<style.*?</style>", " ", without_scripts, flags=re.IGNORECASE | re.DOTALL)
    without_comments = re.sub(r"<!--.*?-->", " ", without_styles, flags=re.DOTALL)
    without_tags = re.sub(r"<[^>]+>", " ", without_comments)
    normalized = re.sub(r"\s+", " ", unescape(without_tags)).strip()
    return normalized


def _truncate_message(message: str, limit: int = 500) -> str:
    return message if len(message) <= limit else f"{message[:limit]}..."


# 保留旧名称，避免外部调用导入时报错；内部已经不再返回固定样例。
OfflineDemoClient = RuleBasedClient
