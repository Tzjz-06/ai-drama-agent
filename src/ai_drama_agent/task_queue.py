"""HTTP adapter for the Go Asynq gateway."""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Any


class TaskQueueError(RuntimeError):
    """队列基础设施不可用或返回了错误。"""


@dataclass(frozen=True)
class AsynqGateway:
    base_url: str = "http://127.0.0.1:8787"
    timeout_seconds: float = 3.0

    @classmethod
    def from_environment(cls) -> "AsynqGateway":
        url = os.getenv("AI_DRAMA_TASK_GATEWAY_URL", "http://127.0.0.1:8787")
        return cls(base_url=url.rstrip("/"))

    def enqueue(self, task: dict[str, Any]) -> None:
        request = urllib.request.Request(
            f"{self.base_url}/enqueue",
            data=json.dumps(task, ensure_ascii=False).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=self.timeout_seconds) as response:
                payload = json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as error:
            detail = error.read().decode("utf-8", errors="replace")
            raise TaskQueueError(f"Asynq 队列拒绝任务（HTTP {error.code}）：{detail[:300]}") from error
        except (urllib.error.URLError, TimeoutError) as error:
            raise TaskQueueError(
                "异步服务未启动：Asynq 网关不可用。请启动 `docker compose up -d redis queue-gateway worker` 后重试。"
            ) from error
        if not isinstance(payload, dict) or payload.get("ok") is not True:
            raise TaskQueueError("Asynq 网关没有确认任务入队。")

    def status(self, task_id: str) -> dict[str, Any]:
        request = urllib.request.Request(f"{self.base_url}/tasks/{task_id}", method="GET")
        try:
            with urllib.request.urlopen(request, timeout=self.timeout_seconds) as response:
                payload = json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as error:
            detail = error.read().decode("utf-8", errors="replace")
            raise TaskQueueError(f"Asynq 状态查询失败（HTTP {error.code}）：{detail[:300]}") from error
        except (urllib.error.URLError, TimeoutError) as error:
            raise TaskQueueError("Asynq 网关暂时不可用，任务状态未知。") from error
        if not isinstance(payload, dict) or not isinstance(payload.get("status"), str):
            raise TaskQueueError("Asynq 网关返回了无效任务状态。")
        return payload


# 旧名称保留为兼容别名，队列实现已经改为 Asynq HTTP 网关。
RedisTaskQueue = AsynqGateway
