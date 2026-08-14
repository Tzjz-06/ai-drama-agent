import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


class StoreTests(unittest.TestCase):
    def test_account_project_and_chapter_lifecycle(self) -> None:
        from ai_drama_agent.store import AuthError, LocalStore

        with tempfile.TemporaryDirectory() as directory:
            store = LocalStore(Path(directory) / "app_state.json")
            user = store.register("饺子导演", "director@example.com", "secret123")
            token, logged_in = store.login("director@example.com", "secret123")

            self.assertEqual(user["id"], logged_in["id"])
            self.assertEqual(store.user_for_token(token)["username"], "饺子导演")

            project = store.create_project(
                user["id"],
                {"title": "雨夜归来", "style": "国漫电影感", "aspect_ratio": "9:16"},
            )
            self.assertEqual(project["product_type"], "drama")
            chapter = store.create_chapter(
                user["id"], project["id"], {"title": "第一集", "content": "林默推门而入。"}
            )
            store.save_production(
                user["id"],
                project["id"],
                chapter["id"],
                {"characters": [{"id": "CHAR-001"}], "scenes": [], "shots": []},
            )

            detail = store.get_project(user["id"], project["id"])
            self.assertEqual(detail["chapters"][0]["status"], "completed")
            self.assertEqual(store.list_projects(user["id"])[0]["character_count"], 1)

            store.logout(token)
            with self.assertRaises(AuthError):
                store.user_for_token(token)

    def test_novel_project_defaults_use_novel_identity(self) -> None:
        from ai_drama_agent.store import LocalStore

        with tempfile.TemporaryDirectory() as directory:
            store = LocalStore(Path(directory) / "app_state.json")
            user = store.register("writer", "", "secret123")
            project = store.create_project(
                user["id"],
                {"title": "饺子网文", "product_type": "novel"},
            )
            self.assertEqual(project["product_type"], "novel")
            self.assertEqual(project["style"], "移动端爽文")
            self.assertEqual(project["aspect_ratio"], "长篇连载")
            self.assertEqual(store.list_projects(user["id"])[0]["product_type"], "novel")

    def test_jubensha_project_defaults_and_summary_counts(self) -> None:
        from ai_drama_agent.store import LocalStore

        with tempfile.TemporaryDirectory() as directory:
            store = LocalStore(Path(directory) / "app_state.json")
            user = store.register("dm-writer", "", "secret123")
            project = store.create_project(
                user["id"],
                {"title": "饺子剧本杀", "product_type": "jubensha"},
            )
            self.assertEqual(project["product_type"], "jubensha")
            self.assertEqual(project["genre"], "还原推理")
            self.assertEqual(project["style"], "沉浸式盒装本")
            self.assertEqual(project["aspect_ratio"], "6人 / 4小时")

            chapter = store.create_chapter(user["id"], project["id"], {"title": "第 1 幕"})
            store.save_production(
                user["id"],
                project["id"],
                chapter["id"],
                {
                    "type": "jubensha_package",
                    "roles": [{"name": "沈砚"}, {"name": "陆岚"}],
                    "clues": [{"id": "CLUE-001"}],
                    "rounds": [{"name": "入席"}],
                },
            )
            summary = store.list_projects(user["id"])[0]
            self.assertEqual(summary["jubensha_role_count"], 2)
            self.assertEqual(summary["jubensha_clue_count"], 1)
            self.assertEqual(summary["jubensha_round_count"], 1)

    def test_novel_and_jubensha_packages_can_be_saved_after_card_edit(self) -> None:
        from ai_drama_agent.store import LocalStore

        with tempfile.TemporaryDirectory() as directory:
            store = LocalStore(Path(directory) / "app_state.json")
            user = store.register("package-editor", "", "secret123")

            novel = store.create_project(
                user["id"], {"title": "旧书名", "product_type": "novel"}
            )
            novel_chapter = store.create_chapter(user["id"], novel["id"], {"title": "第 1 章"})
            store.save_production(
                user["id"],
                novel["id"],
                novel_chapter["id"],
                {"type": "novel_package", "title": "旧书名", "positioning": "旧卖点"},
            )
            updated_novel = store.update_production_package(
                user["id"],
                novel["id"],
                novel_chapter["id"],
                {"type": "novel_package", "title": "新书名", "positioning": "新卖点"},
            )
            self.assertEqual(updated_novel["production"]["title"], "新书名")
            self.assertEqual(updated_novel["production"]["positioning"], "新卖点")

            jubensha = store.create_project(
                user["id"], {"title": "旧剧本", "product_type": "jubensha"}
            )
            jubensha_chapter = store.create_chapter(
                user["id"], jubensha["id"], {"title": "第 1 幕"}
            )
            store.save_production(
                user["id"],
                jubensha["id"],
                jubensha_chapter["id"],
                {"type": "jubensha_package", "roles": [{"name": "旧角色"}]},
            )
            updated_jubensha = store.update_production_package(
                user["id"],
                jubensha["id"],
                jubensha_chapter["id"],
                {"type": "jubensha_package", "roles": [{"name": "新角色"}]},
            )
            self.assertEqual(updated_jubensha["production"]["roles"][0]["name"], "新角色")

    def test_delete_chapter_removes_its_production_without_touching_other_chapters(self) -> None:
        from ai_drama_agent.store import LocalStore, StoreError

        with tempfile.TemporaryDirectory() as directory:
            store = LocalStore(Path(directory) / "app_state.json")
            owner = store.register("owner", "", "secret123")
            other = store.register("other", "", "secret123")
            project = store.create_project(owner["id"], {"title": "章节删除测试"})
            first = store.create_chapter(owner["id"], project["id"], {"title": "第一集"})
            second = store.create_chapter(owner["id"], project["id"], {"title": "第二集"})
            store.save_production(
                owner["id"],
                project["id"],
                first["id"],
                {"characters": [{"id": "CHAR-001"}], "scenes": [], "props": [], "shots": []},
            )
            store.save_production(
                owner["id"],
                project["id"],
                second["id"],
                {"characters": [{"id": "CHAR-002"}], "scenes": [], "props": [], "shots": []},
            )
            store._data["tasks"]["chapter_task"] = {
                "project_id": project["id"],
                "chapter_id": first["id"],
            }
            store._data["tasks"]["other_chapter_task"] = {
                "project_id": project["id"],
                "chapter_id": second["id"],
            }

            with self.assertRaises(StoreError):
                store.delete_chapter(other["id"], project["id"], first["id"])

            store.delete_chapter(owner["id"], project["id"], first["id"])

            detail = store.get_project(owner["id"], project["id"])
            self.assertEqual([chapter["id"] for chapter in detail["chapters"]], [second["id"]])
            self.assertEqual(detail["chapters"][0]["production"]["characters"][0]["id"], "CHAR-002")
            self.assertNotIn("chapter_task", store._data["tasks"])
            self.assertIn("other_chapter_task", store._data["tasks"])

    def test_legacy_project_type_migration_keeps_products_separated(self) -> None:
        from ai_drama_agent.store import LocalStore

        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "app_state.json"
            user_id = "user_writer"
            project_base = {
                "user_id": user_id,
                "description": "",
                "status": "draft",
                "created_at": "2026-08-14T00:00:00+00:00",
                "updated_at": "2026-08-14T00:00:00+00:00",
                "chapters": [],
                "product_type": "drama",
            }
            state = {
                "users": {user_id: {"id": user_id, "username": "writer", "email": ""}},
                "projects": {
                    "project_script": project_base
                    | {
                        "id": "project_script",
                        "title": "归途",
                        "style": "沉浸式盒装本",
                        "genre": "还原推理",
                        "aspect_ratio": "6人 / 4小时",
                    },
                    "project_novel": project_base
                    | {
                        "id": "project_novel",
                        "title": "长夜行",
                        "style": "精品群像",
                        "genre": "悬疑推理",
                        "aspect_ratio": "长篇连载",
                    },
                    "project_drama": project_base
                    | {
                        "id": "project_drama",
                        "title": "雨夜来信",
                        "style": "电影感二维国漫",
                        "genre": "短剧",
                        "aspect_ratio": "9:16",
                    },
                },
            }
            path.write_text(json.dumps(state, ensure_ascii=False), encoding="utf-8")

            store = LocalStore(path)
            projects = {project["id"]: project for project in store.list_projects(user_id)}

            self.assertEqual(projects["project_script"]["product_type"], "jubensha")
            self.assertEqual(projects["project_novel"]["product_type"], "novel")
            self.assertEqual(projects["project_drama"]["product_type"], "drama")
            persisted = json.loads(path.read_text(encoding="utf-8"))
            self.assertEqual(persisted["projects"]["project_script"]["product_type"], "jubensha")
            self.assertEqual(persisted["projects"]["project_novel"]["product_type"], "novel")

    def test_duplicate_account_and_wrong_password_are_rejected(self) -> None:
        from ai_drama_agent.store import AuthError, LocalStore, StoreError

        with tempfile.TemporaryDirectory() as directory:
            store = LocalStore(Path(directory) / "app_state.json")
            store.register("creator", "creator@example.com", "secret123")
            with self.assertRaises(StoreError):
                store.register("creator", "other@example.com", "secret123")
            with self.assertRaises(AuthError):
                store.login("creator", "wrong-password")

    def test_production_assets_can_be_edited_without_changing_their_ids(self) -> None:
        from ai_drama_agent.store import LocalStore, StoreError

        with tempfile.TemporaryDirectory() as directory:
            store = LocalStore(Path(directory) / "app_state.json")
            user = store.register("creator", "", "secret123")
            project = store.create_project(user["id"], {"title": "测试项目"})
            chapter = store.create_chapter(user["id"], project["id"], {"title": "第一集"})
            store.save_production(
                user["id"],
                project["id"],
                chapter["id"],
                {
                    "characters": [
                        {
                            "id": "CHAR-001",
                            "name": "林默",
                            "role": "快递员",
                            "appearance": "黑色短发",
                            "costume": "深色夹克",
                            "turnaround_prompt": "角色提示词",
                            "status": "待确认",
                        }
                    ],
                    "scenes": [],
                    "props": [],
                    "shots": [{"id": "SHOT-001", "character_ids": ["CHAR-001"]}],
                },
            )

            updated = store.update_production_asset(
                user["id"],
                project["id"],
                chapter["id"],
                "characters",
                "CHAR-001",
                {"id": "CHAR-999", "name": "林默（雨夜）", "costume": "湿透的深色夹克"},
            )

            character = updated["production"]["characters"][0]
            self.assertEqual(character["id"], "CHAR-001")
            self.assertEqual(character["name"], "林默（雨夜）")
            self.assertEqual(character["costume"], "湿透的深色夹克")
            self.assertEqual(updated["production"]["shots"][0]["character_ids"], ["CHAR-001"])
            with self.assertRaises(StoreError):
                store.update_production_asset(
                    user["id"], project["id"], chapter["id"], "characters", "CHAR-404", {}
                )
            with self.assertRaises(ValueError):
                store.update_production_asset(
                    user["id"], project["id"], chapter["id"], "videos", "CHAR-001", {}
                )

    def test_shot_prompts_can_be_edited_without_changing_shot_or_asset_references(self) -> None:
        from ai_drama_agent.store import LocalStore, StoreError

        with tempfile.TemporaryDirectory() as directory:
            store = LocalStore(Path(directory) / "app_state.json")
            user = store.register("creator", "", "secret123")
            project = store.create_project(user["id"], {"title": "测试项目"})
            chapter = store.create_chapter(user["id"], project["id"], {"title": "第一集"})
            store.save_production(
                user["id"],
                project["id"],
                chapter["id"],
                {
                    "characters": [],
                    "scenes": [],
                    "props": [],
                    "shots": [
                        {
                            "id": "SHOT-001",
                            "scene_id": "SCENE-001",
                            "character_ids": ["CHAR-001"],
                            "prop_ids": ["PROP-001"],
                            "first_frame_prompt": "旧首帧",
                            "video_prompt": "旧视频",
                            "last_frame_prompt": "旧尾帧",
                            "negative_prompt": "旧负面",
                        }
                    ],
                },
            )

            updated = store.update_shot_prompts(
                user["id"],
                project["id"],
                chapter["id"],
                "SHOT-001",
                {"first_frame_prompt": "新首帧", "negative_prompt": "新负面", "id": "SHOT-999"},
            )

            shot = updated["production"]["shots"][0]
            self.assertEqual(shot["id"], "SHOT-001")
            self.assertEqual(shot["scene_id"], "SCENE-001")
            self.assertEqual(shot["character_ids"], ["CHAR-001"])
            self.assertEqual(shot["first_frame_prompt"], "新首帧")
            self.assertEqual(shot["negative_prompt"], "新负面")
            with self.assertRaises(StoreError):
                store.update_shot_prompts(
                    user["id"], project["id"], chapter["id"], "SHOT-404", {}
                )

    def test_login_session_survives_store_restart_without_persisting_raw_token(self) -> None:
        from ai_drama_agent.store import AuthError, LocalStore

        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "app_state.json"
            store = LocalStore(path)
            user = store.register("creator", "", "secret123")
            token, _ = store.login("creator", "secret123")

            restarted_store = LocalStore(path)
            self.assertEqual(restarted_store.user_for_token(token)["id"], user["id"])
            self.assertNotIn(token, path.read_text(encoding="utf-8"))

            restarted_store.logout(token)
            with self.assertRaises(AuthError):
                LocalStore(path).user_for_token(token)

    def test_default_frozen_data_path_migrates_legacy_state_without_overwriting(self) -> None:
        from ai_drama_agent.store import LocalStore

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            legacy = root / "bundle" / "data" / "app_state.json"
            user_data = root / "local-app-data" / "FrameForgeStudio"
            legacy.parent.mkdir(parents=True)
            legacy.write_text('{"users": {"u": {}}, "projects": {}}', encoding="utf-8")

            with patch("ai_drama_agent.store.app_root", return_value=root / "bundle"), patch(
                "ai_drama_agent.store.app_data_root", return_value=user_data
            ):
                store = LocalStore()
                self.assertEqual(store.path, user_data / "app_state.json")
                self.assertIn("u", store._data["users"])
                self.assertTrue(store.path.is_file())

                store.path.write_text('{"users": {"new": {}}, "projects": {}}', encoding="utf-8")
                legacy.write_text('{"users": {"legacy-changed": {}}, "projects": {}}', encoding="utf-8")
                second = LocalStore()
                self.assertIn("new", second._data["users"])
                self.assertNotIn("legacy-changed", second._data["users"])


if __name__ == "__main__":
    unittest.main()
