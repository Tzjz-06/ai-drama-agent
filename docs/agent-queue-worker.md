# 本地媒体执行规则

## 稳定事实

- 桌面版客户运行时不依赖 Docker、Redis、Go worker 或单独的队列服务。
- 图片、视频和合成任务由 `src/ai_drama_agent/local_media.py` 在桌面进程内执行。
- OpenAI 图片使用图像生成接口，OpenAI 视频使用 Sora 轮询下载流程。
- 兼容接口只作为高级选项，必须显式填写 API 地址和模型名。
- 合成任务依赖 `imageio-ffmpeg` 提供的本地 FFmpeg。

## 禁止事项

- 不得把桌面客户的运行前置条件写成 `docker compose up`、Redis 或 worker。
- 不得在没有图片/视频上游配置时伪造成功结果。
- 不得把本地执行过程中的 API Key 写入任务记录或项目数据。

## 推荐排查顺序

1. 先确认客户是否为图片或视频配置了启用项。
2. 再确认对应供应商、模型和 API 地址是否匹配。
3. 然后验证 OpenAI / 兼容接口的真实 HTTP 返回。
4. 最后检查 FFmpeg 是否可被 `imageio-ffmpeg` 找到。

## 验收标准

- 桌面版可以直接完成关键帧、视频片段和成片合成。
- 任务失败时能直接看到具体供应商、接口或 FFmpeg 错误。
- 客户安装包无需额外安装 Docker、Redis、Go 或系统级 FFmpeg。
