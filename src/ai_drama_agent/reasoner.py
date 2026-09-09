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
    characters = _extract_characters(story_units, visual_style)
    locations = _extract_locations(script)
    scenes = _extract_explicit_scenes(script, visual_style) or _build_scenes(locations, script, visual_style)
    if not characters:
        characters = [_fallback_character(title, story_units, visual_style)]
    if not scenes:
        timeline = _first_match(script, _TIME_WORDS) or "白天"
        weather = _reasonable_weather(script, timeline)
        scenes = [_fallback_scene(script, timeline, weather, visual_style)]
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
    timeline = _first_match(script, _TIME_WORDS) or "白天"
    weather = _reasonable_weather(script, timeline)
    source_hash = hashlib.sha256(script.encode("utf-8")).hexdigest()[:12]
    if not shots:
        shots = _fallback_shot(story_units, characters, scenes, props, visual_style)

    world_rules = [
        "角色外观、服装和关键道具在没有剧情依据时保持不变。",
        "镜头时间轴必须连续，首帧和尾帧要能衔接下一镜。",
        "不改变剧本关键因果；缺失的视觉制作细节由系统定稿并在全片保持一致。",
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
            "unresolved_questions": [],
        },
        "characters": characters,
        "scenes": scenes,
        "props": props,
        "shots": shots,
        "production_locks": _build_production_locks(visual_style, characters, scenes),
        "material_map": _build_material_map(characters, scenes, props, visual_style),
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


def _extract_characters(sentences: list[str], visual_style: str) -> list[dict[str, Any]]:
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
                "age": _extract_age(context),
                "personality": _infer_personality(context),
                "appearance": appearance,
                "costume": costume,
                "props": [],
                "expression_profile": ["观察", "紧张", "犹豫", "释然"],
                "voice_profile": "自然中文对白，音色清晰，情绪克制",
                "continuity_anchors": [f"{name} 的身份和外观在所有镜头中保持一致"],
                "status": "confirmed",
                "turnaround_prompt": _build_character_turnaround_prompt(name, appearance, costume, visual_style),
                "expression_prompt": _build_character_expression_prompt(
                    name, appearance, costume, visual_style, "主要角色" if index == 1 else "配角", _extract_age(context)
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
        time_value = _first_match(body, _TIME_WORDS) or _first_match(script, _TIME_WORDS) or "白天"
        weather_value = _reasonable_weather(body or script, time_value)
        scene_name = re.split(r"[·•/／]", location)[-1].strip() or location
        scene_id = f"S{len(scenes) + 1:03d}"
        scenes.append(
            {
                "id": scene_id,
                "name": scene_name,
                "location": location,
                "time": time_value,
                "weather": weather_value,
                "layout": f"前景、中景、背景层次明确，{scene_name} 的主要入口与固定陈设位置稳定，角色走位沿原有动线展开。",
                "lighting": _scene_lighting_from_text(body),
                "palette": _color_script(body, weather_value),
                "fixed_elements": _scene_fixed_elements(scene_name, body),
                "atmosphere": _infer_tone(body),
                "status": "confirmed",
                "environment_prompt": _build_scene_environment_prompt(
                    visual_style,
                    location,
                    time_value,
                    weather_value,
                    f"前景、中景、背景层次明确，{scene_name} 的主要入口与固定陈设位置稳定，角色走位沿原有动线展开",
                    _scene_lighting_from_text(body),
                    _scene_fixed_elements(scene_name, body),
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
    time_value = _first_match(script, _TIME_WORDS) or "白天"
    weather_value = _reasonable_weather(script, time_value)
    for index, location in enumerate(locations, start=1):
        scene_id = f"S{index:03d}"
        lighting = "窗外自然散射光从画面左侧进入，5600K 中性日光，右侧柔和补光，阴影向右后方过渡"
        if any(word in script for word in ("夜", "深夜", "凌晨")):
            lighting = "低照度夜景光线，局部光源形成空间层次，色温偏冷"
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
                    f"中景：{fixed_elements[1] if len(fixed_elements) > 1 else '中央人物活动区'}；"
                    f"背景：{fixed_elements[2] if len(fixed_elements) > 2 else '后墙与主要出入口'}；"
                    "出入口与角色动线保持稳定。"
                    f"剧本场景证据：{context}"
                ),
                "lighting": lighting,
                "palette": "根据视觉风格统一色彩，主体与背景保持可分离",
                "fixed_elements": fixed_elements or [location, "主要出入口", "中央活动区", "后墙边界"],
                "atmosphere": _infer_tone(script),
                "status": "confirmed",
                "environment_prompt": _build_scene_environment_prompt(
                    visual_style,
                    location,
                    time_value,
                    weather_value,
                    (
                        f"前景：{fixed_elements[0] if fixed_elements else location}；"
                        f"中景：{fixed_elements[1] if len(fixed_elements) > 1 else '中央人物活动区'}；"
                        f"背景：{fixed_elements[2] if len(fixed_elements) > 2 else '后墙与主要出入口'}；"
                        "出入口与角色动线保持稳定。"
                    ),
                    lighting,
                    fixed_elements or [location, "主要出入口", "中央活动区", "后墙边界"],
                ),
                "negative_prompt": "空间结构跳变，时间天气无故变化，新增建筑，错误文字，水印，低清晰度",
            }
        )
    return scenes


def _build_props(script: str, characters: list[dict[str, Any]]) -> list[dict[str, Any]]:
    props: list[dict[str, Any]] = []
    for index, prop_name in enumerate(_unique_matches(script, _PROP_WORDS), start=1):
        owner = characters[0]["id"] if characters else "公共场景资产"
        evidence = next((line.strip() for line in script.splitlines() if prop_name in line), "")
        if not evidence:
            evidence = next((sentence.strip() for sentence in _sentences(script) if prop_name in sentence), "")
        props.append(
            {
                "id": f"P{index:03d}",
                "name": prop_name,
                "description": _build_prop_description(prop_name, evidence),
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
    return f"作为镜头中的关键可见物件推动动作或承载信息（{prop_name}）"


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
    visual_style: str = "电影感二维国漫",
) -> list[dict[str, Any]]:
    materials: list[dict[str, Any]] = []
    for character in characters:
        character_id = str(character.get("id") or "C001")
        turnaround = _build_character_turnaround_prompt(
            str(character.get("name") or "角色"),
            str(character.get("appearance") or _extract_appearance("")),
            str(character.get("costume") or _extract_costume("")),
            visual_style,
            str(character.get("role") or "主要角色"),
            str(character.get("age") or "28岁青年"),
        )
        materials.append(
            {
                "id": character_id,
                "type": "角色资产",
                "purpose": f"锁定 {character.get('name', '角色')} 的身份、脸部、身材比例、服装、鞋子和配饰",
                "notes": "分镜直接引用该角色编号；全身、转面设定板和肖像均继承同一身份锁",
                "prompt": _numbered_asset_prompt(
                    character_id,
                    "全身正面设定："
                    + _build_character_full_body_prompt(character, visual_style)
                    + " 转面设定板："
                    + turnaround
                    + " 肖像特写："
                    + _build_character_portrait_prompt(character, visual_style),
                ),
            }
        )
    for scene in scenes:
        scene_id = str(scene.get("id") or "S001")
        views = " ".join(
            _build_scene_view_prompt(scene, view_name, view_direction)
            for view_name, view_direction in (
                ("主视图", "从主要入口朝人物活动区拍摄"),
                ("反打", "从人物活动区朝主要入口反向拍摄"),
                ("侧广角", "从侧向墙面沿空间长轴拍摄"),
            )
        )
        materials.append(
            {
                "id": scene_id,
                "type": "场景资产",
                "purpose": f"锁定 {scene.get('name', '场景')} 的空间坐标、门窗、固定陈设和光线",
                "notes": "分镜直接引用该场景编号；主视图、反打和侧广角保持同一空间坐标",
                "prompt": _numbered_asset_prompt(scene_id, views),
            }
        )
    for prop in props:
        prop_id = str(prop.get("id") or "P001")
        state = _prop_plot_state(str(prop.get("description") or ""))
        state_prompt = (
            " 剧情状态：" + _build_prop_asset_prompt(prop, state)
            if state
            else ""
        )
        materials.append(
            {
                "id": prop_id,
                "type": "道具资产",
                "purpose": f"锁定关键道具 {prop.get('name', '道具')} 的造型、尺度和材质",
                "notes": "分镜直接引用该道具编号；默认状态与剧情状态沿用同一识别点",
                "prompt": _numbered_asset_prompt(
                    prop_id, _build_prop_asset_prompt(prop) + state_prompt
                ),
            }
        )
    return materials


def _numbered_asset_prompt(asset_id: str, prompt: str) -> str:
    return f"资产编号：{asset_id}。{prompt}"


def enrich_asset_references(data: dict[str, Any], visual_style: str) -> dict[str, Any]:
    """Complete sparse model assets into reusable character, scene, and prop references."""
    enriched = dict(data)
    characters = [dict(item) for item in data.get("characters", []) if isinstance(item, dict)]
    scenes = [dict(item) for item in data.get("scenes", []) if isinstance(item, dict)]
    props = [dict(item) for item in data.get("props", []) if isinstance(item, dict)]

    for character in characters:
        character["status"] = "confirmed"
        if not str(character.get("age") or "").strip() or _contains_placeholder(character.get("age")):
            character["age"] = "28岁青年"
        if not str(character.get("appearance") or "").strip() or _contains_placeholder(character.get("appearance")):
            character["appearance"] = _extract_appearance("")
        if not str(character.get("costume") or "").strip() or _contains_placeholder(character.get("costume")):
            character["costume"] = _extract_costume("")
        if _contains_placeholder(character.get("turnaround_prompt")) or _is_sparse_asset_prompt(
            str(character.get("turnaround_prompt") or ""),
            ("角色固定身份", "画面上方", "画面左侧", "画面底部", "画面右侧", "比例"),
        ):
            character["turnaround_prompt"] = _build_character_turnaround_prompt(
                str(character.get("name") or "角色"),
                str(character["appearance"]),
                str(character["costume"]),
                visual_style,
                str(character.get("role") or "主要角色"),
                str(character.get("age") or "28岁青年"),
            )
        if _contains_placeholder(character.get("expression_prompt")) or _is_sparse_asset_prompt(
            str(character.get("expression_prompt") or ""), ("眉", "眼", "嘴")
        ):
            character["expression_prompt"] = _build_character_expression_prompt(
                str(character.get("name") or "角色"),
                str(character["appearance"]),
                str(character["costume"]),
                visual_style,
                str(character.get("role") or "主要角色"),
                str(character.get("age") or "28岁青年"),
            )

    for scene in scenes:
        scene["status"] = "confirmed"
        time_value = str(scene.get("time") or "白天")
        scene_context = " ".join(
            str(scene.get(key) or "")
            for key in ("location", "name", "layout", "lighting", "atmosphere")
        )
        weather_value = _resolve_weather(scene.get("weather"), scene_context, time_value)
        scene["weather"] = weather_value
        if not str(scene.get("location") or "").strip() or _contains_placeholder(scene.get("location")):
            scene["location"] = str(scene.get("name") or "城市室内会客区")
        if not str(scene.get("layout") or "").strip() or _contains_placeholder(scene.get("layout")):
            scene["layout"] = "前景为入口框景，中景为人物活动区，背景为后墙与第二出入口，桌、椅、窗三处固定陈设坐标不变"
        if not str(scene.get("lighting") or "").strip() or _contains_placeholder(scene.get("lighting")):
            scene["lighting"] = "5600K 自然光从画面左侧窗户进入，右侧柔和补光，阴影向右后方过渡"
        if not scene.get("fixed_elements") or any(_contains_placeholder(item) for item in scene.get("fixed_elements", [])):
            scene["fixed_elements"] = ["主要入口", "中央活动区", "侧窗", "后墙"]
        environment_prompt = str(scene.get("environment_prompt") or "")
        if _contains_placeholder(environment_prompt) or _is_sparse_asset_prompt(
            environment_prompt, ("无人物", "正打", "反打", "侧面")
        ):
            scene["environment_prompt"] = _build_scene_environment_prompt(
                visual_style,
                str(scene.get("location") or scene.get("name") or "城市室内会客区"),
                time_value,
                weather_value,
                str(scene["layout"]),
                str(scene["lighting"]),
                [str(item) for item in scene.get("fixed_elements", [])],
            )

    for prop in props:
        if not str(prop.get("description") or "").strip() or _contains_placeholder(prop.get("description")):
            prop["description"] = _build_prop_description(
                str(prop.get("name") or "关键道具"), ""
            )

    enriched["characters"] = characters
    enriched["scenes"] = scenes
    enriched["props"] = props
    enriched["material_map"] = _build_material_map(characters, scenes, props, visual_style)
    return enriched


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
        asset_references = _build_shot_asset_references(
            scene, character_ids, prop_ids, props
        )
        camera_position = _camera_position(shot_size, sentence)
        lens = _lens_for_shot_size(shot_size)
        dialogue = _dialogue(sentence)
        narration = _narration(sentence)
        sound_design = _sound_design(sentence)
        first_frame_prompt = _build_first_frame_prompt(
            scene,
            character_names,
            asset_references,
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
            asset_references,
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
                    asset_references,
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
                    asset_references,
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
                "status": "confirmed",
            }
        )
        current_time = round(current_time + duration, 1)
    if target_runtime is not None and shots:
        _scale_shot_runtime(shots, target_runtime)
    return shots


def _fallback_character(title: str, sentences: list[str], visual_style: str) -> dict[str, Any]:
    context = sentences[0] if sentences else title
    name = "主角"
    appearance = _extract_appearance(context)
    costume = _extract_costume(context)
    age = _extract_age(context)
    return {
        "id": "C001",
        "name": name,
        "role": "主要角色",
        "age": age,
        "personality": _infer_personality(context),
        "appearance": appearance,
        "costume": costume,
        "props": [],
        "expression_profile": ["观察", "紧张", "释然"],
        "voice_profile": "自然中文对白，音色清晰，语速适中",
        "continuity_anchors": ["主角的脸型、发型、服装和身材比例在所有镜头中保持一致"],
        "status": "confirmed",
        "turnaround_prompt": _build_character_turnaround_prompt(name, appearance, costume, visual_style),
        "expression_prompt": _build_character_expression_prompt(
            name, appearance, costume, visual_style, "主要角色", age
        ),
        "negative_prompt": "角色身份变化，服装变化，多余人物，文字，水印，低清晰度",
    }


def _fallback_scene(script: str, time_value: str, weather: str, style: str) -> dict[str, Any]:
    location = "城市室内会客区"
    if any(word in script for word in ("古代", "皇", "王爷", "寝宫", "宫殿")):
        location = "古代府邸内厅"
    elif any(word in script for word in ("乡村", "村", "农", "田")):
        location = "乡村砖木结构堂屋"
    elif any(word in script for word in ("校园", "学生", "老师", "教室")):
        location = "城市中学标准教室"
    layout = "前景为主要入口与门框，中景为中央人物活动区和木桌，背景为侧窗、后墙与第二出入口，三处固定陈设坐标保持不变"
    lighting = "5600K 自然光从画面左侧窗户进入，右侧柔和补光，阴影向右后方过渡"
    fixed_elements = ["主要入口", "中央木桌", "侧窗", "后墙"]
    return {
        "id": "S001",
        "name": location,
        "location": location,
        "time": time_value,
        "weather": weather,
        "layout": layout,
        "lighting": lighting,
        "palette": style,
        "fixed_elements": fixed_elements,
        "atmosphere": "克制、清晰，保留人物表演空间",
        "status": "confirmed",
        "environment_prompt": _build_scene_environment_prompt(style, location, time_value, weather, layout, lighting, fixed_elements),
        "negative_prompt": "空间结构跳变，错误时间，错误天气，文字，水印，低清晰度",
    }


def _fallback_shot(
    sentences: list[str],
    characters: list[dict[str, Any]],
    scenes: list[dict[str, Any]],
    props: list[dict[str, Any]],
    style: str,
) -> list[dict[str, Any]]:
    sentence = sentences[0] if sentences else "主角站在场景中央观察周围环境"
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


def _match_keyword(context: str, keywords: tuple[str, ...]) -> str:
    return next((keyword for keyword in keywords if keyword in context), "")


def _extract_age(context: str) -> str:
    return _match_keyword(
        context,
        ("孩童", "少年", "少女", "青年", "中年", "老年", "男孩", "女孩", "男人", "女人", "老人"),
    ) or "28岁青年"


def _extract_appearance(context: str) -> str:
    face = _match_keyword(context, ("圆脸", "方脸", "瓜子脸", "鹅蛋脸", "长脸", "娃娃脸")) or "椭圆脸"
    hair_style = _match_keyword(context, ("短发", "长发", "卷发", "直发", "马尾", "丸子头", "辫子", "刘海")) or "利落短发"
    hair_color = _match_keyword(
        context,
        ("黑发", "黑色", "白发", "白色", "棕发", "棕色", "金发", "金色", "银发", "银色", "红发", "红色"),
    ) or "自然黑发"
    feature = _match_keyword(context, ("雀斑", "胡茬", "眼镜", "疤痕", "痣", "酒窝", "泪痣", "浓眉", "薄唇", "高鼻梁", "单眼皮", "双眼皮")) or "眉峰清晰、鼻梁挺直"
    skin = _match_keyword(context, ("白皙", "苍白", "黝黑", "细腻", "粗糙", "干净", "憔悴", "健康")) or "自然健康肤色，保留真实毛孔"
    hair = " ".join((hair_color, hair_style))
    return (
        f"脸型：{face}；"
        f"发型发色：{hair}；"
        f"体型/年龄感：{_extract_age(context)}；"
        f"肤质/妆容：{skin}；"
        f"显著外观：{feature}"
    )


def _extract_costume(context: str) -> str:
    clothing = _match_keyword(
        context,
        (
            "风衣",
            "衬衫",
            "外套",
            "大衣",
            "西装",
            "卫衣",
            "毛衣",
            "T恤",
            "校服",
            "睡衣",
            "长裙",
            "短裙",
            "旗袍",
            "长袍",
            "连衣裙",
            "夹克",
            "背心",
            "牛仔裤",
            "长裤",
            "半身裙",
            "羽绒服",
        ),
    ) or ("长袍" if any(word in context for word in ("皇", "王爷", "古代", "殿")) else "衬衫")
    color = _match_keyword(
        context,
        ("黑色", "白色", "灰色", "红色", "蓝色", "绿色", "棕色", "米色", "紫色", "黄色", "深色", "浅色"),
    ) or "深灰色"
    material = _match_keyword(
        context,
        ("棉", "麻", "丝", "皮革", "羊毛", "牛仔", "针织", "呢料", "缎", "雪纺", "蕾丝"),
    ) or "棉麻混纺"
    layer = _match_keyword(context, ("内搭", "外套", "叠穿", "层叠", "披风", "开衫", "背心")) or "单层利落剪裁"
    accessory = _match_keyword(context, ("围巾", "帽子", "手套", "耳钉", "耳环", "项链", "戒指", "胸针", "腰带", "背包", "手表", "雨伞")) or "无固定配饰"
    return f"服装品类：{clothing}；主色：{color}；材质/层次：{material}，{layer}；配饰：{accessory}"


def _build_character_turnaround_prompt(
    name: str,
    appearance: str,
    costume: str,
    visual_style: str,
    role: str = "主要角色",
    age: str = "28岁青年",
) -> str:
    return (
        f"角色固定身份：{name}，{role}，{age}；{appearance}；{costume}；"
        "身高、体型、头身比、脸型、肤色、眼型、眉形、唇形、发际线、发型、鞋子、固定配饰和身份标记均不可改变；"
        "正面、侧面、背面、面部特写、比例照与局部细节模块必须是同一角色。"
        "人物形象设定板，16:9 横构图，纯白无影背景，制作参考图。"
        "画面上方为主视觉区，占画布约 65%，从左至右排列同一角色的全身正面、严格侧面、全身背面；"
        "三视图从头到脚完整入镜，空手自然站立，姿态中性，比例、服装结构、发丝、鞋子与光线完全一致。"
        "画面左侧为补充信息区：上方为面部特写，清晰展示脸型、眼睛、眉形、唇形、肤质、发际线、皮肤纹理、眼神高光、睫毛、眉毛与面部识别点；"
        "下方为无文字配色板，分别给出毛发、肤色、内搭、外套、下装、鞋子和金属/宝石的色块，并保留空白标注区。"
        "画面底部为局部细节区，以不互相遮挡的小模块分别展示固定配饰、身份标记、服装纹样或五金、袖口/鞋面及必要磨损，明确结构、连接方式和材质。"
        "画面右侧为全身照比例区：同一角色完整全身照旁放置低调、无文字、无刻度乱码的人体比例轮廓，用于对比身高、头身比、肩宽和腿长。"
        f"{_character_style_lock(visual_style)}；只使用这一种风格分支；统一柔和棚拍光，所有模块的阴影、色彩和细节密度一致。"
        "无其他人物、无场景背景、无多余道具、无可读文字、无水印、无品牌标识、无拼接错位、无重复肢体；"
        "不要只生成单张正面肖像，不要裁切脚部或隐藏鞋子，不要把严格侧面变成三分之四侧脸，不要改变服装结构、发型或身材比例。"
    )


def _build_character_expression_prompt(
    name: str,
    appearance: str,
    costume: str,
    visual_style: str,
    role: str = "主要角色",
    age: str = "28岁青年",
) -> str:
    return (
        f"角色固定身份：{name}，{role}，{age}；{appearance}；{costume}；"
        f"表情设定表，{_character_style_lock(visual_style)}；同一身份锚点下保持脸型、发际线、身材比例、服装、鞋子与配饰一致；"
        "拆分观察、紧张、犹豫、爆发、释然等表情，写清眉眼、眼神高光、嘴角、呼吸、皮肤细节和微瑕疵变化，"
        "不要更换发型、服装和脸型，无文字无水印。"
    )


def _build_scene_environment_prompt(
    visual_style: str,
    location: str,
    time_value: str,
    weather_value: str,
    layout: str,
    lighting: str,
    fixed_elements: list[str],
) -> str:
    fixed_text = "、".join(fixed_elements) if fixed_elements else "主要入口、中央活动区、侧窗、后墙"
    return (
        f"{visual_style}场景设定图，{location}，{time_value}，{weather_value}，无人物；"
        f"前中后景分层清楚，{layout}；固定陈设：{fixed_text}；"
        f"光源与氛围：{lighting}；正打、反打、侧面全景都成立，保留门窗、家具和关键道具的相对位置，"
        "空间材质、接触阴影和纵深清晰，无文字、无人影、无水印。"
    )


def _character_style_lock(visual_style: str) -> str:
    if any(keyword in visual_style for keyword in ("国漫", "动漫", "二次元", "动画")):
        return f"统一视觉风格：{visual_style}，半写实动画角色设定，清晰自然的脸部结构、发丝与服装材质，不使用真人写实或塑料玩具质感"
    if "3D" in visual_style.upper():
        return f"统一视觉风格：{visual_style}，高品质 3D 写实角色设定，真实比例与 PBR 材质，不使用平涂赛璐珞"
    return f"统一视觉风格：{visual_style}，真人写实电影质感，真实皮肤、发丝与服料纤维，无美颜滤镜"


def _build_character_full_body_prompt(character: dict[str, Any], visual_style: str) -> str:
    return (
        f"{character.get('id', 'C001')}，角色固定身份：{character.get('name', '角色')}，{character.get('role') or '主要角色'}，{character.get('age') or '28岁青年'}；"
        f"{character.get('appearance') or _extract_appearance('')}；{character.get('costume') or _extract_costume('')}；"
        "全身站立，正面视角，从头到脚完整入镜，双手自然垂落，身体直立，中性表情，"
        "纯白无影背景，柔和均匀棚拍光，50mm 镜头，f/4，全画幅相机，"
        f"{_character_style_lock(visual_style)}；真实面部结构和服装材质，无其他人物、无手持物、无文字、无水印。"
    )


def _build_character_portrait_prompt(character: dict[str, Any], visual_style: str) -> str:
    return (
        f"{character.get('id', 'C001')}，角色固定身份：{character.get('name', '角色')}，{character.get('role') or '主要角色'}，{character.get('age') or '28岁青年'}；同一角色肩部以上肖像设定图，"
        f"{character.get('appearance') or _extract_appearance('')}；{character.get('costume') or _extract_costume('')}；"
        "正面微偏三分之四视角，中性克制表情，纯白无影背景，柔和侧光加轻微轮廓光，"
        "皮肤真实细腻，毛孔、细小汗毛、自然不对称和微瑕疵可见，虹膜纤维清晰，眼神有真实反光，"
        "睫毛根根分明，眉毛略带杂毛，唇部纹理细致，真实发丝和胡茬细节，"
        f"85mm 微距镜头，f/1.2，全画幅相机，{_character_style_lock(visual_style)}，无文字、无水印。"
    )


def _build_scene_view_prompt(scene: dict[str, Any], view_name: str, direction: str) -> str:
    fixed_elements = scene.get("fixed_elements", [])
    fixed_text = "、".join(str(item) for item in fixed_elements) or "主要入口、中央活动区、侧窗、后墙"
    return (
        f"{scene.get('id', 'S001')}，{scene.get('name', '场景')}，{view_name}空镜，"
        f"{scene.get('location') or '城市室内会客区'}，{scene.get('time') or '白天'}，{_scene_weather(scene)}，"
        f"机位：{direction}；{scene.get('layout') or '前景入口、中景活动区、背景侧窗与后墙'}；"
        f"固定元素：{fixed_text}；光线：{scene.get('lighting') or '左侧窗户5600K自然光，右侧柔和补光'}；"
        "空镜，无人物、无人影、无可读文字；门窗、家具、关键道具的相对位置、材质、尺寸、时间和光线方向完全一致；"
        "明确前景、中景、背景与出入口的纵深关系，真实材料、自然磨损、接触阴影和空间尺度清晰，广角全景，无水印。"
    )


def _build_prop_asset_prompt(prop: dict[str, Any], state: str = "默认") -> str:
    return (
        f"{prop.get('id', 'P001')}，{prop.get('name', '道具')}，剧情道具设定图，用于{prop.get('description') or '承载镜头信息并推动角色动作'}；"
        f"当前为{state}状态，单独展示，三分之四俯视角度，纯白无影背景，柔和产品棚拍光，"
        "真实接触阴影，材质、边缘、工艺、使用痕迹和尺度参照清晰；"
        "同时给出不遮挡的局部细节，突出不可替代的识别点、连接结构和当前状态变化；"
        "无人、无手、无真实环境背景、无可读文字、无品牌标识、无水印、无漂浮物。"
    )


def _prop_plot_state(description: str) -> str:
    states = (
        ("半开", ("半开", "打开", "拆开")),
        ("破损", ("破损", "破", "裂", "撕")),
        ("沾污", ("血", "污", "沾水", "潮湿")),
    )
    return next((state for state, keywords in states if any(keyword in description for keyword in keywords)), "")


def _is_sparse_asset_prompt(prompt: str, required_terms: tuple[str, ...]) -> bool:
    return len(prompt.strip()) < 120 or any(term not in prompt for term in required_terms)




def _build_prop_description(prop_name: str, evidence: str) -> str:
    default_materials = {
        "信封": "微黄牛皮纸",
        "照片": "半光面相纸",
        "手机": "黑色玻璃与金属边框",
        "钥匙": "旧黄铜",
        "杯子": "透明玻璃",
        "书": "米白纸张与深色布面封皮",
        "雨伞": "黑色防水布与磨砂金属伞骨",
    }
    material = _match_keyword(evidence, ("金属", "木", "纸", "布", "玻璃", "塑料", "皮革", "陶瓷", "石", "玉")) or default_materials.get(prop_name, "深灰色哑光金属与耐磨复合材料")
    color = _match_keyword(evidence, ("黑", "白", "红", "金", "银", "透明", "灰", "棕", "蓝", "旧")) or "深灰色"
    wear = "边缘有轻微划痕与自然使用痕迹"
    return (
        f"外形：{prop_name}；"
        f"材质：{material}；"
        f"颜色/磨损：{color}/{wear}；"
        f"剧情用途：{_prop_usage(prop_name, evidence)}；"
        f"剧情依据：{evidence or '作为当前镜头的关键可见物件'}"
    )


def _contains_placeholder(value: Any) -> bool:
    text = str(value or "")
    return any(token in text for token in ("待确认", "未知", "未指定", "未命名"))


def _remove_placeholders(value: str, replacement: str = "已按制作要求定稿") -> str:
    result = value
    for token in ("天气待确认", "地点待确认", "时间待确认", "光线待确认", "固定陈设待确认", "待确认", "未知", "未指定"):
        result = result.replace(token, replacement)
    return result


def _resolve_weather(value: Any, context: str, time_value: str) -> str:
    weather = str(value or "").strip()
    if weather and weather not in {"待确认", "天气待确认", "未确认", "未知"}:
        return weather
    return _reasonable_weather(context, time_value)


def _reasonable_weather(context: str, time_value: str) -> str:
    """Infer a stable, shootable weather condition when the script omits one."""
    source = f"{context} {time_value}"
    if any(word in source for word in ("暴雨", "大雨", "雷雨")):
        return "暴雨天气"
    if any(word in source for word in ("小雨", "下雨", "雨夜", "雨")):
        return "降雨天气"
    if any(word in source for word in ("暴雪", "大雪", "风雪", "下雪", "雪")):
        return "降雪天气"
    if any(word in source for word in ("大雾", "薄雾", "雾")):
        return "薄雾天气"
    if any(word in source for word in ("阴天", "阴沉", "乌云", "阴")):
        return "阴天，云层较厚"
    if any(word in source for word in ("狂风", "大风", "寒风", "晚风", "风")):
        return "有风、无明显降水"
    if any(word in time_value for word in ("夜", "凌晨", "午夜")):
        return "晴朗无雨的夜晚"
    return "晴朗、无明显降水"


def _scene_weather(scene: dict[str, Any]) -> str:
    time_value = str(scene.get("time") or "")
    context = " ".join(
        str(scene.get(key) or "")
        for key in ("location", "name", "layout", "lighting", "atmosphere")
    )
    return _resolve_weather(scene.get("weather"), context, time_value)


def _first_match(script: str, choices: tuple[str, ...]) -> str:
    return next((choice for choice in choices if choice in script), "")


def _unique_matches(script: str, choices: tuple[str, ...]) -> list[str]:
    return [choice for choice in choices if choice in script]


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
    return "克制、敏锐，行动前会先观察环境"


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
    return "克制、清晰，逐步积累情绪张力"


def _color_script(script: str, weather: str) -> str:
    if any(word in script for word in ("夜", "雨", "阴")):
        return "低饱和冷色为主，在剧情转折处加入局部暖色光源"
    if any(word in script for word in ("阳光", "晴", "清晨")):
        return "明亮自然色，关键情绪用柔和暖色强化"
    return f"以{weather}对应的中性环境色为基底，主体使用暖灰肤色，背景降低饱和度，转折处提高明暗对比"


def _logline(sentences: list[str], title: str) -> str:
    if not sentences:
        return f"{title}：主角在既定场景中面对冲突并作出选择。"
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
        return "冷色夜景主调，主光来自窗外或门口，室内残火做局部补光，阴影边缘保留柔和过渡"
    if any(word in text for word in ("黄昏", "傍晚")):
        return "斜向暖色夕光与冷色环境光并置，边缘轮廓有轻微补光"
    return "主光源明确、阴影柔和，保证竖屏下人物轮廓清晰，空间材质可读"


def _scene_fixed_elements(scene_name: str, text: str) -> list[str]:
    elements = [scene_name]
    for word in ("床榻", "木门", "窗棂", "桌案", "帛书", "炭火", "风铃"):
        if word in text:
            elements.append(word)
    return elements


def _build_shot_asset_references(
    scene: dict[str, Any],
    character_ids: list[str],
    prop_ids: list[str],
    props: list[dict[str, Any]],
) -> list[str]:
    references = [*character_ids, str(scene.get("id") or "S001"), *prop_ids]
    return list(dict.fromkeys(reference for reference in references if reference))


def _build_state_contract(
    scene: dict[str, Any],
    character_names: str,
    asset_references: list[str],
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
        "reference_assets": asset_references,
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
    asset_references: list[str],
    action: str,
    shot_size: str,
    camera_position: str,
    lens: str,
    emotion: str,
    prop_names: list[str],
    visual_style: str,
) -> str:
    props = "、".join(prop_names) if prop_names else "无显性道具"
    references = "、".join(asset_references)
    return (
        f"引用资产编号：{references}。9:16竖屏漫剧首帧，{scene.get('location') or scene.get('name') or '城市室内会客区'}，"
        f"{scene.get('time') or '白天'}，{_scene_weather(scene)}，{shot_size}，"
        f"{camera_position}，{lens}，{character_names} 入画前的稳定姿态，动作主题“{action}”尚未爆发，"
        f"情绪为{emotion}，关键道具：{props}，固定元素：{'、'.join(scene.get('fixed_elements', [])) or '主要入口、中央活动区、侧窗、后墙'}，"
        f"主光：{scene.get('lighting') or '左侧窗户5600K自然光，右侧柔和补光'}，{visual_style}，线条清晰，人物脸部不崩，画面中无字幕无文字气泡。"
    )


def _build_last_frame_prompt(
    scene: dict[str, Any],
    character_names: str,
    asset_references: list[str],
    action: str,
    shot_size: str,
    camera_position: str,
    emotion: str,
    prop_names: list[str],
    visual_style: str,
) -> str:
    props = "、".join(prop_names) if prop_names else "无显性道具"
    references = "、".join(asset_references)
    return (
        f"引用资产编号：{references}。9:16竖屏漫剧尾帧，{scene.get('name') or '主场景'} 保持空间连续，{shot_size}，"
        f"{camera_position}，{character_names} 完成“{action}”后的可剪停顿姿态，"
        f"表情停在{emotion}与下一镜可衔接的过渡点，关键道具：{props} 保持位置稳定，"
        f"{visual_style}，无字幕、无水印、无多余人物。"
    )


def _build_video_prompt(
    scene: dict[str, Any],
    character_names: str,
    asset_references: list[str],
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
    references = "、".join(asset_references)
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
        f"Seedance 2.0 视频提示词，引用资产编号：{references}，9:16竖屏，时长 {duration:.1f}s，视觉风格：{visual_style}，"
        f"场景：{scene.get('location') or scene.get('name') or '城市室内会客区'}，"
        f"{scene.get('time') or '白天'}，{_scene_weather(scene)}，镜头类型：{shot_size}，"
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
