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

    def test_delete_project_removes_its_local_tasks(self) -> None:
        from ai_drama_agent.store import LocalStore

        with tempfile.TemporaryDirectory() as directory:
            store = LocalStore(Path(directory) / "app_state.json")
            user = store.register("creator", "", "secret123")
            project = store.create_project(user["id"], {"title": "待删除项目"})
            chapter = store.create_chapter(user["id"], project["id"], {"title": "第一集"})
            task = store.create_task(user["id"], project["id"], chapter["id"], "merge", {})

            store.delete_project(user["id"], project["id"])

            self.assertEqual(store.list_projects(user["id"]), [])
            self.assertEqual(store.list_tasks(user["id"], project["id"], chapter["id"]), [])
            self.assertNotIn(task["id"], store._data["tasks"])

    def test_cancelled_task_cannot_be_overwritten_by_worker_updates(self) -> None:
        from ai_drama_agent.store import LocalStore

        with tempfile.TemporaryDirectory() as directory:
            store = LocalStore(Path(directory) / "app_state.json")
            user = store.register("creator", "", "secret123")
            project = store.create_project(user["id"], {"title": "任务项目"})
            chapter = store.create_chapter(user["id"], project["id"], {"title": "第一集"})
            task = store.create_task(user["id"], project["id"], chapter["id"], "merge", {})

            cancelled = store.cancel_task(user["id"], project["id"], chapter["id"], task["id"])
            after_worker_update = store.update_task(
                user["id"], task["id"], {"status": "completed", "progress": 100}
            )

            self.assertEqual(cancelled["status"], "cancelled")
            self.assertEqual(after_worker_update["status"], "cancelled")

    def test_delete_task_only_removes_terminal_task(self) -> None:
        from ai_drama_agent.store import LocalStore

        with tempfile.TemporaryDirectory() as directory:
            store = LocalStore(Path(directory) / "app_state.json")
            user = store.register("creator", "", "secret123")
            project = store.create_project(user["id"], {"title": "任务项目"})
            chapter = store.create_chapter(user["id"], project["id"], {"title": "第一集"})
            task = store.create_task(user["id"], project["id"], chapter["id"], "merge", {})

            with self.assertRaises(ValueError):
                store.delete_task(user["id"], project["id"], chapter["id"], task["id"])

            store.cancel_task(user["id"], project["id"], chapter["id"], task["id"])
            store.delete_task(user["id"], project["id"], chapter["id"], task["id"])
            self.assertEqual(store.list_tasks(user["id"], project["id"], chapter["id"]), [])


if __name__ == "__main__":
    unittest.main()
