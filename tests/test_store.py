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
