"""AI 漫剧制作智能体的分阶段编排。"""

from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path
from typing import Any

from .llm import LLMClient, OpenAICompatibleClient
from .reasoner import RuleBasedClient, build_rule_based_analysis
from .models import (
    ActionBeat,
    Character,
    ContinuityIssue,
    DramaProject,
    GenerationOptions,
    JoinContract,
    MaterialReference,
    Prop,
    ProductionLocks,
    RepairPrompt,
    Scene,
    Shot,
    ShotStateContract,
    StoryBible,
)
from .prompts import (
    build_asset_extraction_prompt,
)

ASSET_EXTRACTION_SYSTEM_PROMPT = (
    "你是中文短剧故事资产提取器。只返回合法 JSON，不要解释，不要输出 Markdown。"
)


class DramaAgent:
    """负责将剧本转换为 AI 漫剧制作包。"""

    def __init__(self, client: LLMClient | None = None) -> None:
        self.client = client

    def run(self, script: str, options: GenerationOptions) -> DramaProject:
        client = self.client or OpenAICompatibleClient.from_environment()
        if isinstance(client, RuleBasedClient):
            raw = build_rule_based_analysis(script, options.title, options.visual_style)
            project = self._project_from_dict(script, options, raw)
        else:
            project = self._run_asset_pipeline(script, options, client)
        project.metadata.update(
            {
                "generation_mode": (
                    "offline-rule-based"
                    if isinstance(client, RuleBasedClient)
                    else project.metadata.get("generation_mode", "llm")
                ),
                "source_script_length": len(script),
            }
        )
        project.continuity_issues.extend(self._validate(project))
        return project

    def _run_asset_pipeline(
        self,
        script: str,
        options: GenerationOptions,
        client: LLMClient,
    ) -> DramaProject:
        asset_data = client.complete_json(
            ASSET_EXTRACTION_SYSTEM_PROMPT,
            build_asset_extraction_prompt(
                script,
                options.title,
                options.visual_style,
                options.aspect_ratio,
                options.fps,
            ),
        )

        local_data = build_rule_based_analysis(script, options.title, options.visual_style)
        merged = _merge_asset_pipeline_payload(local_data, asset_data)
        return self._project_from_dict(script, options, merged)

    def _project_from_dict(
        self,
        script: str,
        options: GenerationOptions,
        data: dict[str, Any],
    ) -> DramaProject:
        story_data = data.get("story_bible", {})
        project = DramaProject(
            title=options.title,
            source_script=script,
            options=options,
            story_bible=StoryBible(
                logline=str(story_data.get("logline", "")),
                genre=str(story_data.get("genre", "")),
                world_rules=_strings(story_data.get("world_rules")),
                visual_direction=str(story_data.get("visual_direction", "")),
                color_script=str(story_data.get("color_script", "")),
                tone=str(story_data.get("tone", "")),
                timeline=str(story_data.get("timeline", "")),
                unresolved_questions=_strings(story_data.get("unresolved_questions")),
            ),
            characters=[self._character(item) for item in _objects(data.get("characters"))],
            scenes=[self._scene(item) for item in _objects(data.get("scenes"))],
            props=[self._prop(item) for item in _objects(data.get("props"))],
            shots=[self._shot(item) for item in _objects(data.get("shots"))],
            production_locks=self._production_locks(data.get("production_locks")),
            material_map=[self._material(item) for item in _objects(data.get("material_map"))],
            join_contracts=[self._join_contract(item) for item in _objects(data.get("join_contracts"))],
            repair_prompts=[self._repair_prompt(item) for item in _objects(data.get("repair_prompts"))],
            continuity_issues=[
                self._issue(item) for item in _objects(data.get("continuity_issues"))
            ],
            metadata=data.get("metadata", {}) if isinstance(data.get("metadata"), dict) else {},
        )
        return project

    @staticmethod
    def _character(item: dict[str, Any]) -> Character:
        return Character(
            id=str(item.get("id", "")),
            name=str(item.get("name", "")),
            role=str(item.get("role", "")),
            age=str(item.get("age", "")),
            personality=str(item.get("personality", "")),
            appearance=str(item.get("appearance", "")),
            costume=str(item.get("costume", "")),
            props=_strings(item.get("props")),
            expression_profile=_strings(item.get("expression_profile")),
            voice_profile=str(item.get("voice_profile", "")),
            continuity_anchors=_strings(item.get("continuity_anchors")),
            status=_status(item.get("status")),
            turnaround_prompt=str(item.get("turnaround_prompt", "")),
            expression_prompt=str(item.get("expression_prompt", "")),
            negative_prompt=str(item.get("negative_prompt", "")),
        )

    @staticmethod
    def _scene(item: dict[str, Any]) -> Scene:
        return Scene(
            id=str(item.get("id", "")),
            name=str(item.get("name", "")),
            location=str(item.get("location", "")),
            time=str(item.get("time", "")),
            weather=str(item.get("weather", "")),
            layout=str(item.get("layout", "")),
            lighting=str(item.get("lighting", "")),
            palette=str(item.get("palette", "")),
            fixed_elements=_strings(item.get("fixed_elements")),
            atmosphere=str(item.get("atmosphere", "")),
            status=_status(item.get("status")),
            environment_prompt=str(item.get("environment_prompt", "")),
            negative_prompt=str(item.get("negative_prompt", "")),
        )

    @staticmethod
    def _prop(item: dict[str, Any]) -> Prop:
        return Prop(
            id=str(item.get("id", "")),
            name=str(item.get("name", "")),
            description=str(item.get("description", "")),
            owner=str(item.get("owner", "")),
            continuity_notes=str(item.get("continuity_notes", "")),
        )

    @staticmethod
    def _shot(item: dict[str, Any]) -> Shot:
        beats = [
            ActionBeat(
                start_second=_number(beat.get("start_second"), 0),
                end_second=_number(beat.get("end_second"), 0),
                action=str(beat.get("action", "")),
                emotion=str(beat.get("emotion", "")),
                continuity_notes=str(beat.get("continuity_notes", "")),
            )
            for beat in _objects(item.get("action_beats"))
        ]
        confidence = str(item.get("confidence", "medium"))
        if confidence not in {"high", "medium", "low"}:
            confidence = "medium"
        state_data = item.get("state_contract")
        state = state_data if isinstance(state_data, dict) else {}
        return Shot(
            id=str(item.get("id", "")),
            scene_id=str(item.get("scene_id", "")),
            character_ids=_strings(item.get("character_ids")),
            prop_ids=_strings(item.get("prop_ids")),
            start_second=_number(item.get("start_second"), 0),
            duration_seconds=_number(item.get("duration_seconds"), 4),
            shot_size=str(item.get("shot_size", "")),
            camera_position=str(item.get("camera_position", "")),
            lens=str(item.get("lens", "")),
            camera_motion=str(item.get("camera_motion", "")),
            visual_action=str(item.get("visual_action", "")),
            dialogue=str(item.get("dialogue", "")),
            narration=str(item.get("narration", "")),
            sound_design=str(item.get("sound_design", "")),
            action_beats=beats,
            prompt_id=str(item.get("prompt_id", "")),
            state_contract=ShotStateContract(
                reference_roles=_strings(state.get("reference_roles")),
                first_visible_frame=str(state.get("first_visible_frame", "")),
                screen_layout=str(state.get("screen_layout", "")),
                subject_state=str(state.get("subject_state", "")),
                performance_cause=str(state.get("performance_cause", "")),
                prop_state=str(state.get("prop_state", "")),
                camera_coverage_mode=str(state.get("camera_coverage_mode", "")),
                camera_path=str(state.get("camera_path", "")),
                action_transition=str(state.get("action_transition", "")),
                final_visible_frame=str(state.get("final_visible_frame", "")),
                hard_limits=_strings(state.get("hard_limits")),
            ),
            first_frame_prompt=str(item.get("first_frame_prompt", "")),
            video_prompt=str(item.get("video_prompt", "")),
            last_frame_prompt=str(item.get("last_frame_prompt", "")),
            negative_prompt=str(item.get("negative_prompt", "")),
            continuity_requirements=_strings(item.get("continuity_requirements")),
            expected_failures=_strings(item.get("expected_failures")),
            repair_strategy=str(item.get("repair_strategy", "")),
            confidence=confidence,  # type: ignore[arg-type]
            status=_status(item.get("status")),
        )

    @staticmethod
    def _production_locks(value: object) -> ProductionLocks:
        item = value if isinstance(value, dict) else {}
        return ProductionLocks(
            character_lock=str(item.get("character_lock", "")),
            scene_lock=str(item.get("scene_lock", "")),
            style_core=str(item.get("style_core", "")),
            visual_tone=str(item.get("visual_tone", "")),
            color_lighting=str(item.get("color_lighting", "")),
            camera_rules=str(item.get("camera_rules", "")),
            action_intensity=str(item.get("action_intensity", "")),
            continuity_lock=str(item.get("continuity_lock", "")),
            sound_mood=str(item.get("sound_mood", "")),
            forbidden_drift=str(item.get("forbidden_drift", "")),
        )

    @staticmethod
    def _material(item: dict[str, Any]) -> MaterialReference:
        return MaterialReference(
            id=str(item.get("id", "")),
            type=str(item.get("type", "")),
            purpose=str(item.get("purpose", "")),
            notes=str(item.get("notes", "")),
            prompt=str(item.get("prompt", "")),
        )

    @staticmethod
    def _join_contract(item: dict[str, Any]) -> JoinContract:
        return JoinContract(
            from_shot=str(item.get("from_shot", "")),
            to_shot=str(item.get("to_shot", "")),
            previous_end_state=str(item.get("previous_end_state", "")),
            next_start_state=str(item.get("next_start_state", "")),
            state_delta=str(item.get("state_delta", "")),
            risk_level=str(item.get("risk_level", "")),
            hard_cut_allowed=bool(item.get("hard_cut_allowed", False)),
            bridge_requirement=str(item.get("bridge_requirement", "")),
            bridge_prompt_id=str(item.get("bridge_prompt_id", "")),
            safety_inserts=_strings(item.get("safety_inserts")),
            sound_bridge=str(item.get("sound_bridge", "")),
            fallback_edit=str(item.get("fallback_edit", "")),
        )

    @staticmethod
    def _repair_prompt(item: dict[str, Any]) -> RepairPrompt:
        return RepairPrompt(
            id=str(item.get("id", "")),
            type=str(item.get("type", "")),
            purpose=str(item.get("purpose", "")),
            prompt=str(item.get("prompt", "")),
        )

    @staticmethod
    def _issue(item: dict[str, Any]) -> ContinuityIssue:
        severity = str(item.get("severity", "warning"))
        if severity not in {"error", "warning", "info"}:
            severity = "warning"
        return ContinuityIssue(
            severity=severity,  # type: ignore[arg-type]
            scope=str(item.get("scope", "")),
            message=str(item.get("message", "")),
            suggested_action=str(item.get("suggested_action", "")),
        )

    @staticmethod
    def _validate(project: DramaProject) -> list[ContinuityIssue]:
        issues: list[ContinuityIssue] = []
        character_ids = {item.id for item in project.characters}
        scene_ids = {item.id for item in project.scenes}
        prop_ids = {item.id for item in project.props}
        shot_ids = set()
        expected_start = 0.0

        for shot in project.shots:
            if shot.id in shot_ids:
                issues.append(ContinuityIssue("error", shot.id, "镜头 ID 重复。", "重新分配唯一镜头 ID。"))
            shot_ids.add(shot.id)
            if shot.scene_id not in scene_ids:
                issues.append(ContinuityIssue("error", shot.id, "引用了不存在的场景 ID。", "补充场景或修正场景引用。"))
            missing_characters = set(shot.character_ids) - character_ids
            if missing_characters:
                issues.append(ContinuityIssue("error", shot.id, f"引用了不存在的角色：{sorted(missing_characters)}。", "补充角色资产。"))
            missing_props = set(shot.prop_ids) - prop_ids
            if missing_props:
                issues.append(ContinuityIssue("error", shot.id, f"引用了不存在的道具：{sorted(missing_props)}。", "补充道具资产。"))
            if abs(shot.start_second - expected_start) > 0.01:
                issues.append(
                    ContinuityIssue(
                        "warning",
                        shot.id,
                        f"镜头时间轴存在空档或重叠，期望从 {expected_start:.2f}s 开始，实际为 {shot.start_second:.2f}s。",
                        "重新计算镜头起止时间。",
                    )
                )
            if shot.duration_seconds <= 0:
                issues.append(ContinuityIssue("error", shot.id, "镜头时长必须大于 0 秒。", "调整 duration_seconds。"))
            expected_start = shot.start_second + shot.duration_seconds
            if not shot.video_prompt:
                issues.append(ContinuityIssue("error", shot.id, "缺少视频主提示词。", "补充可直接生成视频的完整提示词。"))
            if not shot.first_frame_prompt or not shot.last_frame_prompt:
                issues.append(ContinuityIssue("warning", shot.id, "缺少首帧或尾帧提示词。", "补充关键帧提示词以增强连续性。"))

        return issues


def write_outputs(project: DramaProject, output_dir: Path) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "project.json").write_text(
        json.dumps(project.to_dict(), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    (output_dir / "production_package.md").write_text(
        render_production_package(project),
        encoding="utf-8",
    )
    (output_dir / "story_bible.md").write_text(render_story_bible(project), encoding="utf-8")
    (output_dir / "characters.md").write_text(render_characters(project), encoding="utf-8")
    (output_dir / "scenes.md").write_text(render_scenes(project), encoding="utf-8")
    (output_dir / "production_system.md").write_text(
        render_production_system(project),
        encoding="utf-8",
    )
    (output_dir / "storyboard.md").write_text(render_storyboard(project), encoding="utf-8")
    (output_dir / "continuity_report.md").write_text(
        render_continuity_report(project),
        encoding="utf-8",
    )


def render_production_package(project: DramaProject) -> str:
    return "\n\n".join(
        [
            f"# {project.title}：AI 漫剧制作包",
            render_story_bible(project),
            render_characters(project),
            render_scenes(project),
            render_production_system(project),
            render_storyboard(project),
            render_continuity_report(project),
        ]
    )


def render_story_bible(project: DramaProject) -> str:
    story = project.story_bible
    unresolved_questions = (
        [f"  - {item}" for item in story.unresolved_questions]
        if story.unresolved_questions
        else ["  - 无"]
    )
    return "\n".join(
        [
            "## 故事圣经",
            f"- 故事梗概：{story.logline}",
            f"- 类型：{story.genre}",
            f"- 视觉方向：{story.visual_direction}",
            f"- 色彩脚本：{story.color_script}",
            f"- 整体基调：{story.tone}",
            f"- 时间线：{story.timeline}",
            "- 世界规则：",
            *[f"  - {item}" for item in story.world_rules],
            "- 待确认问题：",
            *unresolved_questions,
        ]
    )


def render_characters(project: DramaProject) -> str:
    lines = ["## 角色资产"]
    for character in project.characters:
        lines.extend(
            [
                f"### {character.id}｜{character.name}",
                f"- 身份：{character.role}",
                f"- 年龄：{character.age}",
                f"- 性格：{character.personality}",
                f"- 外观：{character.appearance}",
                f"- 服装：{character.costume}",
                f"- 一致性锚点：{'；'.join(character.continuity_anchors)}",
                f"- 三视图提示词：{character.turnaround_prompt}",
                f"- 表情设定提示词：{character.expression_prompt}",
                f"- 负面提示词：{character.negative_prompt}",
            ]
        )
    return "\n".join(lines)


def render_scenes(project: DramaProject) -> str:
    lines = ["## 场景资产"]
    for scene in project.scenes:
        lines.extend(
            [
                f"### {scene.id}｜{scene.name}",
                f"- 地点：{scene.location}",
                f"- 时间：{scene.time}",
                f"- 天气：{scene.weather}",
                f"- 空间布局：{scene.layout}",
                f"- 光线：{scene.lighting}",
                f"- 色彩：{scene.palette}",
                f"- 固定元素：{'；'.join(scene.fixed_elements)}",
                f"- 场景提示词：{scene.environment_prompt}",
                f"- 负面提示词：{scene.negative_prompt}",
            ]
        )
    return "\n".join(lines)


def render_production_system(project: DramaProject) -> str:
    locks = project.production_locks
    lines = [
        "## 生产锁",
        f"- 角色锁：{locks.character_lock or '待确认'}",
        f"- 场景锁：{locks.scene_lock or '待确认'}",
        f"- 风格核心：{locks.style_core or '待确认'}",
        f"- 视觉基调：{locks.visual_tone or '待确认'}",
        f"- 色彩与光影：{locks.color_lighting or '待确认'}",
        f"- 镜头规则：{locks.camera_rules or '待确认'}",
        f"- 动作强度：{locks.action_intensity or '待确认'}",
        f"- 连续性锁：{locks.continuity_lock or '待确认'}",
        f"- 声音氛围：{locks.sound_mood or '待确认'}",
        f"- 禁止漂移：{locks.forbidden_drift or '待确认'}",
        "",
        "## 素材对应表",
    ]
    if project.material_map:
        for item in project.material_map:
            lines.extend(
                [
                    f"### {item.id}｜{item.type}｜{item.purpose}",
                    f"- 备注：{item.notes or '无'}",
                    f"- 参考提示词：{item.prompt}",
                ]
            )
    else:
        lines.append("- 待生成")

    lines.extend(["", "## 镜头连接合同"])
    if project.join_contracts:
        for item in project.join_contracts:
            lines.extend(
                [
                    f"### {item.from_shot} → {item.to_shot}｜风险：{item.risk_level}",
                    f"- 前镜结束状态：{item.previous_end_state}",
                    f"- 后镜开始状态：{item.next_start_state}",
                    f"- 状态差异：{item.state_delta}",
                    f"- 允许硬切：{'是' if item.hard_cut_allowed else '否'}",
                    f"- 桥接需求：{item.bridge_requirement or '无'}",
                    f"- 桥接提示词 ID：{item.bridge_prompt_id or '无'}",
                    f"- 保险素材：{'；'.join(item.safety_inserts) or '无'}",
                    f"- 声音桥：{item.sound_bridge or '无'}",
                    f"- 失败备用剪法：{item.fallback_edit or '无'}",
                ]
            )
    else:
        lines.append("- 无")

    if project.repair_prompts:
        lines.extend(["", "## 桥接、插入与修复提示词"])
        for item in project.repair_prompts:
            lines.extend(
                [
                    f"### {item.id}｜{item.type}",
                    f"- 用途：{item.purpose}",
                    f"- 可复制提示词：{item.prompt}",
                ]
            )
    return "\n".join(lines)


def render_storyboard(project: DramaProject) -> str:
    lines = ["## 分镜与视频提示词"]
    for shot in project.shots:
        lines.extend(
            [
                f"### {shot.id}｜{shot.start_second:.2f}s - {shot.start_second + shot.duration_seconds:.2f}s｜{shot.duration_seconds:.2f}秒",
                f"- 场景：{shot.scene_id}",
                f"- 角色：{', '.join(shot.character_ids) or '无'}",
                f"- 道具：{', '.join(shot.prop_ids) or '无'}",
                f"- 景别：{shot.shot_size}",
                f"- 机位：{shot.camera_position}",
                f"- 镜头：{shot.lens}",
                f"- 运镜：{shot.camera_motion}",
                f"- 画面动作：{shot.visual_action}",
                f"- 台词：{shot.dialogue or '无'}",
                f"- 旁白：{shot.narration or '无'}",
                f"- 音效：{shot.sound_design or '无'}",
                f"- 主提示词 ID：{shot.prompt_id or f'VIDEO_MAIN_{shot.id}'}",
                "- Shot State Contract：",
                f"  - 参考角色：{'；'.join(shot.state_contract.reference_roles) or '待确认'}",
                f"  - 首帧状态：{shot.state_contract.first_visible_frame or shot.first_frame_prompt}",
                f"  - 屏幕方位：{shot.state_contract.screen_layout or '待确认'}",
                f"  - 主体状态：{shot.state_contract.subject_state or '待确认'}",
                f"  - 表演因果：{shot.state_contract.performance_cause or '待确认'}",
                f"  - 道具状态：{shot.state_contract.prop_state or '待确认'}",
                f"  - 镜头覆盖模式：{shot.state_contract.camera_coverage_mode or '待确认'}",
                f"  - 镜头路径：{shot.state_contract.camera_path or '待确认'}",
                f"  - 动作状态变化：{shot.state_contract.action_transition or '待确认'}",
                f"  - 终帧状态：{shot.state_contract.final_visible_frame or shot.last_frame_prompt}",
                f"  - 硬限制：{'；'.join(shot.state_contract.hard_limits) or '无'}",
                "- 动作时间轴：",
                *[
                    f"  - {beat.start_second:.2f}s-{beat.end_second:.2f}s：{beat.action}；情绪：{beat.emotion or '待确认'}"
                    for beat in shot.action_beats
                ],
                f"- 首帧提示词：{shot.first_frame_prompt}",
                f"- 视频提示词：{shot.video_prompt}",
                f"- 尾帧提示词：{shot.last_frame_prompt}",
                f"- 负面提示词：{shot.negative_prompt}",
                f"- 连续性要求：{'；'.join(shot.continuity_requirements) or '无'}",
                f"- 常见失败：{'；'.join(shot.expected_failures) or '待确认'}",
                f"- 失败修复：{shot.repair_strategy or '待确认'}",
                f"- 置信度：{shot.confidence}",
            ]
        )
    return "\n".join(lines)


def render_continuity_report(project: DramaProject) -> str:
    lines = ["## 连续性检查报告"]
    if not project.continuity_issues:
        lines.append("未发现结构性问题。")
        return "\n".join(lines)
    for issue in project.continuity_issues:
        lines.append(
            f"- [{issue.severity}] {issue.scope}：{issue.message} 建议：{issue.suggested_action}"
        )
    return "\n".join(lines)


def _merge_asset_pipeline_payload(
    local_data: dict[str, Any],
    asset_data: dict[str, Any],
) -> dict[str, Any]:
    merged_metadata: dict[str, Any] = {}
    if isinstance(local_data.get("metadata"), dict):
        merged_metadata.update(local_data["metadata"])
    if isinstance(asset_data.get("metadata"), dict):
        merged_metadata.update(asset_data["metadata"])
    merged_metadata.update(
        {
            "generation_mode": "llm-assets-local-shots",
            "generation_strategy": "asset-only-llm + local-shot-synthesis",
        }
    )
    return {
        "story_bible": _merge_dict_payload(local_data.get("story_bible"), asset_data.get("story_bible")),
        "characters": _merge_named_assets(local_data.get("characters"), asset_data.get("characters")),
        "scenes": _merge_named_assets(local_data.get("scenes"), asset_data.get("scenes")),
        "props": _merge_named_assets(local_data.get("props"), asset_data.get("props")),
        "shots": _objects(local_data.get("shots")),
        "production_locks": _merge_dict_payload(
            local_data.get("production_locks"),
            asset_data.get("production_locks"),
        ),
        "material_map": _objects(asset_data.get("material_map")) or _objects(local_data.get("material_map")),
        "join_contracts": _build_join_contract_dicts(_objects(local_data.get("shots"))),
        "repair_prompts": _objects(local_data.get("repair_prompts")),
        "continuity_issues": _objects(local_data.get("continuity_issues")),
        "metadata": merged_metadata,
    }


def _merge_named_assets(fallback: object, preferred: object) -> list[dict[str, Any]]:
    merged: dict[str, dict[str, Any]] = {}
    order: list[str] = []
    for item in _objects(fallback):
        item_id = str(item.get("id", "")).strip()
        if not item_id:
            continue
        merged[item_id] = dict(item)
        order.append(item_id)
    for item in _objects(preferred):
        item_id = str(item.get("id", "")).strip()
        if not item_id:
            continue
        current = merged.get(item_id, {})
        merged[item_id] = _merge_dict_payload(current, item)
        if item_id not in order:
            order.append(item_id)
    return [merged[item_id] for item_id in order]


def _merge_dict_payload(fallback: object, preferred: object) -> dict[str, Any]:
    base = dict(fallback) if isinstance(fallback, dict) else {}
    if not isinstance(preferred, dict):
        return base
    merged = dict(base)
    for key, value in preferred.items():
        if isinstance(value, str):
            if value.strip():
                merged[key] = value.strip()
            continue
        if isinstance(value, list):
            if value:
                merged[key] = value
            continue
        if isinstance(value, dict):
            nested = _merge_dict_payload(merged.get(key), value)
            if nested:
                merged[key] = nested
            continue
        if value not in (None, "", 0):
            merged[key] = value
    return merged


def _build_join_contract_dicts(shots: list[dict[str, Any]]) -> list[dict[str, Any]]:
    contracts: list[dict[str, Any]] = []
    for previous, current in zip(shots, shots[1:]):
        previous_id = str(previous.get("id", "")).strip()
        current_id = str(current.get("id", "")).strip()
        if not previous_id or not current_id:
            continue
        previous_scene = str(previous.get("scene_id", "")).strip()
        current_scene = str(current.get("scene_id", "")).strip()
        same_scene = previous_scene and previous_scene == current_scene
        previous_action = str(previous.get("visual_action", "")).strip() or "上一镜头动作"
        current_action = str(current.get("visual_action", "")).strip() or "下一镜头动作"
        contracts.append(
            {
                "from_shot": previous_id,
                "to_shot": current_id,
                "previous_end_state": str(previous.get("last_frame_prompt", "")).strip() or previous_action,
                "next_start_state": str(current.get("first_frame_prompt", "")).strip() or current_action,
                "state_delta": f"{previous_action} -> {current_action}",
                "risk_level": "low" if same_scene else "medium",
                "hard_cut_allowed": bool(same_scene),
                "bridge_requirement": "" if same_scene else "跨场景时注意空间和情绪衔接",
                "bridge_prompt_id": "",
                "safety_inserts": [],
                "sound_bridge": str(current.get("sound_design", "")).strip(),
                "fallback_edit": "必要时插入反应镜头或环境镜头缓冲转场",
            }
        )
    return contracts


def _objects(value: object) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, dict)]


def _strings(value: object) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item) for item in value]


def _number(value: object, default: float) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _status(value: object) -> str:
    return "confirmed" if value == "confirmed" else "待确认"


def build_default_agent(
    offline_demo: bool = False,
    client: LLMClient | None = None,
) -> DramaAgent:
    if offline_demo and client is not None:
        raise ValueError("offline_demo 与自定义模型客户端不能同时启用。")
    return DramaAgent(client or (RuleBasedClient() if offline_demo else None))
