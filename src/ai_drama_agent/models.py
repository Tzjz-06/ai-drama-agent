"""智能体使用的结构化领域模型。

这些模型是项目的单一事实源。提示词、Markdown 和 JSON 导出都从这里生成。
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Literal


Status = Literal["confirmed", "待确认"]


@dataclass
class GenerationOptions:
    title: str
    visual_style: str
    aspect_ratio: str = "16:9"
    fps: int = 24
    target_model: str = "model-agnostic"
    language: str = "zh-CN"


@dataclass
class StoryBible:
    logline: str = ""
    genre: str = ""
    world_rules: list[str] = field(default_factory=list)
    visual_direction: str = ""
    color_script: str = ""
    tone: str = ""
    timeline: str = ""
    unresolved_questions: list[str] = field(default_factory=list)


@dataclass
class Character:
    id: str
    name: str
    role: str = ""
    age: str = ""
    personality: str = ""
    appearance: str = ""
    costume: str = ""
    props: list[str] = field(default_factory=list)
    expression_profile: list[str] = field(default_factory=list)
    voice_profile: str = ""
    continuity_anchors: list[str] = field(default_factory=list)
    status: Status = "confirmed"
    turnaround_prompt: str = ""
    expression_prompt: str = ""
    negative_prompt: str = ""


@dataclass
class Scene:
    id: str
    name: str
    location: str = ""
    time: str = ""
    weather: str = ""
    layout: str = ""
    lighting: str = ""
    palette: str = ""
    fixed_elements: list[str] = field(default_factory=list)
    atmosphere: str = ""
    status: Status = "confirmed"
    environment_prompt: str = ""
    negative_prompt: str = ""


@dataclass
class Prop:
    id: str
    name: str
    description: str = ""
    owner: str = ""
    continuity_notes: str = ""


@dataclass
class ActionBeat:
    start_second: float
    end_second: float
    action: str
    emotion: str = ""
    continuity_notes: str = ""


@dataclass
class ShotStateContract:
    reference_roles: list[str] = field(default_factory=list)
    reference_assets: list[str] = field(default_factory=list)
    first_visible_frame: str = ""
    screen_layout: str = ""
    subject_state: str = ""
    performance_cause: str = ""
    prop_state: str = ""
    camera_coverage_mode: str = ""
    camera_path: str = ""
    action_transition: str = ""
    final_visible_frame: str = ""
    hard_limits: list[str] = field(default_factory=list)


@dataclass
class Shot:
    id: str
    scene_id: str
    character_ids: list[str] = field(default_factory=list)
    prop_ids: list[str] = field(default_factory=list)
    start_second: float = 0.0
    duration_seconds: float = 4.0
    shot_size: str = ""
    camera_position: str = ""
    lens: str = ""
    camera_motion: str = ""
    visual_action: str = ""
    dialogue: str = ""
    narration: str = ""
    sound_design: str = ""
    action_beats: list[ActionBeat] = field(default_factory=list)
    prompt_id: str = ""
    state_contract: ShotStateContract = field(default_factory=ShotStateContract)
    first_frame_prompt: str = ""
    video_prompt: str = ""
    last_frame_prompt: str = ""
    negative_prompt: str = ""
    continuity_requirements: list[str] = field(default_factory=list)
    expected_failures: list[str] = field(default_factory=list)
    repair_strategy: str = ""
    confidence: Literal["high", "medium", "low"] = "medium"
    status: Status = "confirmed"


@dataclass
class ContinuityIssue:
    severity: Literal["error", "warning", "info"]
    scope: str
    message: str
    suggested_action: str = ""


@dataclass
class ProductionLocks:
    character_lock: str = ""
    scene_lock: str = ""
    style_core: str = ""
    visual_tone: str = ""
    color_lighting: str = ""
    camera_rules: str = ""
    action_intensity: str = ""
    continuity_lock: str = ""
    sound_mood: str = ""
    forbidden_drift: str = ""


@dataclass
class MaterialReference:
    id: str
    type: str = ""
    purpose: str = ""
    notes: str = ""
    prompt: str = ""


@dataclass
class JoinContract:
    from_shot: str
    to_shot: str
    previous_end_state: str = ""
    next_start_state: str = ""
    state_delta: str = ""
    risk_level: str = ""
    hard_cut_allowed: bool = False
    bridge_requirement: str = ""
    bridge_prompt_id: str = ""
    safety_inserts: list[str] = field(default_factory=list)
    sound_bridge: str = ""
    fallback_edit: str = ""


@dataclass
class RepairPrompt:
    id: str
    type: str = ""
    purpose: str = ""
    prompt: str = ""


@dataclass
class DramaProject:
    title: str
    source_script: str
    options: GenerationOptions
    story_bible: StoryBible = field(default_factory=StoryBible)
    characters: list[Character] = field(default_factory=list)
    scenes: list[Scene] = field(default_factory=list)
    props: list[Prop] = field(default_factory=list)
    shots: list[Shot] = field(default_factory=list)
    production_locks: ProductionLocks = field(default_factory=ProductionLocks)
    material_map: list[MaterialReference] = field(default_factory=list)
    join_contracts: list[JoinContract] = field(default_factory=list)
    repair_prompts: list[RepairPrompt] = field(default_factory=list)
    continuity_issues: list[ContinuityIssue] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
