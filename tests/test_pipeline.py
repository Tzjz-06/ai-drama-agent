import tempfile
import unittest
from pathlib import Path

from ai_drama_agent.models import GenerationOptions
from ai_drama_agent.pipeline import build_default_agent, write_outputs


class PipelineTests(unittest.TestCase):
    def test_offline_pipeline_exports_complete_package(self) -> None:
        script = Path("examples/sample_script.txt").read_text(encoding="utf-8")
        project = build_default_agent(offline_demo=True).run(
            script,
            GenerationOptions(title="测试剧", visual_style="二维国漫"),
        )

        self.assertGreaterEqual(len(project.characters), 1)
        self.assertGreaterEqual(len(project.scenes), 1)
        self.assertGreaterEqual(len(project.shots), 2)
        self.assertEqual(project.metadata["generation_mode"], "offline-rule-based")
        self.assertFalse(project.continuity_issues)
        self.assertIn("角色四视图", project.characters[0].turnaround_prompt)
        self.assertIn("纯白背景", project.characters[0].turnaround_prompt)
        self.assertIn("无人物", project.scenes[0].environment_prompt)
        self.assertIn("Seedance 2.0", project.shots[0].video_prompt)
        self.assertIn("时间轴", project.shots[0].video_prompt)
        self.assertIn("不生成音乐", project.shots[0].video_prompt)
        self.assertIn("不要生成任何字幕", project.shots[0].video_prompt)

        with tempfile.TemporaryDirectory() as directory:
            write_outputs(project, Path(directory))
            self.assertTrue((Path(directory) / "project.json").exists())
            self.assertTrue((Path(directory) / "storyboard.md").exists())
            self.assertIn("SH001", (Path(directory) / "production_package.md").read_text(encoding="utf-8"))

    def test_offline_pipeline_changes_with_different_scripts(self) -> None:
        first_script = "《雨夜归来》\n深夜，旧城区火车站下着大雨。林舟撑着透明雨伞走上月台，发现长椅上的旧信封。"
        second_script = "《天台告白》\n黄昏的学校天台，苏棠抱着一束花走向周屿，晚风吹起她的长发。"
        agent = build_default_agent(offline_demo=True)

        first_project = agent.run(
            first_script,
            GenerationOptions(title="雨夜归来", visual_style="二维国漫"),
        )
        second_project = agent.run(
            second_script,
            GenerationOptions(title="天台告白", visual_style="青春动画"),
        )

        self.assertNotEqual(first_project.story_bible.logline, second_project.story_bible.logline)
        self.assertNotEqual(first_project.shots[0].video_prompt, second_project.shots[0].video_prompt)
        self.assertNotEqual(first_project.scenes[0].name, second_project.scenes[0].name)

    def test_online_pipeline_uses_one_asset_request_and_local_shots(self) -> None:
        prompts: list[str] = []

        class FakeAssetClient:
            def __init__(self) -> None:
                self.calls = 0

            def complete_json(self, system_prompt: str, user_prompt: str) -> dict[str, object]:
                self.calls += 1
                prompts.append(user_prompt)
                return {
                    "story_bible": {
                        "logline": "病弱皇子借退婚风波翻盘。",
                        "genre": "古装权谋",
                        "world_rules": ["未知信息标记为待确认。"],
                        "visual_direction": "冷色深宫，压迫感构图",
                        "color_script": "冷青灰到局部金红反转",
                        "tone": "压抑后骤然反击",
                        "timeline": "深夜寝宫",
                        "unresolved_questions": ["苏万山后续行动待确认"],
                    },
                    "characters": [
                        {
                            "id": "C001",
                            "name": "萧晨",
                            "role": "废皇子",
                            "appearance": "病弱苍白但眼神锐利",
                            "costume": "素色寝衣",
                            "continuity_anchors": ["病弱伪装与冷冽眼神并存"],
                            "status": "confirmed",
                            "turnaround_prompt": "萧晨三视图",
                            "expression_prompt": "萧晨表情设定",
                            "negative_prompt": "角色漂移",
                        }
                    ],
                    "scenes": [
                        {
                            "id": "S001",
                            "name": "静眠殿",
                            "location": "大炎皇宫静眠殿",
                            "time": "深夜",
                            "weather": "寒风",
                            "layout": "床榻、木门、破窗形成纵深",
                            "lighting": "残火与冷风夜光",
                            "palette": "冷青灰",
                            "fixed_elements": ["床榻", "木门", "破窗"],
                            "atmosphere": "压抑",
                            "status": "confirmed",
                            "environment_prompt": "静眠殿夜景设定图",
                            "negative_prompt": "空间漂移",
                        }
                    ],
                    "props": [],
                    "production_locks": {
                        "character_lock": "萧晨保持病弱伪装",
                        "scene_lock": "静眠殿破败结构不变",
                        "style_core": "电影感二维国漫",
                    },
                    "material_map": [],
                    "metadata": {"generation_profile": "assets-only"},
                }

        script = (
            "深夜，破败寝宫里，萧晨卧床装病。"
            "苏清颜闯入退婚，当众羞辱。"
            "萧晨起身反击，提出道歉与赔罪条件。"
        )
        client = FakeAssetClient()
        project = build_default_agent(client=client).run(
            script,
            GenerationOptions(title="退婚反击", visual_style="电影感二维国漫"),
        )

        self.assertEqual(project.metadata["generation_mode"], "llm-assets-local-shots")
        self.assertEqual(project.story_bible.genre, "古装权谋")
        self.assertGreaterEqual(len(project.shots), 1)
        self.assertTrue(project.shots[0].video_prompt)
        self.assertEqual(client.calls, 1)
        self.assertEqual(len(prompts), 1)
        self.assertIn("只提取故事与资产", prompts[0])


if __name__ == "__main__":
    unittest.main()
