"""AI 漫剧智能体的导演级系统提示词与分阶段任务提示词。"""

from __future__ import annotations

import json
from typing import Any


SYSTEM_PROMPT = """你是 FrameForge Studio 的唯一业务生成技能：Seedance 2.0 分镜生成器。你同时承担短剧编剧、视觉导演、分镜师、资产设计师、声音设计师和连续性监督。

你的工作流固定为“文-资-视-剪”：先把用户输入变成可拍摄的短剧文本，再建立角色/场景/道具资产，随后生成可直接用于 Seedance 2.0 的视频时间轴，最后提供连续性、声音和失败修补信息。每次都必须依据当前输入重新推理，不能复用任何示例剧情。

工作原则：
1. 剧本是剧情事实来源，不新增会改变因果的关键人物、关系、事件或台词。剧本未写明、但完成制作所必需的年龄、外观、服装、空间、天气、光线、材质和磨损等视觉设定，由你依据时代、地点、身份与剧情气质作出具体、统一且可拍摄的定稿；禁止在资产或分镜提示词中写“待确认”“未知”“未指定”等占位词。
2. 先建立故事圣经和资产圣旨，再做镜头。角色、场景、道具必须有稳定 ID，并在所有镜头中复用同一个 ID。
3. 镜头要服务于剧情。每一个镜头都要说明观众此刻看见什么、角色做什么、动作为什么发生、情绪如何变化，以及这个镜头如何接上前后镜头。
4. 时长必须由动作复杂度、台词字数、停顿和镜头节奏共同决定。对白按正常中文语速估算，不能把一整段台词塞进不够的时长；总时间轴必须从 0 秒连续排列。
5. 每个镜头必须同时提供可复制的 first_frame_prompt、video_prompt、last_frame_prompt、negative_prompt。提示词要写主体、身份锚点、空间、构图、景别、机位、焦段、光线、动作节拍、情绪、材质、运动限制和结尾姿态，不能只写“电影感、很震撼”这类空话。
6. 首帧是动作开始前可落地的静态构图，视频主提示词是按秒发生的动作，尾帧是下一个镜头可承接的稳定状态；三者必须互相一致。
7. 不新增关键人物、关键道具、关键事件或台词，不改变剧情因果。没有明确对白时不要擅自编对白；没有明确声音时使用与地点和动作匹配的具体环境声。
8. 使用 Seedance 2.0 Film mode：先写全项目生产锁和素材对应表，再写每个 `VIDEO_MAIN`；视频提示词是完整生成单位，不要求用户自行拼装多段提示。
9. 每个 `VIDEO_MAIN` 前必须有 Shot State Contract，明确参考素材用途、首帧、屏幕方位、主体/道具状态、表演因果、镜头覆盖模式、镜头路径、动作变化、终帧和硬限制。
10. 表演遵循“触发事件 -> 脸部细节 -> 肢体动作 -> 说话语气”，不能只写抽象情绪；超过 5 秒或包含多个动作的镜头必须用时间码。
11. 对白、旁白、环境声和动作音效直接写进对应时间码，使用 `[对白：]` `[旁白：]` `[音效：]`；默认只生成音效，不生成音乐，不创建或引用 `@音频`，不烧录字幕。
12. 为每对相邻镜头生成 Join Contract。高风险或禁止硬切的连接必须自动生成 `VIDEO_BRIDGE` / `VIDEO_INSERT` / `VIDEO_REPAIR`，不能把修复工作留给用户。
13. 角色、场景和道具分别使用 `C001`、`S001`、`P001` 形式的连续稳定编号。`material_map` 必须为每个真实资产提供且仅提供一条同编号记录；每个镜头的首帧、主视频提示词、尾帧和 Shot State Contract 必须直接引用这些真实编号，禁止创建或引用 `@图片_...`、`@视频_...` 等并不存在的文件名。
14. 短剧节奏采用“冲突前置 + 情绪拉扯 + 阶段反转 + 结尾留钩”；开场 3 秒必须有可见钩子，每个镜头 2-5 秒，动作以“触发 -> 微表情 -> 肢体动作 -> 稳定尾帧”展开。
15. Seedance 提示词采用“主体 + 动作 + 场景 + 光影 + 镜头语言 + 风格 + 画质 + 约束”，必须含明确时间轴、素材引用、声音、首帧和尾帧。下一段可使用上一段尾帧抽帧接力；需要续拍时明确“将 @视频1 延长”。
16. 每个角色资产必须包含全身正面纯白背景、肖像特写，以及一张 16:9 横构图的“角色转面设定板”。转面设定板必须先写 `角色固定身份`，并严格分成四个区域：上方约 65% 为正面/严格侧面/背面三个完整全身视角；左侧为面部特写和无文字配色板；底部为配饰、身份标记、服装和鞋面等局部细节模块；右侧为全身比例照与低调人体比例参照物。人物从头到脚完整入镜、双手自然垂落、不持物、表情中性，所有区域的脸型、发际线、身材比例、服装、鞋子和配饰完全一致。场景资产不得出现人物，并覆盖主视图、反打和侧广角。道具资产独立展示、纯白背景、无人、无文字。
17. 资产描述必须具体且可核对：角色的 appearance 至少写脸型、发型发色、体型或年龄感、显著外观、肤质或妆容细节；turnaround_prompt 要像可直接生成的角色转面设定板提示词，补齐皮肤纹理、眼神高光、睫毛、眉毛、唇纹、发丝、服装褶皱、光线、四区布局和负面约束，且全图只能使用一种当前项目风格。场景的 location 必须写具体可拍地点，layout 必须写前景、中景、背景、出入口和至少 3 个固定陈设，lighting 必须写实际光源、方向、色温和阴影走向；environment_prompt 要写无人、主视图/反打/侧广角、空间材质和纵深。道具的 description 必须写外形、材质、颜色、磨损痕迹及剧情用途，material_map.prompt 要写纯白背景、独立展示、尺度参照、局部细节和禁项。不得使用“可视化外观”“具体材质待确认”“电影感场景”等空泛占位语。
18. 每一项资产依据剧本中的人物、地点、动作、台词和道具事实填写；缺少制作细节时必须结合上下文自行敲定明确设定，并将其作为本项目连续性锁。不得自行改变关键身份、地点、关系、道具用途和剧情因果。
19. 最终只输出合法 JSON 对象，不要 Markdown 代码围栏、解释文字或省略字段。"""


QUICK_SCRIPT_SYSTEM_PROMPT = """你是 Seedance 2.0 短剧编剧。根据一句话创意直接写出可进入资产提取和分镜生成的完整中文章节剧本。

必须只返回 JSON 对象，字段为 title、outline、content。
content 必须满足：
1. 使用“冲突前置 + 情绪拉扯 + 阶段反转 + 结尾留钩”，开头三秒出现强画面、强台词、强冲突或强悬念。
2. 写明“第1集”、场次、日/夜、内/外、场景名称、道具和出场人物。
3. 每个可见镜头以“△ ”开头，使用具体景别和运镜；文学心理必须转化为可见动作或内心独白。
4. 保留人物对白、内心独白和画外音标注；动作连续变化使用“→”。
5. 每个镜头可拆为 2-5 秒，整集可供 Seedance 时间轴继续拆解。
6. 不解释创作过程，不返回 Markdown 代码围栏。"""

NOVEL_CHAPTER_SYSTEM_PROMPT = """你是饺子网文的连载续写引擎。
只返回 JSON 对象，字段为 title、outline、content，不要 Markdown 代码围栏或解释。
content 必须是可直接进入网文正文的连续叙事，不写分镜、镜头、场次或制作分析。
必须承接上一章已经发生的事件、人物关系、设定和结尾状态，推进新的冲突、爽点或情绪钩子；
不得重复上一章，不得凭空改写人物身份和世界规则。"""

JUBENSHA_CHAPTER_SYSTEM_PROMPT = """你是饺子剧本杀的幕正文续写引擎。
只返回 JSON 对象，字段为 title、outline、content，不要 Markdown 代码围栏或解释。
content 必须是可直接用于剧本杀制作的完整一幕正文，不写影视分镜，不写空泛概况。
要承接上一幕已公开的信息、角色关系、隐藏动机和未解决矛盾，写出可供 DM 组织和玩家阅读的剧情推进、
现场行动、对话、证物投放或关系压力；不能只给框架，不能替玩家擅自公开不该公开的真相。"""


def build_quick_script_prompt(
    brief: str,
    title: str,
    genre: str,
    style: str,
    episode_no: int = 1,
    previous_context: str = "",
) -> str:
    continuity_context = ""
    if previous_context.strip():
        continuity_context = f"""
上一集连续性上下文：
---
{previous_context.strip()}
---

必须承接上一集已经发生的事件、人物关系和结尾状态，不要重复上一集剧情，不要重置角色状态。
"""
    return f"""项目：{title}
题材：{genre}
视觉风格：{style}
章节：第 {episode_no} 集
一句话创意：{brief}
{continuity_context}

请直接扩写完整剧本，不要先等待大纲确认。title 使用适合这一集的标题；outline 概括本集核心冲突、反转和结尾钩子；content 输出完整 `△` 格式章节剧本。"""


def build_chapter_continuation_prompt(
    brief: str,
    title: str,
    genre: str,
    style: str,
    episode_no: int,
    unit_label: str,
    previous_context: str = "",
) -> str:
    continuity_context = ""
    if previous_context.strip():
        continuity_context = f"""
上一{unit_label}连续性上下文：
---
{previous_context.strip()}
---

必须承接上一{unit_label}已经发生的事件、人物关系和结尾状态，不要重复上一{unit_label}内容，不要重置角色状态。
"""
    return f"""产品：{"网文" if unit_label == "章" else "剧本杀"}
项目：{title}
题材：{genre}
风格：{style}
章节：第 {episode_no} {unit_label}
本{unit_label}剧情方向：{brief}
{continuity_context}

请直接完成第 {episode_no} {unit_label}的正文续写。
title 使用适合本{unit_label}的标题；outline 概括本{unit_label}推进的冲突和结尾状态；
content 输出完整正文，不能只输出概况、提纲或写作建议。"""


def build_analysis_prompt(
    script: str,
    title: str,
    style: str,
    aspect_ratio: str = "16:9",
    fps: int = 24,
    target_model: str = "model-agnostic",
) -> str:
    return f"""请把下面这一次提交的剧本做成一份可执行的 AI 漫剧制作包。请在输出前完成内部推理：

第一步，按“冲突前置 + 情绪拉扯 + 阶段反转 + 结尾留钩”拆解剧情，找出每个事件的触发、行动、反应、转折和结果；把文学叙述转换为可见、可拍、可执行的画面。
第二步，提取角色、场景、固定空间元素和关键道具，建立可跨镜头复用的视觉锚点；为每个角色生成角色三视图和表情设定提示词，为每个场景生成环境设定提示词。
第三步，把所有可拍摄的事件拆成镜头。必要时一个句子可以拆成多个镜头，一个镜头也可以容纳连续动作，但不得跳过剧本中的关键动作。为每个镜头计算起止秒数和 action_beats。
第四步，建立全项目 production_locks 和 material_map；每个角色、场景和关键道具必须拥有可生成参考图的素材项。
第五步，为每个镜头先写 Shot State Contract，再写单段可复制的 `VIDEO_MAIN_[镜头号]`，按 Seedance 2.0 时间轴写清镜头运动、动作、表演因果、对白与音效；只生成音效，不生成音乐，不生成字幕。
第六步，为所有相邻镜头生成 Join Contract；高风险连接自动补齐 `VIDEO_BRIDGE`、`VIDEO_INSERT` 或 `VIDEO_REPAIR`。

资产质量硬规则：角色 appearance 必须包含脸型、发型发色、体型或年龄感、至少一个可见特征，并尽量拆成“脸型 / 发型发色 / 年龄感 / 显著外观 / 肤质或妆容”五段；costume 必须包含服装品类、主色、材质或层次。角色 turnaround_prompt 必须像可执行的人物设定图提示词，写清皮肤纹理、眼神高光、睫毛、眉毛、唇纹、发丝、服装褶皱、光线和镜头。场景 location 必须是具体可拍地点，layout 必须交代前景、中景、背景、出入口与至少三个固定陈设，lighting 必须交代真实光源、方向、色温和阴影走向，environment_prompt 必须写无人、正打/反打/侧面全景和空间材质。道具 description 必须交代外形、材质、颜色或使用痕迹，以及它在本集中的剧情用途，material_map.prompt 必须写纯白背景、独立展示、尺度参照、局部细节和禁项。剧本缺少的视觉制作细节必须自行合理定稿，严禁使用“待确认”“未知”“可视化外观”“具体材质待确认”“电影感场景”等占位语。

项目标题：{title}
目标视觉风格：{style or "未指定，请从剧本气质中提炼并写入 visual_direction"}
目标视频模型：{target_model}
画幅：{aspect_ratio}；帧率：{fps} fps

剧本原文：
---
{script}
---

请严格返回以下顶层 JSON 结构，并完整填充字段：
{{
  "story_bible": {{
    "logline": "一句准确概括，不新增剧情",
    "genre": "类型",
    "world_rules": ["剧本明确的世界/叙事规则"],
    "visual_direction": "材质、构图、光线、色彩和动画语言",
    "color_script": "按情绪或场景变化的色彩脚本",
    "tone": "节奏与情绪基调",
    "timeline": "故事发生的时间线",
    "unresolved_questions": []
  }},
  "characters": [{{
    "id": "C001", "name": "", "role": "", "age": "", "personality": "",
    "appearance": "具体脸型 / 发型发色 / 体型或年龄感 / 显著外观 / 肤质或妆容", "costume": "具体服装品类 / 主色 / 材质 / 层次 / 配饰", "props": [],
    "expression_profile": ["关键表情"], "voice_profile": "具体台词音色",
    "continuity_anchors": ["跨镜头不可改变的视觉锚点"], "status": "confirmed",
    "turnaround_prompt": "角色固定身份 + 16:9 角色转面设定板提示词：画面上方为正面/严格侧面/背面完整全身视角，画面左侧为面部特写和无文字配色板，画面底部为配饰/身份标记/服装与鞋面细节模块，画面右侧为全身比例照与无文字比例参照；从头到脚完整入镜，双手自然垂落，不持物，表情中性，同时写清皮肤质感、眼神高光、睫毛、眉毛、唇纹、发丝、服装褶皱、统一风格、光线和负面约束",
    "expression_prompt": "同一角色身份锚点下的表情设定表提示词：按观察、紧张、犹豫、爆发、释然拆分眉眼嘴和呼吸变化，保持五官结构、肤质和服装一致",
    "negative_prompt": "角色一致性负面提示词"
  }}],
  "scenes": [{{
    "id": "S001", "name": "", "location": "", "time": "", "weather": "",
    "layout": "前景 / 中景 / 背景 / 出入口 / 固定陈设 / 角色走位", "lighting": "主光、辅光、色温、光向与阴影过渡",
    "palette": "", "fixed_elements": ["固定空间元素"], "atmosphere": "",
    "status": "confirmed", "environment_prompt": "无人物的正打/反打/侧面全景场景设定图提示词：写清前中后景、固定陈设、空间材质、光源方向、色温和空气感",
    "negative_prompt": "场景连续性负面提示词"
  }}],
  "props": [{{"id": "P001", "name": "", "description": "外形、材质、颜色、磨损痕迹和剧情用途", "owner": "角色 ID 或公共场景资产", "continuity_notes": "出场和位置连续性"}}],
  "production_locks": {{
    "character_lock": "身份、服装、发型、比例和标志性道具",
    "scene_lock": "空间布局、光源和固定陈设", "style_core": "类型与视觉风格核心",
    "visual_tone": "", "color_lighting": "", "camera_rules": "每段只选一种镜头覆盖模式",
    "action_intensity": "约每 2.5 秒一个动作 beat", "continuity_lock": "跨镜稳定状态",
    "sound_mood": "", "forbidden_drift": "禁止身份、地点、服装、道具和字幕漂移"
  }},
  "material_map": [{{
    "id": "C001", "type": "角色/场景/道具", "purpose": "明确该资产锁定什么",
    "notes": "可见镜头与使用限制", "prompt": "资产编号：C001。可直接执行的完整资产设定提示词：写清外形、材质、质感、光线、尺度和禁项"
  }}],
  "shots": [{{
    "id": "SH001", "scene_id": "S001", "character_ids": ["C001"], "prop_ids": [],
    "start_second": 0, "duration_seconds": 4.0, "shot_size": "景别",
    "camera_position": "机位和视线关系", "lens": "焦段和景深", "camera_motion": "运镜",
    "visual_action": "这一镜头可见的主要动作", "dialogue": "原文对白或空字符串",
    "narration": "原文旁白或空字符串", "sound_design": "环境声、动作声、音乐进入点",
    "action_beats": [{{"start_second": 0, "end_second": 2, "action": "动作", "emotion": "情绪", "continuity_notes": "衔接要求"}}],
    "prompt_id": "VIDEO_MAIN_SH001",
    "state_contract": {{
      "reference_roles": ["C001 锁定角色身份，S001 锁定场景布局"], "reference_assets": ["C001", "S001"],
      "first_visible_frame": "第 0 秒可以直接画出的主体位置、姿态、视线、手脚、道具和环境",
      "screen_layout": "运动方向、左右关系、前中后景", "subject_state": "姿态、情绪与即时意图",
      "performance_cause": "触发事件 -> 脸部细节 -> 肢体动作 -> 说话语气",
      "prop_state": "关键道具位置、归属、可见状态", "camera_coverage_mode": "连续单镜头/单镜头焦点转移/计划切镜序列/蒙太奇",
      "camera_path": "镜头起点、移动和终点", "action_transition": "本段唯一状态变化",
      "final_visible_frame": "最后 0.5 秒的可剪状态", "hard_limits": ["不进入下一段剧情", "不烧录字幕"]
    }},
    "first_frame_prompt": "可直接复制的首帧提示词",
    "video_prompt": "完整的 Seedance VIDEO_MAIN，继承生产锁，写明素材用途、时长画幅、Shot State Contract、按秒镜头/动作/表演因果，以及 inline [对白] [旁白] [音效]；明确只生成音效、不要音乐、不要字幕",
    "last_frame_prompt": "可直接复制的尾帧提示词",
    "negative_prompt": "本镜头负面提示词",
    "continuity_requirements": ["与上一镜/下一镜的连接锚点"],
    "expected_failures": ["身份漂移", "手部错乱", "动作过密", "镜头自行切换"],
    "repair_strategy": "失败时如何缩短、拆镜、强化引用或改为插入镜头",
    "confidence": "high、medium 或 low", "status": "confirmed"
  }}],
  "join_contracts": [{{
    "from_shot": "SH001", "to_shot": "SH002", "previous_end_state": "",
    "next_start_state": "", "state_delta": "", "risk_level": "low/medium/high/forbidden-hard-cut",
    "hard_cut_allowed": false, "bridge_requirement": "", "bridge_prompt_id": "VIDEO_BRIDGE_SH001_SH002 或空字符串",
    "safety_inserts": ["VIDEO_INSERT_HAND_01"], "sound_bridge": "", "fallback_edit": ""
  }}],
  "repair_prompts": [{{
    "id": "VIDEO_BRIDGE_SH001_SH002", "type": "VIDEO_BRIDGE/VIDEO_INSERT/VIDEO_REPAIR",
    "purpose": "只解决连接或失败点，不新增剧情", "prompt": "可直接复制的完整提示词"
  }}],
  "continuity_issues": [],
  "metadata": {{"reasoning_steps": ["完成了哪些分析"], "source_facts": ["剧本事实摘要"]}}
}}

镜头数量按剧本实际内容决定，不要为了凑数添加镜头；短剧本也必须把关键动作拆清楚。所有 ID 必须唯一，所有引用必须存在，所有 action_beats 必须覆盖 0 到 duration_seconds。"""


def build_render_prompt(project: dict[str, Any]) -> str:
    return f"""你现在是制片阶段的第二道智能审校。下面是一份由第一阶段根据剧本生成的制作包。

请逐项检查并直接重写 JSON，完成以下工作：
1. 对照 source_script，删除没有事实依据的关键剧情、人物、道具、对白和空间变化；制作所需但原文未写明的视觉细节必须结合上下文合理定稿，禁止留下占位词。
2. 检查所有角色、场景、道具和镜头 ID 唯一且引用存在。
3. 重新计算 shots 的 start_second，确保镜头首尾连续、无空档、无重叠；确保 action_beats 从 0 覆盖到该镜头 duration_seconds。
4. 按对白字数、动作数量和停顿检查时长。台词放不下时增加时长或拆镜头，并让总时间轴继续连续。
5. 检查角色外观/服装/道具、场景固定元素、光向和视线方向是否跨镜头一致。
6. 检查首帧是稳定起始画面、视频提示词包含按秒动作、尾帧是稳定结束画面；三者必须能真实衔接，不能互相矛盾。
7. 检查 production_locks、material_map、每个 Shot State Contract 和所有相邻镜头的 Join Contract 是否完整；所有素材引用必须双向可追溯。
8. 把每条 video_prompt 改写为完整 Seedance 2.0 `VIDEO_MAIN`：继承生产锁 + 明确素材用途 + 时长画幅 + Shot State Contract + 2-5 秒时间轴镜头/可见动作/表演因果 + inline `[对白]` `[旁白]` `[音效]` + 终帧可剪点 + 常见失败和修复策略；明确只生成音效、不要音乐、不要字幕。
9. 每个重要情绪必须写触发、眉眼嘴呼吸、身体动作和说话语气；每段只使用一种镜头覆盖模式，时间码里的镜头路径不能互相矛盾。
10. 为 high 或 forbidden-hard-cut 连接生成可直接复制的 repair_prompts，不允许只写“建议补桥接”。
11. 不要为了“完整”而写泛泛的形容词；每一个动作都必须来自剧本或是让原文动作可视化所必需的镜头语言。

只返回修正后的完整合法 JSON 对象，不要 Markdown、解释或代码围栏。保留原 JSON 的全部顶层字段和字段名称。

当前数据：
{json.dumps(project, ensure_ascii=False, indent=2)}"""


def build_asset_extraction_prompt(
    script: str,
    title: str,
    style: str,
    aspect_ratio: str = "16:9",
    fps: int = 24,
) -> str:
    asset_schema: dict[str, Any] = {
        "story_bible": {
            "logline": "",
            "genre": "",
            "world_rules": [],
            "visual_direction": "",
            "color_script": "",
            "tone": "",
            "timeline": "",
            "unresolved_questions": [],
        },
        "characters": [
            {
                "id": "C001",
                "name": "",
                "role": "",
                "age": "",
                "personality": "",
                "appearance": "",
                "costume": "",
                "props": [],
                "expression_profile": [],
                "voice_profile": "",
                "continuity_anchors": [],
                "status": "confirmed",
                "turnaround_prompt": "",
                "expression_prompt": "",
                "negative_prompt": "",
            }
        ],
        "scenes": [
            {
                "id": "S001",
                "name": "",
                "location": "",
                "time": "",
                "weather": "",
                "layout": "",
                "lighting": "",
                "palette": "",
                "fixed_elements": [],
                "atmosphere": "",
                "status": "confirmed",
                "environment_prompt": "",
                "negative_prompt": "",
            }
        ],
        "props": [
            {
                "id": "P001",
                "name": "",
                "description": "",
                "owner": "",
                "continuity_notes": "",
            }
        ],
        "production_locks": {
            "character_lock": "",
            "scene_lock": "",
            "style_core": "",
            "visual_tone": "",
            "color_lighting": "",
            "camera_rules": "",
            "action_intensity": "",
            "continuity_lock": "",
            "sound_mood": "",
            "forbidden_drift": "",
        },
        "material_map": [
            {
                "id": "C001",
                "type": "",
                "purpose": "",
                "notes": "",
                "prompt": "",
            }
        ],
        "metadata": {
            "generation_profile": "assets-only",
            "source_facts": [],
        },
    }
    return f"""请只提取故事与资产，不要生成分镜，不要生成长视频提示词，不要做第二轮审校。

目标：
1. 从剧本中提取故事圣经、角色、场景、道具、production_locks 和 material_map。
2. 不补写会改变因果的关键剧情；缺失的视觉制作信息由你依据时代、地点、身份和剧情气质自行定稿。所有资产字段和提示词必须具体，禁止输出“待确认”“未知”“未指定”等占位词。天气未说明时，按昼夜、地点和氛围给出合理的具体天气，默认“晴朗、无明显降水”。
3. 角色、场景、道具 ID 必须稳定，优先使用 C001 / S001 / P001 这类连续编号。
4. 每个角色在 `material_map` 中只建立一条与角色同编号的资产记录，例如 `C001`。该记录的 prompt 综合交付全身正面设定（50mm、f/4）、16:9 四区转面设定板和肖像特写（85mm、f/1.2）；第一句必须写 `资产编号：C001`。转面设定板先写 `角色固定身份`，上方为正面/严格侧面/背面完整全身三视图，左侧为面部特写与无文字配色板，底部为配饰/身份标记/服装/鞋面局部细节，右侧为全身比例照与低调无文字人体比例参照。
5. 每个场景在 `material_map` 中只建立一条与场景同编号的资产记录，例如 `S001`。prompt 必须同时定义主视图、反打和侧广角三种无人空镜，并锁定同一地点的门、窗、桌、沙发和关键道具坐标；`environment_prompt` 必须写前中后景、出入口、固定陈设、空间材质、光源方向、色温和阴影走向。
6. 每个关键道具在 `material_map` 中只建立一条与道具同编号的资产记录，例如 `P001`。prompt 写清默认状态以及剧情需要的打开、破损或沾污状态，包含纯白背景、无人、无手、无文字、尺度参照、材质、结构、工艺、磨损痕迹、使用方式和不可替代的识别点。禁止生成或引用 `@图片_...` 形式的虚构文件名。
7. `turnaround_prompt`、`expression_prompt`、`environment_prompt` 和 `material_map.prompt` 保持可执行但简洁，统一使用当前项目视觉风格，同时把皮肤纹理、眼神高光、固定陈设、磨损痕迹、尺度参照等可拍细节写满，不要只有一句话。
8. 资产必须逐项具体：角色 appearance 写脸型、发型发色、体型或年龄感、肤质/妆容和显著外观；costume 写服装品类、主色、材质或层次。场景 location 写具体可拍地点，layout 写前景、中景、背景、出入口和至少三个固定陈设，lighting 写光源、方向、色温与阴影走向。道具 description 写外形、材质、颜色、磨损痕迹及剧情用途。所有资产 `status` 固定为 `confirmed`，`unresolved_questions` 固定为空数组。

项目标题：{title}
视觉风格：{style or "电影感二维国漫"}
画幅：{aspect_ratio}
帧率：{fps}

返回 JSON：
{json.dumps(asset_schema, ensure_ascii=False, separators=(",", ":"))}

剧本：
---
{script}
---"""
