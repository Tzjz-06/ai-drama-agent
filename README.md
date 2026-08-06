# 饺子短剧

这是一个面向 AI 短剧与漫剧创作者的本地创作工作台，提供账户隔离、多项目管理、章节化写作和完整提示词生产流程。

它将一份剧本转换成：

- 故事圣经
- 角色资产与角色三视图提示词
- 场景资产与场景设定提示词
- 道具清单
- 按秒拆解的分镜表
- 每个镜头的首帧、视频、尾帧和负面提示词
- 连续性检查结果

## 设计原则

视频模型通常以镜头片段为生成单位，因此本项目采用“逐镜头 + 关键帧”的方式，而不是为每一帧写一条独立提示词：

- 每个镜头有一个完整视频提示词
- 每个镜头有首帧和尾帧提示词
- 动作按时间段拆解
- 角色、场景和道具使用稳定 ID 引用
- 信息不足时标记 `待确认`，不静默编造关键剧情

## 快速开始

### 1. 配置模型

项目支持两种真实模型接入方式：

- 手动填写 OpenAI-compatible 接口
- 使用本机 CC-Switch 当前启用的 Codex 供应商

### 手动填写接口

手动模式支持 OpenAI-compatible 的 Chat Completions 服务：

```powershell
$env:AI_DRAMA_API_KEY = "你的 API Key"
$env:AI_DRAMA_BASE_URL = "https://你的服务地址/v1"
$env:AI_DRAMA_MODEL = "你的模型名称"
```

如果 `AI_DRAMA_BASE_URL` 为空，默认使用 `https://api.openai.com/v1`。

### 使用 CC-Switch

如果本机已经安装并启用了 CC-Switch 的 Codex 代理，可在 Web 设置里切换到“使用 CC-Switch”模式。此时：

- 饺子短剧只读取 `C:\Users\LEGION\.cc-switch\cc-switch.db` 中当前启用的 Codex 供应商
- 调用通过本机代理 `http://127.0.0.1:15721/v1/responses` 发起
- API Key 继续由 CC-Switch 管理，不会传给浏览器
- 在 CC-Switch 内切换中转站后，饺子短剧会自动跟随

如果 CC-Switch 未启动、代理未启用，或当前协议不是 `responses`，页面会明确提示，不会静默切换到其他接口。

### 2. 运行

```powershell
python -m ai_drama_agent.cli `
  --script examples/sample_script.txt `
  --output ..\..\outputs\ai-drama-demo `
  --title "雨夜归来" `
  --style "电影感二维国漫，冷暖对比，细腻光影" `
  --aspect-ratio "16:9" `
  --fps 24
```

从项目目录运行时，需要把 `src` 放入 `PYTHONPATH`：

```powershell
$env:PYTHONPATH = "$PWD\src"
python -m ai_drama_agent.cli --script examples/sample_script.txt --output ..\..\outputs\ai-drama-demo
```

### 3. 离线演示

没有 API Key 时，可以运行离线演示验证导出格式：

```powershell
$env:PYTHONPATH = "$PWD\src"
python -m ai_drama_agent.cli `
  --script examples/sample_script.txt `
  --output ..\..\outputs\ai-drama-offline `
  --offline-demo
```

## 输出结构

```text
output/
├── project.json
├── production_package.md
├── story_bible.md
├── characters.md
├── scenes.md
├── storyboard.md
└── continuity_report.md
```

## Web 工作流

1. 注册或登录本地创作者账户。
2. 在项目管理台创建多个短剧项目。
3. 为项目创建章节，手动录入、导入文档或使用 AI 起草剧本。
4. 从当前章节生成角色、场景、道具和完整分镜提示词。
5. 在资产库和分镜检视器中检查、复制生成结果。

## 启动网页版本

在项目目录运行真实模型 Web 版本：

```powershell
$env:PYTHONPATH = "$PWD\src"
python -m ai_drama_agent.web
```

然后打开浏览器访问 `http://127.0.0.1:8765`。

如果要调用真实模型，先配置：

```powershell
$env:AI_DRAMA_API_KEY = "你的 API Key"
$env:AI_DRAMA_BASE_URL = "https://api.openai.com/v1"
$env:AI_DRAMA_MODEL = "你的模型名称"
```

再运行：

```powershell
$env:PYTHONPATH = "$PWD\src"
python -m ai_drama_agent.web
```

也可以在登录后的“设置”中选择“手动填写接口”或“使用 CC-Switch”。手动模式下填写的密钥只保存在当前浏览器标签页会话，不会写入账户、项目或制作包。只有显式加上 `--offline-demo` 才会启用离线规则调试模式。

本地账户、项目、章节和每章生成结果默认保存在 `data/app_state.json`。可用 `AI_DRAMA_DATA_FILE` 指定其他位置；密码只保存 PBKDF2 哈希，不保存明文。

### PaddleOCR

扫描版 PDF、PNG 和 JPG 会使用 PaddleOCR 中文模型识别；PDF 若本身含有足够文本则直接读取文本层，扫描版才会渲染页面后调用 PaddleOCR。首次 OCR 可能需要下载中文模型。

## 启动桌面版

项目已经增加本地桌面端入口，默认行为：

- 不带 `--offline-demo` 时，工作台保持真实模型可配置模式，可使用环境变量、浏览器会话配置或 CC-Switch
- 只有显式传入 `--offline-demo` 时，才进入离线推理模式

运行：

```powershell
$env:PYTHONPATH = "$PWD\src"
python -m ai_drama_agent.desktop
```

如果只想启动本地服务并在默认浏览器预览：

```powershell
$env:PYTHONPATH = "$PWD\src"
python -m ai_drama_agent.desktop --browser-preview
```

仅做桌面端 smoke 测试：

```powershell
$env:PYTHONPATH = "$PWD\src"
python -m ai_drama_agent.desktop --smoke-test
```

## 构建 Windows 桌面分发包

已提供构建脚本：

```powershell
.\build_desktop.ps1
```

构建完成后，输出位于：

```text
C:\Users\LEGION\Documents\Codex\2026-08-02\ai\outputs\frameforge-desktop
```

### Windows 安装器产物

执行 `.\build_desktop.ps1` 后，会同时生成以下三类桌面端产物：

```text
FrameForgeStudio\
FrameForgeStudio-windows.zip
FrameForgeStudio-Setup-0.1.0.exe
```

- `FrameForgeStudio\`：便携桌面版，打开目录后直接运行 `FrameForgeStudio.exe`
- `FrameForgeStudio-windows.zip`：便于分发和备份的压缩包
- `FrameForgeStudio-Setup-0.1.0.exe`：本地安装器，双击后会安装到当前用户目录并创建开始菜单入口
