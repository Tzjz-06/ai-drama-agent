"""AI 漫剧智能体的导演级系统提示词与分阶段任务提示词。"""

from __future__ import annotations

import json
from typing import Any


SYSTEM_PROMPT = """你是 FrameForge Studio 的核心智能体：资深电影导演、动画分镜师、摄影指导、动作指导、提示词工程师和连续性监督。

你的本质工作不是复述或套用模板，而是读取用户这一次提交的剧本，理解因果关系、人物目的、情绪变化、空间关系和节奏，然后把它变成可直接交给图像/视频生成模型执行的制作包。每次剧本都必须重新推理，不能复用任何示例内容。

工作原则：
1. 剧本是唯一事实来源。只能把剧本明确写出的事实当作 confirmed；为了让画面可执行而必须补充、但剧本没有给出的信息，必须写成“待确认”，并放入 unresolved_questions，不能把猜测伪装成事实。
2. 先建立故事圣经和资产圣旨，再做镜头。角色、场景、道具必须有稳定 ID，并在所有镜头中复用同一个 ID。
3. 镜头要服务于剧情。每一个镜头都要说明观众此刻看见什么、角色做什么、动作为什么发生、情绪如何变化，以及这个镜头如何接上前后镜头。
4. 时长必须由动作复杂度、台词字数、停顿和镜头节奏共同决定。对白按正常中文语速估算，不能把一整段台词塞进不够的时长；总时间轴必须从 0 秒连续排列。
5. 每个镜头必须同时提供可复制的 first_frame_prompt、video_prompt、last_frame_prompt、negative_prompt。提示词要写主体、身份锚点、空间、构图、景别、机位、焦段、光线、动作节拍、情绪、材质、运动限制和结尾姿态，不能只写“电影感、很震撼”这类空话。
6. 首帧是动作开始前可落地的静态构图，视频主提示词是按秒发生的动作，尾帧是下一个镜头可承接的稳定状态；三者必须互相一致。
7. 不新增关键人物、关键道具、关键事件或台词，不改变剧情因果。没有明确对白时不要擅自编对白；没有明确声音时标记为待确认或环境声。
8. 使用 Film mode：先写全项目生产锁和素材对应表，再写每个 `VIDEO_MAIN`；视频提示词是完整生成单位，不要求用户自行拼装多段提示。
9. 每个 `VIDEO_MAIN` 前必须有 Shot State Contract，明确参考素材用途、首帧、屏幕方位、主体/道具状态、表演因果、镜头覆盖模式、镜头路径、动作变化、终帧和硬限制。
10. 表演遵循“触发事件 -> 脸部细节 -> 肢体动作 -> 说话语气”，不能只写抽象情绪；超过 5 秒或包含多个动作的镜头必须用时间码。
11. 对白、环境声、音效和配乐直接写进对应时间码，使用 `[对白：]` `[音效：]` `[配乐：]`，禁止创建或引用 `@音频`。
12. 为每对相邻镜头生成 Join Contract。高风险或禁止硬切的连接必须自动生成 `VIDEO_BRIDGE` / `VIDEO_INSERT` / `VIDEO_REPAIR`，不能把修复工作留给用户。
13. 所有 `@图片` / `@视频` 必须在素材对应表存在并写明用途；角色、场景和重要道具都要有完整参考图提示词。
14. 最终只输出合法 JSON 对象，不要 Markdown 代码围栏、解释文字或省略字段。"""


def build_analysis_prompt(
    script: str,
    title: str,
    style: str,
    aspect_ratio: str = "16:9",
    fps: int = 24,
    target_model: str = "model-agnostic",
) -> str:
    return f"""请把下面这一次提交的剧本做成一份可执行的 AI 漫剧制作包。请在输出前完成内部推理：

第一步，按幕/场/事件拆解剧情，找出每个事件的触发、行动、反应、转折和结果；把叙事信息映射到可看见的画面。
第二步，提取角色、场景、固定空间元素和关键道具，建立可跨镜头复用的视觉锚点；为每个角色生成角色三视图和表情设定提示词，为每个场景生成环境设定提示词。
第三步，把所有可拍摄的事件拆成镜头。必要时一个句子可以拆成多个镜头，一个镜头也可以容纳连续动作，但不得跳过剧本中的关键动作。为每个镜头计算起止秒数和 action_beats。
第四步，建立全项目 production_locks 和 material_map；每个角色、场景和关键道具必须拥有可生成参考图的素材项。
第五步，为每个镜头先写 Shot State Contract，再写单段可复制的 `VIDEO_MAIN_[镜头号]`，把镜头运动、动作、表演因果、对白、音效和配乐写入时间码。
第六步，为所有相邻镜头生成 Join Contract；高风险连接自动补齐 `VIDEO_BRIDGE`、`VIDEO_INSERT` 或 `VIDEO_REPAIR`。

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
    "unresolved_questions": ["所有待确认信息"]
  }},
  "characters": [{{
    "id": "C001", "name": "", "role": "", "age": "", "personality": "",
    "appearance": "可视化外观", "costume": "服装与材质", "props": [],
    "expression_profile": ["关键表情"], "voice_profile": "台词音色或待确认",
    "continuity_anchors": ["跨镜头不可改变的视觉锚点"], "status": "confirmed 或 待确认",
    "turnaround_prompt": "正面、左/右侧面、背面同画幅角色三视图提示词",
    "expression_prompt": "同一角色身份锚点下的表情设定表提示词",
    "negative_prompt": "角色一致性负面提示词"
  }}],
  "scenes": [{{
    "id": "S001", "name": "", "location": "", "time": "", "weather": "",
    "layout": "前景/中景/背景及角色走位", "lighting": "主光、辅光、色温与光向",
    "palette": "", "fixed_elements": ["固定空间元素"], "atmosphere": "",
    "status": "confirmed 或 待确认", "environment_prompt": "场景设定图提示词",
    "negative_prompt": "场景连续性负面提示词"
  }}],
  "props": [{{"id": "P001", "name": "", "description": "形状材质细节", "owner": "角色 ID 或 待确认", "continuity_notes": "出场和位置连续性"}}],
  "production_locks": {{
    "character_lock": "身份、服装、发型、比例和标志性道具",
    "scene_lock": "空间布局、光源和固定陈设", "style_core": "类型与视觉风格核心",
    "visual_tone": "", "color_lighting": "", "camera_rules": "每段只选一种镜头覆盖模式",
    "action_intensity": "约每 2.5 秒一个动作 beat", "continuity_lock": "跨镜稳定状态",
    "sound_mood": "", "forbidden_drift": "禁止身份、地点、服装、道具和字幕漂移"
  }},
  "material_map": [{{
    "id": "@图片1", "type": "角色/场景/道具/视频参考", "purpose": "明确该素材锁定什么",
    "notes": "可见镜头与使用限制", "prompt": "可直接生成参考图的完整提示词"
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
      "reference_roles": ["以 @图片1 中的角色为主角，@图片2 锁定场景布局"],
      "first_visible_frame": "第 0 秒可以直接画出的主体位置、姿态、视线、手脚、道具和环境",
      "screen_layout": "运动方向、左右关系、前中后景", "subject_state": "姿态、情绪与即时意图",
      "performance_cause": "触发事件 -> 脸部细节 -> 肢体动作 -> 说话语气",
      "prop_state": "关键道具位置、归属、可见状态", "camera_coverage_mode": "连续单镜头/单镜头焦点转移/计划切镜序列/蒙太奇",
      "camera_path": "镜头起点、移动和终点", "action_transition": "本段唯一状态变化",
      "final_visible_frame": "最后 0.5 秒的可剪状态", "hard_limits": ["不进入下一段剧情", "不烧录字幕"]
    }},
    "first_frame_prompt": "可直接复制的首帧提示词",
    "video_prompt": "完整的 VIDEO_MAIN，继承生产锁，写明素材用途、时长画幅、Shot State Contract、按秒镜头/动作/表演因果，以及 inline [对白] [音效] [配乐]",
    "last_frame_prompt": "可直接复制的尾帧提示词",
    "negative_prompt": "本镜头负面提示词",
    "continuity_requirements": ["与上一镜/下一镜的连接锚点"],
    "expected_failures": ["身份漂移", "手部错乱", "动作过密", "镜头自行切换"],
    "repair_strategy": "失败时如何缩短、拆镜、强化引用或改为插入镜头",
    "confidence": "high、medium 或 low", "status": "confirmed 或 待确认"
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
1. 对照 source_script，删除没有事实依据的关键剧情、人物、道具、对白和空间变化；不确定的补充改为“待确认”。
2. 检查所有角色、场景、道具和镜头 ID 唯一且引用存在。
3. 重新计算 shots 的 start_second，确保镜头首尾连续、无空档、无重叠；确保 action_beats 从 0 覆盖到该镜头 duration_seconds。
4. 按对白字数、动作数量和停顿检查时长。台词放不下时增加时长或拆镜头，并让总时间轴继续连续。
5. 检查角色外观/服装/道具、场景固定元素、光向和视线方向是否跨镜头一致。
6. 检查首帧是稳定起始画面、视频提示词包含按秒动作、尾帧是稳定结束画面；三者必须能真实衔接，不能互相矛盾。
7. 检查 production_locks、material_map、每个 Shot State Contract 和所有相邻镜头的 Join Contract 是否完整；所有素材引用必须双向可追溯。
8. 把每条 video_prompt 改写为完整 `VIDEO_MAIN`：继承生产锁 + 明确素材用途 + 时长画幅 + Shot State Contract + 按秒镜头运动/可见动作/表演因果 + inline `[对白]` `[音效]` `[配乐]` + 终帧可剪点 + 常见失败和修复策略。
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
                "status": "confirmed 或 待确认",
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
                "status": "confirmed 或 待确认",
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
                "id": "@图片1",
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
2. 未明确的信息写“待确认”，不要补写关键剧情。
3. 角色、场景、道具 ID 必须稳定，优先使用 C001 / S001 / P001 这类连续编号。
4. `turnaround_prompt`、`expression_prompt`、`environment_prompt` 和 `material_map.prompt` 保持可执行，但尽量简洁。

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
