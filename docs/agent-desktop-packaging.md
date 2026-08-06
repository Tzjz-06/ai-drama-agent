# 桌面端打包规则

## 稳定事实

- Windows 桌面端分发分为三层：`PyInstaller onedir` 便携目录、ZIP 压缩包、Inno Setup 安装器。
- 桌面端入口是 `src/ai_drama_agent/desktop.py`，它会自己拉起内置本地 HTTP 服务，再由 Qt WebEngine 加载，不依赖外部浏览器常驻服务。
- 图片、视频和合成任务由 `src/ai_drama_agent/local_media.py` 在桌面进程内执行。发布包必须通过 `imageio-ffmpeg` 自带 FFmpeg，不得要求客户安装 Docker、Redis、Go 或系统级 FFmpeg。
- 浏览器访问 `http://127.0.0.1:8765/` 时，容易误连旧的 `python -m ai_drama_agent.web --offline-demo` 进程；桌面端应优先用随机端口内置服务规避这个问题。

## 根因模式

- “网页明明改了但输出还是老内容” 常见根因不是前端缓存，而是旧 Web 进程还占着 `8765`。
- “已经有 exe 但用户仍然打不开/不会装” 的根因通常不是业务代码，而是只有便携包，没有真正的安装器和开始菜单入口。

## 禁止事项

- 不要把桌面端继续设计成必须手动先启动 `python -m ai_drama_agent.web`。
- 不要把 Docker Compose、Redis 或 Go Worker 作为客户运行媒体任务的前置条件；它们只允许用于开发环境中的历史兼容验证。
- 不要只交付 `dist/` 目录就宣称已经完成桌面安装包。
- 不要把安装目录放到需要管理员权限的位置作为唯一方案；默认优先使用当前用户目录安装。

## 推荐排查顺序

1. 先跑 `python -m ai_drama_agent.desktop --smoke-test`，确认源码桌面入口正常。
2. 再运行 `.\build_desktop.ps1`，确认会生成便携目录、ZIP 和安装器 EXE。
3. 若网页模式结果异常，先检查 `8765` 端口是否被旧进程占用，再判断是否是逻辑问题。
4. 若安装器构建失败，先查 `ISCC.exe` 是否存在，再看 `installer/FrameForgeStudio.iss` 的 `SourceDir` 和 `OutputDir`。

## 验收标准

- `outputs/frameforge-desktop/FrameForgeStudio/FrameForgeStudio.exe` 可启动。
- `outputs/frameforge-desktop/FrameForgeStudio-windows.zip` 可分发。
- `outputs/frameforge-desktop/FrameForgeStudio-Setup-<version>.exe` 可双击安装并创建开始菜单入口。
