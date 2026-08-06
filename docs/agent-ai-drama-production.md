# AI Drama Production Skill 映射

提示词编排依据 `D:\download\ai-drama-production-master (1).zip` 中的 `SKILL.md`、`references/workflow.md`、`references/templates.md` 和 `references/review-checklists.md`。

项目中的映射关系：

- `production_locks`：角色、场景、风格、镜头、连续性、声音和禁止漂移锁。
- `material_map`：角色、场景、道具及动作参考的 `@图片` / `@视频` 用途表。
- `ShotStateContract`：每个 `VIDEO_MAIN` 的首帧、屏幕方位、主体/道具状态、表演因果、镜头路径和终帧。
- `join_contracts`：相邻镜头的状态差异、风险、硬切、桥接、声音桥和备用剪法。
- `repair_prompts`：高风险连接的 `VIDEO_BRIDGE`、`VIDEO_INSERT`、`VIDEO_REPAIR` 可复制提示词。

默认交付以单片段 `VIDEO_MAIN` 为主，不强制用户逐镜生成关键帧；关键帧只作为后续修复工具。所有对白、音效、环境声和配乐写在视频提示词时间码内，不使用 `@音频` 引用。
