import unittest
from unittest.mock import patch

import app


def progress_entry(status, *history):
    return {"status": status, "history": list(history)}


class FirstAllCompletedDateTests(unittest.TestCase):
    def test_uses_latest_of_each_problem_first_completion(self):
        prog = {
            "1": progress_entry(
                app.STATUS_SOLID,
                {"date": "2026-08-06", "action": "solve"},
                {"date": "2026-08-09", "action": "solve"},
            ),
            "2": progress_entry(
                app.STATUS_ARCHIVED,
                {"date": "2026-08-07", "action": "archive"},
            ),
            # 已软删题留下的孤儿进度不在 problem_ids 中，必须忽略。
            "999": progress_entry(
                app.STATUS_SOLID,
                {"date": "2026-08-10", "action": "solve"},
            ),
        }

        self.assertEqual(
            app._first_all_completed_date(prog, [1, 2]),
            "2026-08-07",
        )

    def test_returns_none_when_any_current_problem_is_todo(self):
        prog = {
            "1": progress_entry(
                app.STATUS_SOLID,
                {"date": "2026-08-06", "action": "solve"},
            ),
            "2": progress_entry(app.STATUS_TODO),
        }

        self.assertIsNone(app._first_all_completed_date(prog, [1, 2]))

    def test_returns_none_when_completion_history_is_missing_or_invalid(self):
        cases = (
            progress_entry(app.STATUS_SOLID),
            progress_entry(
                app.STATUS_SOLID,
                {"date": "not-a-date", "action": "solve"},
            ),
            progress_entry(
                app.STATUS_ARCHIVED,
                {"date": "2026-08-07", "action": "review"},
            ),
        )

        for entry in cases:
            with self.subTest(entry=entry):
                self.assertIsNone(app._first_all_completed_date({"1": entry}, [1]))

    def test_returns_none_for_empty_problem_set(self):
        self.assertIsNone(app._first_all_completed_date({}, []))


class PickCheckinBlurbTests(unittest.TestCase):
    def pick(self, **overrides):
        values = {
            "done_count": 2,
            "total": 2,
            "all_completed_date": "2026-08-07",
            "today_str": "2026-08-09",
            "streak": 4,
            "has_activity": False,
        }
        values.update(overrides)
        return app._pick_checkin_blurb(**values)

    def test_first_completion_celebration_wins_over_milestone(self):
        self.assertEqual(
            self.pick(all_completed_date="2026-08-09", streak=35),
            "100 题首战告捷，恭喜！",
        )

    def test_post_completion_keeps_day_and_week_milestones(self):
        cases = {
            3: "连续 3 天",
            5: "连续 5 天",
            7: "连续 1 周",
            35: "连续 5 周",
        }

        for streak, expected in cases.items():
            with self.subTest(streak=streak):
                self.assertEqual(self.pick(streak=streak), expected)

    def test_post_completion_uses_review_pool_off_milestones(self):
        with patch.object(
            app.random,
            "choice",
            return_value=app.CHECKIN_REVIEW_BLURB_POOL[0],
        ) as choice:
            self.assertEqual(
                self.pick(streak=4),
                app.CHECKIN_REVIEW_BLURB_POOL[0],
            )
            choice.assert_called_once_with(app.CHECKIN_REVIEW_BLURB_POOL)

    def test_in_progress_activity_keeps_general_pool(self):
        with patch.object(
            app.random,
            "choice",
            return_value=app.CHECKIN_BLURB_POOL[0],
        ) as choice:
            self.assertEqual(
                self.pick(
                    done_count=1,
                    all_completed_date=None,
                    has_activity=True,
                ),
                app.CHECKIN_BLURB_POOL[0],
            )
            choice.assert_called_once_with(app.CHECKIN_BLURB_POOL)

    def test_in_progress_without_activity_keeps_fallback(self):
        self.assertEqual(
            self.pick(done_count=1, all_completed_date=None, has_activity=False),
            "明天再来",
        )

    def test_no_progress_keeps_starting_blurb(self):
        self.assertEqual(
            self.pick(
                done_count=0,
                total=2,
                all_completed_date=None,
                streak=0,
            ),
            "起点即出发",
        )


if __name__ == "__main__":
    unittest.main()
