"""无外部模型时的动态剧本解析器。

它不是固定样例，而是根据当前剧本重新提取结构和生成镜头。
真实模型可用时，主流程仍优先使用 LLM。
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from typing import Any

from .models import GenerationOptions


_TIME_WORDS = (
    "清晨",
    "早晨",
    "上午",
    "中午",
    "午后",
    "黄昏",
    "傍晚",
    "深夜",
    "夜里",
    "凌晨",
    "午夜",
    "白天",
)
_WEATHER_WORDS = (
    "暴雨",
    "下雨",
    "雨夜",
    "小雨",
    "下雪",
    "风雪",
    "雷雨",
    "雾",
    "晴天",
    "阴天",
)
_PROP_WORDS = (
    "雨伞",
    "信封",
    "手机",
    "手枪",
    "长剑",
    "刀",
    "钥匙",
    "相机",
    "书",
    "花",
    "杯子",
    "灯",
    "项链",
    "戒指",
    "照片",
    "车票",
)
_LOCATION_SUFFIXES = (
    "车站",
    "月台",
    "房间",
    "客厅",
    "教室",
    "学校",
    "办公室",
    "医院",
    "街道",
    "巷子",
    "桥",
    "河边",
    "森林",
    "山顶",
    "海边",
    "广场",
    "咖啡馆",
    "车厢",
    "院子",
    "屋顶",
    "楼顶",
    "庭院",
    "城市",
    "村庄",
    "皇宫",
    "寝宫",
    "宫殿",
    "大殿",
    "静眠殿",
    "偏殿",
    "王府",
    "相府",
    "府邸",
    "殿",
    "宫",
    "阁",
    "堂",
    "厅",
)
_COMMON_FALSE_NAMES = {
    "旁白",
    "旁白OS",
    "镜头",
    "场景",
    "此时",
    "随后",
    "一个",
    "只见",
    "我们",
    "他们",
    "音效",
    "巨响音效",
    "黑屏字幕",
    "字幕",
}


@dataclass
class RuleBasedClient:
    """根据当前请求文本生成动态结构化数据。"""

    def complete_json(self, system_prompt: str, user_prompt: str) -> dict[str, Any]:
        if "当前数据：" in user_prompt:
            return _extract_json_after_marker(user_prompt, "当前数据：")

        if "剧本原文：" in user_prompt:
            script_block = user_prompt.split("剧本原文：", 1)[1]
            script_parts = script_block.split("---")
            script = script_parts[1].strip() if len(script_parts) > 2 else script_block.strip()
        else:
            script = _extract_marker_block(user_prompt, "剧本：")
        title = _extract_labeled_value(user_prompt, "项目标题：") or _title_from_script(script)
        style = (
            _extract_labeled_value(user_prompt, "目标视觉风格：")
            or _extract_labeled_value(user_prompt, "视觉风格：")
            or "电影感二维国漫，细腻光影"
        )
        return build_rule_based_analysis(script, title, style)


def build_rule_based_analysis(
    script: str,
    title: str,
    visual_style: str,
) -> dict[str, Any]:
    paragraphs = _paragraphs(script)
    story_units = _story_units(script)
    if not story_units:
        story_units = _sentences(script)
    characters = _extract_characters(story_units)
    locations = _extract_locations(script)
    scenes = _extract_explicit_scenes(script, visual_style) or _build_scenes(locations, script, visual_style)
    if not characters:
        characters = [_fallback_character(title, story_units)]
    if not scenes:
        timeline = _first_match(script, _TIME_WORDS) or "时间待确认"
        weather = _first_match(script, _WEATHER_WORDS) or "天气待确认"
        scenes = [_fallback_scene(timeline, weather, visual_style)]
    props = _build_props(script, characters)
    shots = _build_shots(
        story_units,
        characters,
        scenes,
        props,
        visual_style,
        _extract_target_runtime(script),
    )
    genre = _infer_genre(script)
    tone = _infer_tone(script)
    timeline = _first_match(script, _TIME_WORDS) or "时间待确认"
    weather = _first_match(script, _WEATHER_WORDS) or "天气待确认"
    source_hash = hashlib.sha256(script.encode("utf-8")).hexdigest()[:12]
    if not shots:
        shots = _fallback_shot(story_units, characters, scenes, props, visual_style)

    world_rules = [
        "角色外观、服装和关键道具在没有剧情依据时保持不变。",
        "镜头时间轴必须连续，首帧和尾帧要能衔接下一镜。",
        "剧本未提供的信息标记为待确认，不静默补写关键剧情。",
    ]
    reasoning_steps = [
        f"读取 {len(paragraphs)} 个剧情段落和 {len(story_units)} 个可执行叙事节点。",
        f"识别 {len(characters)} 个角色、{len(scenes)} 个场景和 {len(props)} 个道具。",
        f"根据剧情节点生成 {len(shots)} 个连续镜头，并估算每个镜头时长。",
        "将角色、场景和道具写入统一资产 ID，供镜头重复引用。",
    ]

    return {
        "story_bible": {
            "logline": _logline(story_units, title),
            "genre": genre,
            "world_rules": world_rules,
            "visual_direction": visual_style,
            "color_script": _color_script(script, weather),
            "tone": tone,
            "timeline": timeline,
            "unresolved_questions": _unresolved_questions(script, characters, scenes),
        },
        "characters": characters,
        "scenes": scenes,
        "props": props,
        "shots": shots,
        "production_locks": _build_production_locks(visual_style, characters, scenes),
        "material_map": _build_material_map(characters, scenes, props),
        "join_contracts": _build_join_contracts(shots),
        "repair_prompts": [],
        "continuity_issues": [],
        "metadata": {
            "generation_mode": "offline-rule-based",
            "source_hash": source_hash,
            "reasoning_steps": reasoning_steps,
        },
    }


def _paragraphs(script: str) -> list[str]:
    return [item.strip() for item in re.split(r"\n\s*\n+", script) if item.strip()]


def _sentences(script: str) -> list[str]:
    cleaned = re.sub(r"《[^》]+》", "", script)
    raw = re.split(r"(?<=[。！？!?；;])\s*|\n+", cleaned)
    return [item.strip() for item in raw if item.strip() and len(item.strip()) >= 4]


def _story_units(script: str) -> list[str]:
    units: list[str] = []
    for raw_line in script.splitlines():
        normalized = _normalize_script_line(raw_line)
        if not normalized or normalized.startswith("场景："):
            continue
        for item in re.split(r"(?<=[。！？!?；;])\s*", normalized):
            cleaned = _cleanup_story_unit(item)
            if cleaned:
                units.append(cleaned)
    return units


def _normalize_script_line(raw_line: str) -> str:
    line = raw_line.strip()
    if not line:
        return ""
    if re.match(r"^第\d+集\b", line) or ("时长" in line and "|" in line):
        return ""
    if "短剧剧本" in line or ("剧本" in line and len(line) <= 24 and "：" not in line and ":" not in line):
        return ""
    if re.match(r"^【\d+\s*-\s*\d+秒", line):
        return ""
    if line.startswith("【场景】"):
        return "场景：" + line.split("】", 1)[1].strip()
    line = re.sub(r"^（?旁白(?:OS)?(?:·[^：:）]+)?）?[:：]?", "旁白：", line)
    line = re.sub(r"^（?(?:全景镜头|近景特写|特写镜头|镜头猛切|暗线镜头|镜头)[:：]", "", line)
    line = re.sub(r"^（?(?:全景|中景|近景|特写)[:：]", "", line)
    line = re.sub(r"([\u4e00-\u9fffA-Za-z0-9])（([^）]+)）", r"\1，\2", line)
    if (line.startswith("（") and line.endswith("）")) or (line.startswith("(") and line.endswith(")")):
        line = line[1:-1].strip()
    return re.sub(r"\s+", " ", line).strip()


def _cleanup_story_unit(raw_unit: str) -> str:
    cleaned = raw_unit.strip(" -\t")
    if not cleaned:
        return ""
    cleaned = re.sub(r"^（?(?:全景镜头|近景特写|特写镜头|镜头猛切|暗线镜头|镜头|全景|中景|近景|特写)[:：]\s*", "", cleaned)
    cleaned = re.sub(r"^黑屏字幕[:：]\s*", "", cleaned)
    cleaned = cleaned.strip("（）() ")
    if len(cleaned) < 4:
        return ""
    if "AI写代码" in cleaned or re.match(r"^[0-9| /.-]+$", cleaned):
        return ""
    return cleaned


def _extract_target_runtime(script: str) -> float | None:
    match = re.search(r"时长\s*(\d+(?:\.\d+)?)\s*秒", script)
    if not match:
        return None
    try:
        value = float(match.group(1))
    except ValueError:
        return None
    return value if value > 0 else None


def _extract_characters(sentences: list[str]) -> list[dict[str, Any]]:
    names: list[str] = []
    for sentence in sentences:
        explicit_patterns = [
            r"^([\u4e00-\u9fff]{1,6})(?=（)",
            r"^([\u4e00-\u9fff]{1,6})[：:]\s*",
            r"^([\u4e00-\u9fff]{1,6})，",
        ]
        for pattern in explicit_patterns:
            for name in re.findall(pattern, sentence):
                normalized = "主角" if name == "我" else name
                if _is_plausible_character_name(normalized) and normalized not in names:
                    names.append(normalized)

    if not names:
        heuristic_pattern = r"([\u4e00-\u9fff]{2,4})(?=(?:走|说|看|抬|拿|站|坐|推|回|来到|进入|发现|穿|撑|收起|转身|低头|抬头|奔向|望向))"
        for sentence in sentences:
            for name in re.findall(heuristic_pattern, sentence):
                if _is_plausible_character_name(name) and name not in names:
                    names.append(name)

    characters: list[dict[str, Any]] = []
    for index, name in enumerate(names[:12], start=1):
        context = next((sentence for sentence in sentences if name in sentence), "")
        costume = _extract_costume(context)
        appearance = _extract_appearance(context)
        character_id = f"C{index:03d}"
        characters.append(
            {
                "id": character_id,
                "name": name,
                "role": "主要角色" if index == 1 else "配角",
                "age": "待确认",
                "personality": _infer_personality(context),
                "appearance": appearance,
                "costume": costume,
                "props": [],
                "expression_profile": ["观察", "紧张", "犹豫", "释然"],
                "voice_profile": "待确认",
                "continuity_anchors": [f"{name} 的身份和外观在所有镜头中保持一致"],
                "status": "待确认",
                "turnaround_prompt": (
                    f"{name} 角色四视图，纯白背景；左侧为面部特写，右侧为全身正面、侧面、背面，"
                    f"全身站立，正面视角，从头到脚完整入镜，双手自然垂落，不持物，表情中性，"
                    f"{appearance}，{costume}，鞋子完整可见，沿用项目视觉风格，细节清晰，无文字无水印"
                ),
                "expression_prompt": (
                    f"{name} 表情设定表：观察、紧张、犹豫、释然，保持相同脸型、发型和服装，"
                    "二维动画角色设定图"
                ),
                "negative_prompt": "服装无故变化，发色变化，多余人物，多余肢体，文字，水印，模糊",
            }
        )
    return characters


def _extract_locations(script: str) -> list[str]:
    matches: list[str] = []
    suffix_pattern = "|".join(map(re.escape, _LOCATION_SUFFIXES))
    pattern = rf"([\u4e00-\u9fff]{{0,10}}(?:{suffix_pattern}))"
    for value in re.findall(pattern, script):
        cleaned = value.strip("，。！？；： ")
        if cleaned and cleaned not in matches:
            matches.append(cleaned)
    return matches[:10]


def _extract_explicit_scenes(script: str, visual_style: str) -> list[dict[str, Any]]:
    scenes: list[dict[str, Any]] = []
    for raw_line in script.splitlines():
        line = raw_line.strip()
        if not line.startswith("【场景】"):
            continue
        body = line.split("】", 1)[1].strip()
        location = re.split(r"\s+", body, maxsplit=1)[0].strip("，。")
        if not location:
            continue
        time_value = _first_match(body, _TIME_WORDS) or _first_match(script, _TIME_WORDS) or "时间待确认"
        weather_value = _first_match(body, _WEATHER_WORDS) or _first_match(script, _WEATHER_WORDS) or "天气待确认"
        scene_name = re.split(r"[·•/／]", location)[-1].strip() or location
        scene_id = f"S{len(scenes) + 1:03d}"
        scenes.append(
            {
                "id": scene_id,
                "name": scene_name,
                "location": location,
                "time": time_value,
                "weather": weather_value,
                "layout": f"{scene_name} 保持前景、中景、背景的深度关系，关键入口与床榻/桌案位置固定。",
                "lighting": _scene_lighting_from_text(body),
                "palette": _color_script(body, weather_value),
                "fixed_elements": _scene_fixed_elements(scene_name, body),
                "atmosphere": _infer_tone(body),
                "status": "待确认",
                "environment_prompt": (
                    f"{visual_style}场景设定，{location}，{time_value}，{weather_value}，无人物，"
                    "同一空间的正打、反打和侧面全景，站位与空间关系清晰，"
                    "光线色调统一，固定陈设稳定，无文字无水印。"
                ),
                "negative_prompt": "空间跳变，朝代错乱，额外人物，字幕，文字气泡，低清晰度，过曝，模糊背景",
            }
        )
    return scenes


def _build_scenes(
    locations: list[str],
    script: str,
    visual_style: str,
) -> list[dict[str, Any]]:
    scenes: list[dict[str, Any]] = []
    time_value = _first_match(script, _TIME_WORDS) or "时间待确认"
    weather_value = _first_match(script, _WEATHER_WORDS) or "天气待确认"
    for index, location in enumerate(locations, start=1):
        scene_id = f"S{index:03d}"
        lighting = "自然光，光线方向待确认"
        if any(word in script for word in ("夜", "深夜", "凌晨")):
            lighting = "低照度夜景光线，局部光源形成空间层次"
        fixed_elements = _scene_fixed_elements(location, script)
        context = next((line.strip() for line in script.splitlines() if location in line), script[:160])
        scenes.append(
            {
                "id": scene_id,
                "name": location,
                "location": location,
                "time": time_value,
                "weather": weather_value,
                "layout": (
                    f"前景：{fixed_elements[0] if fixed_elements else location}；"
                    f"中景：{fixed_elements[1] if len(fixed_elements) > 1 else '人物活动区待确认'}；"
                    f"背景：{fixed_elements[2] if len(fixed_elements) > 2 else '空间边界待确认'}。"
                    f"剧本场景证据：{context}"
                ),
                "lighting": lighting,
                "palette": "根据视觉风格统一色彩，主体与背景保持可分离",
                "fixed_elements": fixed_elements or [location, "固定陈设待确认"],
                "atmosphere": _infer_tone(script),
                "status": "待确认",
                "environment_prompt": (
                    f"{visual_style}场景设定，{location}，{time_value}，{weather_value}，无人物，"
                    "正打、反打和侧面全景，电影感构图，空间纵深清晰，建筑结构和固定道具连续，无文字无水印"
                ),
                "negative_prompt": "空间结构跳变，时间天气无故变化，新增建筑，错误文字，水印，低清晰度",
            }
        )
    return scenes


def _build_props(script: str, characters: list[dict[str, Any]]) -> list[dict[str, Any]]:
    props: list[dict[str, Any]] = []
    for index, prop_name in enumerate(_unique_matches(script, _PROP_WORDS), start=1):
        owner = characters[0]["name"] if characters else "待确认"
        evidence = next((line.strip() for line in script.splitlines() if prop_name in line), "")
        if not evidence:
            evidence = next((sentence.strip() for sentence in _sentences(script) if prop_name in sentence), "")
        props.append(
            {
                "id": f"P{index:03d}",
                "name": prop_name,
                "description": (
                    f"剧本证据：{evidence or '待确认'}；"
                    f"{prop_name} 的外形、材质、颜色和磨损痕迹以剧本明确描述为准，未提供部分待确认；"
                    f"剧情用途：{_prop_usage(prop_name, evidence)}"
                ),
                "owner": owner,
                "continuity_notes": f"{prop_name} 的位置和持有者随剧情节点连续变化",
            }
        )
    return props


def _prop_usage(prop_name: str, evidence: str) -> str:
    if any(word in evidence for word in ("发现", "收到", "找到", "揭开")):
        return f"作为情节线索被发现或揭示（{prop_name}）"
    if any(word in evidence for word in ("撑", "拿", "握", "抱", "戴", "挂")):
        return f"作为角色动作中的可见道具（{prop_name}）"
    if any(word in evidence for word in ("打", "刺", "砍", "指向", "击")):
        return f"作为冲突动作的关键道具（{prop_name}）"
    return "剧情用途待确认"


def _build_production_locks(
    visual_style: str,
    characters: list[dict[str, Any]],
    scenes: list[dict[str, Any]],
) -> dict[str, Any]:
    character_names = "、".join(character["name"] for character in characters[:3]) or "主角"
    scene_names = "、".join(scene["name"] for scene in scenes[:2]) or "主场景"
    return {
        "character_lock": f"{character_names} 的脸型、发型、服装层次与标志性道具在全片保持一致。",
        "scene_lock": f"{scene_names} 的空间朝向、固定陈设和主光源方向不能跳变。",
        "style_core": f"{visual_style}，竖屏漫剧，线条清晰，重点突出人物表情和动作节拍。",
        "visual_tone": "前3秒必须给出强视觉钩子，后续每3-5秒出现一次明确视觉变化。",
        "color_lighting": "情绪压迫段使用冷色主调，反击或转折瞬间加入局部暖色或高对比补光。",
        "camera_rules": "单镜头内只保留一种主要覆盖模式，避免镜头路径自相矛盾。",
        "action_intensity": "动作先触发、再表情、后肢体，保证竖屏观感一眼可读。",
        "continuity_lock": "道具位置、视线方向、角色站位和伤痕服装状态必须跨镜头稳定。",
        "sound_mood": "对白、旁白和音效按动作时间轴进入；只生成音效，不生成音乐，不烧录字幕。",
        "forbidden_drift": "禁止角色脸崩、服装跳变、空间重置、道具消失、字幕烧录。",
    }


def _build_material_map(
    characters: list[dict[str, Any]],
    scenes: list[dict[str, Any]],
    props: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    materials: list[dict[str, Any]] = []
    for index, character in enumerate(characters[:3], start=1):
        materials.append(
            {
                "id": f"@图片{index}",
                "type": "角色",
                "purpose": f"锁定 {character['name']} 的身份和服装连续性",
                "notes": "适用于近景、特写和正反打镜头",
                "prompt": character.get("turnaround_prompt", ""),
            }
        )
    base_index = len(materials)
    for offset, scene in enumerate(scenes[:2], start=1):
        materials.append(
            {
                "id": f"@图片{base_index + offset}",
                "type": "场景",
                "purpose": f"锁定 {scene['name']} 的空间结构与光线",
                "notes": "适用于建立镜头与场景回切",
                "prompt": scene.get("environment_prompt", ""),
            }
        )
    if props:
        prop = props[0]
        materials.append(
            {
                "id": f"@图片{len(materials) + 1}",
                "type": "道具",
                "purpose": f"锁定关键道具 {prop['name']} 的造型和位置",
                "notes": "适用于特写与交接动作镜头",
                "prompt": f"{prop['name']} 道具独立设定图，纯白背景，不出现人物和真实环境，材质、年代感与使用痕迹清晰，无文字无水印。",
            }
        )
    return materials


def _build_join_contracts(shots: list[dict[str, Any]]) -> list[dict[str, Any]]:
    contracts: list[dict[str, Any]] = []
    for previous, current in zip(shots, shots[1:]):
        previous_action = str(previous.get("visual_action", "")).strip() or "上一镜头动作"
        current_action = str(current.get("visual_action", "")).strip() or "下一镜头动作"
        same_scene = previous.get("scene_id") == current.get("scene_id")
        contracts.append(
            {
                "from_shot": str(previous.get("id", "")),
                "to_shot": str(current.get("id", "")),
                "previous_end_state": str(previous.get("last_frame_prompt", "")).strip() or previous_action,
                "next_start_state": str(current.get("first_frame_prompt", "")).strip() or current_action,
                "state_delta": f"{previous_action} -> {current_action}",
                "risk_level": "low" if same_scene else "medium",
                "hard_cut_allowed": bool(same_scene),
                "bridge_requirement": "" if same_scene else "需要环境或反应镜头缓冲空间切换",
                "bridge_prompt_id": "",
                "safety_inserts": [],
                "sound_bridge": str(current.get("sound_design", "")).strip(),
                "fallback_edit": "必要时补一个手部/眼神/环境反应镜头做桥接",
            }
        )
    return contracts


def _build_shots(
    sentences: list[str],
    characters: list[dict[str, Any]],
    scenes: list[dict[str, Any]],
    props: list[dict[str, Any]],
    visual_style: str,
    target_runtime: float | None = None,
) -> list[dict[str, Any]]:
    shots: list[dict[str, Any]] = []
    current_time = 0.0
    for index, sentence in enumerate(sentences[:20], start=1):
        duration = min(5.0, max(2.5, round(1.8 + len(sentence) / 28, 1)))
        scene = scenes[min(index - 1, len(scenes) - 1)]
        sentence_character_ids = [
            character["id"] for character in characters if character["name"] in sentence
        ]
        if sentence_character_ids:
            character_ids = sentence_character_ids
        elif _looks_like_environment_only(sentence):
            character_ids = []
        else:
            character_ids = [characters[0]["id"]] if characters else []
        prop_ids = [prop["id"] for prop in props if prop["name"] in sentence]
        shot_id = f"SH{index:03d}"
        shot_size = _shot_size(sentence, index)
        motion = _camera_motion(sentence, index)
        emotion = _infer_emotion(sentence)
        action = _clean_action(sentence)
        beats = _beats(duration, action, emotion)
        character_names = "、".join(
            character["name"] for character in characters if character["id"] in character_ids
        ) or "无人物出镜"
        prop_names = [prop["name"] for prop in props if prop["id"] in prop_ids]
        camera_position = _camera_position(shot_size, sentence)
        lens = _lens_for_shot_size(shot_size)
        dialogue = _dialogue(sentence)
        narration = _narration(sentence)
        sound_design = _sound_design(sentence)
        first_frame_prompt = _build_first_frame_prompt(
            scene,
            character_names,
            action,
            shot_size,
            camera_position,
            lens,
            emotion,
            prop_names,
            visual_style,
        )
        last_frame_prompt = _build_last_frame_prompt(
            scene,
            character_names,
            action,
            shot_size,
            camera_position,
            emotion,
            prop_names,
            visual_style,
        )
        shots.append(
            {
                "id": shot_id,
                "scene_id": scene["id"],
                "character_ids": character_ids,
                "prop_ids": prop_ids,
                "start_second": current_time,
                "duration_seconds": duration,
                "shot_size": shot_size,
                "camera_position": camera_position,
                "lens": lens,
                "camera_motion": motion,
                "visual_action": action,
                "dialogue": dialogue,
                "narration": narration,
                "sound_design": sound_design,
                "action_beats": beats,
                "prompt_id": f"VIDEO_MAIN_{shot_id}",
                "state_contract": _build_state_contract(
                    scene,
                    character_names,
                    action,
                    shot_size,
                    camera_position,
                    motion,
                    emotion,
                    prop_names,
                    first_frame_prompt,
                    last_frame_prompt,
                ),
                "first_frame_prompt": first_frame_prompt,
                "video_prompt": _build_video_prompt(
                    scene,
                    character_names,
                    action,
                    shot_size,
                    camera_position,
                    lens,
                    motion,
                    emotion,
                    prop_names,
                    visual_style,
                    duration,
                    beats,
                    dialogue,
                    narration,
                    sound_design,
                    first_frame_prompt,
                    last_frame_prompt,
                ),
                "last_frame_prompt": last_frame_prompt,
                "negative_prompt": _negative_prompt_for_shot(shot_size),
                "continuity_requirements": [
                    f"保持 {character_names} 的身份、服装与情绪走向连续",
                    f"保持 {scene['name']} 的空间结构、光向和关键道具位置稳定",
                    "镜头结尾必须停在可衔接下一镜的稳定状态，不能中途跳切",
                ],
                "expected_failures": _expected_failures(shot_size, motion),
                "repair_strategy": _repair_strategy(shot_size, motion),
                "confidence": "medium",
                "status": "待确认",
            }
        )
        current_time = round(current_time + duration, 1)
    if target_runtime is not None and shots:
        _scale_shot_runtime(shots, target_runtime)
    return shots


def _fallback_character(title: str, sentences: list[str]) -> dict[str, Any]:
    context = sentences[0] if sentences else title
    return {
        "id": "C001",
        "name": "主角（待命名）",
        "role": "主要角色",
        "age": "待确认",
        "personality": _infer_personality(context),
        "appearance": "外观待确认",
        "costume": "服装待确认",
        "props": [],
        "expression_profile": ["观察", "紧张", "释然"],
        "voice_profile": "待确认",
        "continuity_anchors": ["角色身份和外观需要在后续确认"],
        "status": "待确认",
        "turnaround_prompt": "主角角色四视图，纯白背景，左侧面部特写，右侧全身正面、侧面、背面；从头到脚完整入镜，双手自然垂落，不持物，表情中性，鞋子完整可见，外观和服装待确认，无文字无水印",
        "expression_prompt": "主角表情设定表：观察、紧张、释然，二维动画角色设定图",
        "negative_prompt": "角色身份变化，服装变化，多余人物，文字，水印，低清晰度",
    }


def _fallback_scene(time_value: str, weather: str, style: str) -> dict[str, Any]:
    return {
        "id": "S001",
        "name": "未命名场景",
        "location": "地点待确认",
        "time": time_value,
        "weather": weather,
        "layout": "空间布局待确认",
        "lighting": "光线待确认",
        "palette": style,
        "fixed_elements": ["待确认"],
        "atmosphere": "待确认",
        "status": "待确认",
        "environment_prompt": f"{style}场景设定，地点待确认，{time_value}，{weather}，场景中无人物，正打、反打、侧面全景，电影感空间构图，无文字无水印",
        "negative_prompt": "空间结构跳变，错误时间，错误天气，文字，水印，低清晰度",
    }


def _fallback_shot(
    sentences: list[str],
    characters: list[dict[str, Any]],
    scenes: list[dict[str, Any]],
    props: list[dict[str, Any]],
    style: str,
) -> list[dict[str, Any]]:
    sentence = sentences[0] if sentences else "主角的动作待确认"
    return _build_shots([sentence], characters, scenes, props, style)


def _title_from_script(script: str) -> str:
    match = re.search(r"《([^》]+)》", script)
    return match.group(1) if match else "未命名剧本"


def _extract_marker_block(value: str, marker: str) -> str:
    if marker not in value:
        return value
    block = value.split(marker, 1)[1]
    for stop_marker in ("JSON 顶层结构必须包含：", "字段要求："):
        if stop_marker in block:
            block = block.split(stop_marker, 1)[0]
    return block.strip()


def _extract_labeled_value(value: str, marker: str) -> str:
    if marker not in value:
        return ""
    return value.split(marker, 1)[1].split("\n", 1)[0].strip()


def _extract_json_after_marker(value: str, marker: str) -> dict[str, Any]:
    import json

    raw = value.split(marker, 1)[1].strip()
    parsed = json.loads(raw)
    if not isinstance(parsed, dict):
        raise ValueError("离线渲染数据不是 JSON 对象。")
    return parsed


def _first_match(script: str, choices: tuple[str, ...]) -> str:
    return next((choice for choice in choices if choice in script), "")


def _unique_matches(script: str, choices: tuple[str, ...]) -> list[str]:
    return [choice for choice in choices if choice in script]


def _extract_costume(context: str) -> str:
    match = re.search(r"(?:穿着|身穿|穿|披着|戴着)([^，。；\n]{2,24})", context)
    return match.group(1) if match else "服装品类、主色、材质或层次：剧本未提供，待确认"


def _extract_appearance(context: str) -> str:
    match = re.search(r"(?:黑色|白色|棕色|短发|长发|年轻|老人|女孩|男孩|女子|男人)[^，。；\n]{0,20}", context)
    return match.group(0) if match else "脸型、发型发色、体型或年龄感：剧本未提供，待确认"


def _is_plausible_character_name(name: str) -> bool:
    if name in _COMMON_FALSE_NAMES:
        return False
    if name != "主角" and not (1 <= len(name) <= 4):
        return False
    invalid_keywords = ("满脸", "胸口", "殿宇", "殿内", "寒风", "签字", "痛快", "微", "燃尽")
    return not any(keyword in name for keyword in invalid_keywords)


def _infer_personality(context: str) -> str:
    if any(word in context for word in ("犹豫", "沉默", "低头", "独自")):
        return "克制、敏感、内敛"
    if any(word in context for word in ("奔跑", "冲向", "拔出", "怒")):
        return "果断、强烈、行动导向"
    if any(word in context for word in ("笑", "温柔", "拥抱")):
        return "温和、亲近、情感外露"
    return "性格待确认"


def _infer_genre(script: str) -> str:
    genres = {
        "悬疑": ("悬疑", "秘密", "信封", "失踪", "真相"),
        "爱情": ("喜欢", "爱", "告白", "拥抱", "恋人"),
        "动作": ("追", "战斗", "刀", "枪", "爆炸"),
        "奇幻": ("魔法", "龙", "穿越", "异世界", "精灵"),
        "古装": ("皇宫", "江湖", "王爷", "将军", "古代"),
    }
    found = [name for name, words in genres.items() if any(word in script for word in words)]
    return "、".join(found) if found else "剧情短片"


def _infer_tone(script: str) -> str:
    if any(word in script for word in ("雨", "夜", "孤独", "沉默", "秘密")):
        return "克制、安静、带有悬念"
    if any(word in script for word in ("战斗", "追逐", "爆炸", "冲向")):
        return "紧张、快速、强动作"
    if any(word in script for word in ("笑", "拥抱", "阳光", "温柔")):
        return "温暖、明亮、情绪外露"
    return "情绪待确认"


def _color_script(script: str, weather: str) -> str:
    if any(word in script for word in ("夜", "雨", "阴")):
        return "低饱和冷色为主，在剧情转折处加入局部暖色光源"
    if any(word in script for word in ("阳光", "晴", "清晨")):
        return "明亮自然色，关键情绪用柔和暖色强化"
    return f"根据{weather}和剧情情绪自动调整，具体色彩待确认"


def _logline(sentences: list[str], title: str) -> str:
    if not sentences:
        return f"{title}：剧情梗概待确认。"
    first = sentences[0].rstrip("。！？")
    second = sentences[1].rstrip("。！？") if len(sentences) > 1 else ""
    return f"{first}；{second}" if second else first


def _unresolved_questions(
    script: str,
    characters: list[dict[str, Any]],
    scenes: list[dict[str, Any]],
) -> list[str]:
    questions: list[str] = []
    if any(character["age"] == "待确认" for character in characters):
        questions.append("主要角色年龄和外观细节是否需要补充？")
    if any(scene["location"] == "地点待确认" for scene in scenes):
        questions.append("是否需要补充具体地点和空间结构？")
    if "？" in script or "?" in script:
        questions.append("剧本中的问句是否需要作为对白或旁白保留？")
    return questions


def _shot_size(sentence: str, index: int) -> str:
    if any(word in sentence for word in ("特写", "眼底", "指尖", "唇角", "脸颊", "目光")):
        return "特写"
    if any(word in sentence for word in ("近景", "抓起", "拍在", "抬手", "咬牙", "睁眼")):
        return "近景"
    if any(word in sentence for word in ("中景", "上前", "对峙", "站在", "闯入", "甩门")):
        return "中景"
    if any(word in sentence for word in ("全景", "殿宇", "寝宫", "众人", "环境", "外景")):
        return "全景"
    return ("全景", "中景", "近景", "特写")[min(index - 1, 3)]


def _camera_motion(sentence: str, index: int) -> str:
    if any(word in sentence for word in ("猛切", "巨响", "甩门", "闯入")):
        return "快速切入后轻微跟拍"
    if any(word in sentence for word in ("缓缓", "睁眼", "精光", "寒光")):
        return "缓慢推进"
    if any(word in sentence for word in ("走", "上前", "小跑", "离去")):
        return "平稳跟拍"
    if any(word in sentence for word in ("特写", "盯", "直视", "咬牙")):
        return "轻微停顿后微推"
    return ("缓慢推进", "平稳横移", "轻微跟拍", "静止观察")[min(index - 1, 3)]


def _camera_position(shot_size: str, sentence: str) -> str:
    if shot_size == "全景":
        return "竖屏构图下的平视建立机位，带轻微俯角观察空间纵深"
    if shot_size == "中景":
        return "人物胸口到膝部的平视机位，保留角色对峙关系"
    if shot_size == "近景":
        return "胸像近景机位，镜头略向主导角色倾斜以强调压迫感"
    if "床" in sentence or "卧" in sentence:
        return "靠近床榻侧前方的平视机位，突出人物病态与空间压迫"
    return "面部与手部并重的近距离特写机位，聚焦眼神与微表情"


def _lens_for_shot_size(shot_size: str) -> str:
    if shot_size == "全景":
        return "24mm 广角，保留空间层次"
    if shot_size == "中景":
        return "35mm 纪实焦段，兼顾人物与环境"
    if shot_size == "近景":
        return "50mm 标准焦段，主体突出，背景轻微虚化"
    return "85mm 轻长焦，强调眼神、嘴角和细微动作"


def _infer_emotion(sentence: str) -> str:
    if any(word in sentence for word in ("惊", "发现", "警觉", "害怕")):
        return "警觉"
    if any(word in sentence for word in ("笑", "温柔", "拥抱")):
        return "温柔"
    if any(word in sentence for word in ("怒", "冲", "追")):
        return "紧张"
    return "克制"


def _clean_action(sentence: str) -> str:
    cleaned = sentence.rstrip("。！？；;")
    cleaned = re.sub(r"^[\u4e00-\u9fff]{1,4}[：:]\s*", "", cleaned)
    cleaned = re.sub(r"^旁白：", "", cleaned)
    return cleaned.strip()


def _dialogue(sentence: str) -> str:
    match = re.search(r"[\u4e00-\u9fff]{1,6}[：:](.+)", sentence)
    return match.group(1).strip() if match else ""


def _narration(sentence: str) -> str:
    return sentence.replace("旁白：", "").strip() if "旁白：" in sentence else ""


def _sound_design(sentence: str) -> str:
    sounds = []
    for word in ("雨", "风", "雷", "脚步", "门", "枪", "爆炸", "音乐", "寒风", "风铃", "药雾", "珠翠", "拍桌", "甩门"):
        if word in sentence:
            sounds.append(f"{word}声")
    return "、".join(sounds) if sounds else "环境声根据场景生成"


def _looks_like_environment_only(sentence: str) -> bool:
    if _dialogue(sentence) or _narration(sentence):
        return False
    environment_keywords = (
        "殿宇",
        "墙皮",
        "木窗",
        "窗棂",
        "炭火",
        "寒风",
        "药雾",
        "满屋",
        "场景",
        "黑屏字幕",
    )
    return any(word in sentence for word in environment_keywords)


def _beats(duration: float, action: str, emotion: str) -> list[dict[str, Any]]:
    middle = round(duration / 2, 1)
    return [
        {
            "start_second": 0.0,
            "end_second": middle,
            "action": f"前半段建立状态：{action}",
            "emotion": emotion,
            "continuity_notes": "先给出清晰姿态、视线方向和关键道具位置",
        },
        {
            "start_second": middle,
            "end_second": round(duration, 1),
            "action": f"后半段完成变化：{action}",
            "emotion": emotion,
            "continuity_notes": "把动作停在下一个镜头可承接的稳定姿态",
        },
    ]


def _scene_lighting_from_text(text: str) -> str:
    if any(word in text for word in ("深夜", "夜", "寒风")):
        return "冷色夜景主调，主光来自窗外或门口，室内残火做局部补光"
    if any(word in text for word in ("黄昏", "傍晚")):
        return "斜向暖色夕光与冷色环境光并置"
    return "主光源明确、阴影柔和，保证竖屏下人物轮廓清晰"


def _scene_fixed_elements(scene_name: str, text: str) -> list[str]:
    elements = [scene_name]
    for word in ("床榻", "木门", "窗棂", "桌案", "帛书", "炭火", "风铃"):
        if word in text:
            elements.append(word)
    return elements


def _build_state_contract(
    scene: dict[str, Any],
    character_names: str,
    action: str,
    shot_size: str,
    camera_position: str,
    motion: str,
    emotion: str,
    prop_names: list[str],
    first_frame_prompt: str,
    last_frame_prompt: str,
) -> dict[str, Any]:
    prop_state = "、".join(prop_names) if prop_names else "无显性关键道具或由画面补足"
    return {
        "reference_roles": [
            f"角色参考：{character_names}",
            f"场景参考：{scene.get('name', '主场景')}",
        ],
        "first_visible_frame": first_frame_prompt,
        "screen_layout": f"{shot_size} 竖屏构图，主体居中偏上，背景保留 {scene.get('name', '场景')} 的深度层次。",
        "subject_state": f"{character_names} 处于“{emotion}”情绪下，准备进入动作“{action}”。",
        "performance_cause": f"先交代触发事件，再显露眼神/嘴角细节，最后完成肢体动作“{action}”。",
        "prop_state": prop_state,
        "camera_coverage_mode": "单镜头内以一种覆盖模式完成信息传递，避免无故切换视角",
        "camera_path": f"{camera_position}，镜头运动为“{motion}”。",
        "action_transition": f"本镜头唯一主要变化：{action}",
        "final_visible_frame": last_frame_prompt,
        "hard_limits": [
            "不新增剧本没有交代的关键人物或道具",
            "不烧录字幕，不生成文字气泡",
            "镜头结尾必须停在可承接状态",
        ],
    }


def _build_first_frame_prompt(
    scene: dict[str, Any],
    character_names: str,
    action: str,
    shot_size: str,
    camera_position: str,
    lens: str,
    emotion: str,
    prop_names: list[str],
    visual_style: str,
) -> str:
    props = "、".join(prop_names) if prop_names else "无显性道具"
    return (
        f"9:16竖屏漫剧首帧，{scene.get('location', scene.get('name', '未命名场景'))}，"
        f"{scene.get('time', '时间待确认')}，{scene.get('weather', '天气待确认')}，{shot_size}，"
        f"{camera_position}，{lens}，{character_names} 入画前的稳定姿态，动作主题“{action}”尚未爆发，"
        f"情绪为{emotion}，关键道具：{props}，固定元素：{'、'.join(scene.get('fixed_elements', [])) or '待确认'}，"
        f"主光：{scene.get('lighting', '光线待确认')}，{visual_style}，线条清晰，人物脸部不崩，画面中无字幕无文字气泡。"
    )


def _build_last_frame_prompt(
    scene: dict[str, Any],
    character_names: str,
    action: str,
    shot_size: str,
    camera_position: str,
    emotion: str,
    prop_names: list[str],
    visual_style: str,
) -> str:
    props = "、".join(prop_names) if prop_names else "无显性道具"
    return (
        f"9:16竖屏漫剧尾帧，{scene.get('name', '未命名场景')} 保持空间连续，{shot_size}，"
        f"{camera_position}，{character_names} 完成“{action}”后的可剪停顿姿态，"
        f"表情停在{emotion}与下一镜可衔接的过渡点，关键道具：{props} 保持位置稳定，"
        f"{visual_style}，无字幕、无水印、无多余人物。"
    )


def _build_video_prompt(
    scene: dict[str, Any],
    character_names: str,
    action: str,
    shot_size: str,
    camera_position: str,
    lens: str,
    motion: str,
    emotion: str,
    prop_names: list[str],
    visual_style: str,
    duration: float,
    beats: list[dict[str, Any]],
    dialogue: str,
    narration: str,
    sound_design: str,
    first_frame_prompt: str,
    last_frame_prompt: str,
) -> str:
    props = "、".join(prop_names) if prop_names else "无显性道具"
    beat_lines = []
    for beat in beats:
        beat_lines.append(
            f"{beat['start_second']:.1f}-{beat['end_second']:.1f}s：{beat['action']}；情绪 {beat['emotion']}；{beat['continuity_notes']}"
        )
    audio_parts = []
    if dialogue:
        audio_parts.append(f"[对白：{dialogue}]")
    if narration:
        audio_parts.append(f"[旁白：{narration}]")
    if sound_design:
        audio_parts.append(f"[音效：{sound_design}]")
    audio_text = " ".join(audio_parts) if audio_parts else "[音效：环境声轻垫底，给角色动作留停顿]"
    return (
        f"Seedance 2.0 视频提示词，9:16竖屏，时长 {duration:.1f}s，视觉风格：{visual_style}，"
        f"场景：{scene.get('location', scene.get('name', '未命名场景'))}，"
        f"{scene.get('time', '时间待确认')}，{scene.get('weather', '天气待确认')}，镜头类型：{shot_size}，"
        f"机位：{camera_position}，焦段：{lens}，运镜：{motion}，角色一致性锁定：{character_names}，"
        f"关键道具：{props}。首帧：{first_frame_prompt}。"
        f"镜头目标：围绕“{action}”完成一个清晰可读的视觉动作，并在 3-5 秒窗口内给出至少一次可见变化。"
        f"表演顺序：触发事件 -> 眼神/嘴角微表情 -> 肢体动作 -> 收束停顿，情绪基调 {emotion}。"
        f"时间轴：{'；'.join(beat_lines)}。{audio_text}。"
        f"【声音】只生成对白、旁白和环境/动作音效，不生成音乐。不要生成任何字幕。"
        f"尾帧：{last_frame_prompt}。禁止镜头乱切、角色换脸、服装跳变、空间重置、字幕、文字和水印。"
    )


def _negative_prompt_for_shot(shot_size: str) -> str:
    shot_bias = {
        "全景": "背景建筑错位，纵深消失，人物比例失衡",
        "中景": "双人对峙站位错乱，手臂畸形，服装层级错位",
        "近景": "手部扭曲，面部崩坏，眼神漂移",
        "特写": "五官比例异常，眼睛错位，嘴型失真，皮肤塑料感",
    }
    return (
        f"{shot_bias.get(shot_size, '人物崩坏')}，角色身份变化，服装变化，道具消失，场景跳变，"
        "镜头路径矛盾，字幕，文字气泡，水印，低清晰度，过曝，严重运动拖影。"
    )


def _expected_failures(shot_size: str, motion: str) -> list[str]:
    failures = ["角色脸型漂移", "服装与发型跨镜头不一致"]
    if shot_size in {"近景", "特写"}:
        failures.extend(["嘴型和眼神失真", "手部或指尖畸形"])
    if "跟拍" in motion or "推进" in motion:
        failures.append("运镜时背景抖动或空间透视崩坏")
    return failures


def _repair_strategy(shot_size: str, motion: str) -> str:
    if shot_size == "特写":
        return "若面部失真，缩短时长到 2.5-3 秒，固定机位，只保留眼神和嘴角变化。"
    if "跟拍" in motion:
        return "若运镜不稳，改为静止观察或微推镜头，并拆成前后两个短镜头。"
    return "若画面信息过密，先保留单一动作主线，再补一个反应镜头或环境镜头。"


def _scale_shot_runtime(shots: list[dict[str, Any]], target_runtime: float) -> None:
    total = sum(float(shot.get("duration_seconds", 0.0)) for shot in shots)
    if total <= 0:
        return
    scale = target_runtime / total
    current_time = 0.0
    for index, shot in enumerate(shots):
        original_duration = float(shot.get("duration_seconds", 3.0))
        if index == len(shots) - 1:
            duration = round(max(2.0, target_runtime - current_time), 1)
        else:
            duration = round(min(5.0, max(2.0, original_duration * scale)), 1)
        shot["start_second"] = round(current_time, 1)
        shot["duration_seconds"] = duration
        shot["action_beats"] = _beats(
            duration,
            str(shot.get("visual_action", "")),
            _infer_emotion(str(shot.get("visual_action", ""))),
        )
        current_time = round(current_time + duration, 1)
