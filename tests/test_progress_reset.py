import unittest
from datetime import date
from unittest.mock import patch

import app


class ResetEntryForNewRoundTests(unittest.TestCase):
    def test_records_previous_schedule_and_preserves_long_term_fields(self):
        original_event = {"date": "2026-08-01", "action": "review", "score": "easy"}
        entry = {
            "status": app.STATUS_SOLID,
            "review_stage": 4,
            "next_review": "2026-09-01",
            "last_done": "2026-08-01",
            "history": [original_event],
            "note": "双指针",
            "cheatsheet": "模板",
            "code_file": "solutions/python/001.py",
            "code_files": {"python": "solutions/python/001.py"},
            "future_field": {"keep": True},
        }

        with patch.object(app, "_today", return_value=date(2026, 8, 31)):
            changed = app._reset_entry_for_new_round(entry)

        self.assertTrue(changed)
        self.assertEqual(entry["status"], app.STATUS_TODO)
        self.assertEqual(entry["review_stage"], -1)
        self.assertEqual(entry["next_review"], "")
        self.assertEqual(entry["last_done"], "")
        self.assertEqual(entry["history"][0], original_event)
        self.assertEqual(
            entry["history"][-1],
            {
                "date": "2026-08-31",
                "action": "reset-all",
                "previous_status": app.STATUS_SOLID,
                "previous_review_stage": 4,
                "previous_next_review": "2026-09-01",
                "previous_last_done": "2026-08-01",
            },
        )
        self.assertEqual(entry["note"], "双指针")
        self.assertEqual(entry["cheatsheet"], "模板")
        self.assertEqual(entry["code_file"], "solutions/python/001.py")
        self.assertEqual(entry["code_files"], {"python": "solutions/python/001.py"})
        self.assertEqual(entry["future_field"], {"keep": True})

    def test_is_idempotent_while_entry_remains_unstarted(self):
        entry = {
            "status": app.STATUS_SHAKY,
            "review_stage": 2,
            "next_review": "2026-09-03",
            "last_done": "2026-08-27",
            "history": [],
        }

        with patch.object(app, "_today", return_value=date(2026, 8, 31)):
            self.assertTrue(app._reset_entry_for_new_round(entry))
            history_after_first_call = list(entry["history"])
            self.assertFalse(app._reset_entry_for_new_round(entry))

        self.assertEqual(entry["history"], history_after_first_call)

    def test_current_round_history_starts_after_latest_reset(self):
        entry = {
            "history": [
                {"date": "2026-07-01", "action": "solve"},
                {"date": "2026-08-01", "action": "reset-all"},
                {"date": "2026-08-20", "action": "solve"},
                {"date": "2026-08-31", "action": "reset-all"},
                {"date": "2026-08-31", "action": "solve"},
            ]
        }

        self.assertEqual(
            app._current_round_history(entry),
            [{"date": "2026-08-31", "action": "solve"}],
        )
        self.assertEqual(len(entry["history"]), 5)


class CurrentRoundStatisticsTests(unittest.TestCase):
    def test_done_today_ignores_actions_before_same_day_reset(self):
        prog = {
            "1": {
                "history": [
                    {"date": "2026-08-31", "action": "solve"},
                    {"date": "2026-08-31", "action": "reset-all"},
                ]
            },
            "2": {
                "history": [
                    {"date": "2026-08-31", "action": "review"},
                    {"date": "2026-08-31", "action": "reset-all"},
                    {"date": "2026-08-31", "action": "solve"},
                ]
            },
            "3": {
                "history": [
                    {"date": "2026-08-30", "action": "solve"},
                    {"date": "2026-08-31", "action": "reset-all"},
                    {"date": "2026-08-31", "action": "review"},
                ]
            },
        }

        with patch.object(app, "_today", return_value=date(2026, 8, 31)):
            solved, reviewed = app._done_today(prog)

        self.assertEqual(solved, {2})
        self.assertEqual(reviewed, {3})

    def test_first_all_completed_date_uses_only_latest_round(self):
        prog = {
            "1": {
                "status": app.STATUS_SOLID,
                "history": [
                    {"date": "2026-07-01", "action": "solve"},
                    {"date": "2026-08-01", "action": "reset-all"},
                    {"date": "2026-08-10", "action": "solve"},
                ],
            },
            "2": {
                "status": app.STATUS_ARCHIVED,
                "history": [
                    {"date": "2026-07-02", "action": "archive"},
                    {"date": "2026-08-01", "action": "reset-all"},
                    {"date": "2026-08-12", "action": "archive"},
                ],
            },
        }

        self.assertEqual(
            app._first_all_completed_date(prog, [1, 2]),
            "2026-08-12",
        )


class ResetAllProgressApiTests(unittest.TestCase):
    def setUp(self):
        self.client = app.app.test_client()

    def test_resets_only_existing_entries_for_current_problems(self):
        prog = {
            "1": {
                "status": app.STATUS_SOLID,
                "review_stage": 4,
                "next_review": "2026-09-01",
                "last_done": "2026-08-01",
                "history": [],
                "note": "保留",
            },
            "2": {
                "status": app.STATUS_TODO,
                "review_stage": -1,
                "next_review": "",
                "last_done": "",
                "history": [],
            },
            "999": {
                "status": app.STATUS_SOLID,
                "review_stage": 3,
                "next_review": "2026-09-02",
                "last_done": "2026-08-02",
                "history": [],
            },
        }
        orphan_before = dict(prog["999"])
        saved = []

        with (
            patch.object(app, "load_progress", return_value=prog),
            patch.object(app, "load_problems", return_value=[{"id": 1}, {"id": 2}, {"id": 3}]),
            patch.object(app, "save_progress", side_effect=lambda data: saved.append(data)),
            patch.object(app, "_today", return_value=date(2026, 8, 31)),
        ):
            first = self.client.post("/api/progress/reset-all")
            second = self.client.post("/api/progress/reset-all")

        self.assertEqual(first.status_code, 200)
        self.assertEqual(first.get_json(), {"ok": True, "total": 3, "reset_count": 1})
        self.assertEqual(second.get_json(), {"ok": True, "total": 3, "reset_count": 0})
        self.assertEqual(len(saved), 2)
        self.assertIs(saved[0], prog)
        self.assertEqual(prog["1"]["status"], app.STATUS_TODO)
        self.assertEqual(prog["1"]["note"], "保留")
        self.assertEqual(len(prog["1"]["history"]), 1)
        self.assertEqual(prog["2"]["history"], [])
        self.assertNotIn("3", prog)
        self.assertEqual(prog["999"], orphan_before)

    def test_empty_problem_set_succeeds_without_creating_entries(self):
        prog = {"999": {"status": app.STATUS_SOLID}}

        with (
            patch.object(app, "load_progress", return_value=prog),
            patch.object(app, "load_problems", return_value=[]),
            patch.object(app, "save_progress") as save_progress,
        ):
            response = self.client.post("/api/progress/reset-all")

        self.assertEqual(response.get_json(), {"ok": True, "total": 0, "reset_count": 0})
        save_progress.assert_called_once_with(prog)

    def test_dashboard_uses_reset_entries_as_todo_pool(self):
        problems = [
            {"id": 1, "title": "A", "difficulty": "简单", "category": "数组", "custom": False},
            {"id": 2, "title": "B", "difficulty": "中等", "category": "数组", "custom": False},
            {"id": 3, "title": "C", "difficulty": "困难", "category": "数组", "custom": False},
        ]
        prog = {
            str(problem["id"]): {
                "status": app.STATUS_TODO,
                "review_stage": -1,
                "next_review": "",
                "last_done": "",
                "history": [{"date": "2026-08-31", "action": "reset-all"}],
            }
            for problem in problems
        }
        config = {
            "daily_quota": {"weekday": 2, "weekend": 2},
            "overdue_alert_days": 3,
        }

        with (
            patch.object(app, "load_progress", return_value=prog),
            patch.object(app, "load_problems", return_value=problems),
            patch.object(app, "load_config", return_value=config),
            patch.object(app, "_today", return_value=date(2026, 8, 31)),
        ):
            dashboard = app.build_dashboard()

        self.assertEqual(dashboard["counts"][app.STATUS_TODO], 3)
        self.assertEqual(dashboard["todo_left"], 3)
        self.assertEqual(dashboard["due_review"], [])
        self.assertEqual(len(dashboard["today_new"]), 2)


if __name__ == "__main__":
    unittest.main()
