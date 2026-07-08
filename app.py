"""
LeetCode Hot 100 tracker.

单文件 Flask，数据全部落 JSON。跑：
    python app.py
然后访问 http://localhost:5001
"""
from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from datetime import date, datetime, timedelta
from pathlib import Path

from flask import (
    Flask,
    abort,
    jsonify,
    redirect,
    render_template,
    request,
    url_for,
)

ROOT = Path(__file__).resolve().parent
DATA_DIR = ROOT / "data"
SOLUTIONS_DIR = ROOT / "solutions"
CONFIG_PATH = ROOT / "config.json"
CONFIG_LOCAL_PATH = ROOT / "config.local.json"
PROBLEMS_PATH = DATA_DIR / "problems.json"
PROGRESS_PATH = DATA_DIR / "progress.json"
PROGRESS_LOCAL_PATH = DATA_DIR / "progress.local.json"
CHEATSHEET_PATH = DATA_DIR / "cheatsheet.md"

STATUS_TODO = "todo"        # 未刷
STATUS_FORGOT = "forgot"    # 🔴 思路忘（新刷或重刷完从这里起步进复习队列）
STATUS_SHAKY = "shaky"      # 🟡 语法忘 / 磕绊
STATUS_SOLID = "solid"      # 🟢 稳
STATUS_ARCHIVED = "archived"  # 归档，不再复习

SCORE_EASY = "easy"     # 😄 秒A
SCORE_OK = "ok"         # 🙂 磕绊
SCORE_HARD = "hard"     # 😩 卡住

app = Flask(__name__)


# ---------- I/O ----------

def load_json(path: Path, default):
    if not path.exists():
        return default
    with path.open("r", encoding="utf-8") as f:
        text = f.read().strip()
        if not text:
            return default
        return json.loads(text)


def save_json(path: Path, data) -> None:
    tmp = path.with_suffix(path.suffix + ".tmp")
    with tmp.open("w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    tmp.replace(path)


def _today() -> date:
    """返回"今天"的日期，考虑用户配置的 day_boundary_hour（一天何时结束）。

    默认 0（0 点）—— 自然日，等价于 date.today()。
    如果配置成 3（03:00），凌晨 0:00~2:59 仍然算"昨天"，直到 03:00 才切到新一天。
    值域 [0, 6]，允许 0.5 步长（例如 3.5 → 03:30）。
    """
    boundary = float(load_config().get("day_boundary_hour", 0) or 0)
    if boundary <= 0:
        return date.today()
    now = datetime.now()
    boundary_hour = int(boundary)
    boundary_minute = int(round((boundary - boundary_hour) * 60))
    threshold = now.replace(hour=boundary_hour, minute=boundary_minute, second=0, microsecond=0)
    if now < threshold:
        return (now - timedelta(days=1)).date()
    return now.date()


def _load_dotenv() -> None:
    """极简 .env 解析器：只支持 KEY=VALUE，不支持 quoting/interp。"""
    env_path = ROOT / ".env"
    if not env_path.exists():
        return
    for line in env_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, _, v = line.partition("=")
        k, v = k.strip(), v.strip()
        # 剥掉可选的引号
        if len(v) >= 2 and v[0] == v[-1] and v[0] in ("'", '"'):
            v = v[1:-1]
        os.environ.setdefault(k, v)


_load_dotenv()


def load_config() -> dict:
    """读 config.json，config.local.json 里同名字段覆盖之。

    敏感字段（feishu webhook / secret 等）从 .env 环境变量读，不走 config 文件。
    """
    base = load_json(CONFIG_PATH, {})
    local = load_json(CONFIG_LOCAL_PATH, {})
    base.update(local)
    # 敏感字段从环境变量注入
    if os.environ.get("FEISHU_WEBHOOK"):
        base["feishu_webhook"] = os.environ["FEISHU_WEBHOOK"]
    if os.environ.get("FEISHU_SECRET"):
        base["feishu_secret"] = os.environ["FEISHU_SECRET"]
    return base


def load_problems() -> list[dict]:
    """返回扁平列表，附上 category 字段。"""
    raw = load_json(PROBLEMS_PATH, {"categories": []})
    flat = []
    for cat in raw["categories"]:
        for p in cat["problems"]:
            flat.append({**p, "category": cat["name"]})
    return flat


def load_categories() -> list[dict]:
    """带上 category 名的原始分类结构。"""
    return load_json(PROBLEMS_PATH, {"categories": []})["categories"]


def load_progress() -> dict:
    """读进度：优先 progress.local.json，回退到 progress.json。

    progress.local.json 是你私人的刷题进度，不进 git；
    progress.json 是公开仓库里的空 seed。
    """
    if PROGRESS_LOCAL_PATH.exists():
        return load_json(PROGRESS_LOCAL_PATH, {})
    return load_json(PROGRESS_PATH, {})


def _progress_write_path() -> Path:
    """写进度时首选 local；如果 local 从未存在过，写 seed 那份。"""
    if PROGRESS_LOCAL_PATH.exists() or (DATA_DIR / ".use_local_progress").exists():
        return PROGRESS_LOCAL_PATH
    return PROGRESS_PATH


def save_progress(prog: dict) -> None:
    save_json(_progress_write_path(), prog)


# ---------- 遗忘曲线 ----------

def _intervals() -> list[int]:
    return load_config().get("review_intervals_days", [1, 3, 7, 15, 30])


def _next_review_date(stage: int) -> str:
    """stage 从 0 开始，取 intervals[stage]。stage 超出 → 归档。"""
    intervals = _intervals()
    if stage >= len(intervals):
        return ""  # archived
    delta = intervals[stage]
    return (_today() + timedelta(days=delta)).isoformat()


def _default_entry() -> dict:
    return {
        "status": STATUS_TODO,
        "note": "",
        "cheatsheet": "",
        "code_file": "",         # 兼容老数据（默认语言指向的路径）
        "code_files": {},        # 新字段：{"python": "solutions/python/...", "go": "..."}
        "history": [],
        "review_stage": -1,
        "next_review": "",
        "last_done": "",
    }


def apply_first_solve(entry: dict, status: str) -> dict:
    """第一次刷完 / 手动改状态。status ∈ {forgot, shaky, solid}。"""
    today = _today().isoformat()
    entry["status"] = status
    entry["last_done"] = today
    if status == STATUS_SOLID:
        # 直接进复习队列稍后档位（+3 天开始）
        entry["review_stage"] = 1
    else:
        entry["review_stage"] = 0
    entry["next_review"] = _next_review_date(entry["review_stage"])
    entry["history"].append({"date": today, "action": "solve", "status": status})
    return entry


def apply_review(entry: dict, score: str) -> dict:
    """复习后打分：easy 前进一档；ok 保持；hard 回退到档 0。"""
    today = _today().isoformat()
    intervals = _intervals()
    stage = entry.get("review_stage", 0)
    if stage < 0:
        stage = 0

    if score == SCORE_EASY:
        stage += 1
    elif score == SCORE_HARD:
        stage = 0
    # ok 保持

    entry["last_done"] = today
    entry["history"].append({"date": today, "action": "review", "score": score})

    if stage >= len(intervals):
        entry["status"] = STATUS_ARCHIVED
        entry["review_stage"] = stage
        entry["next_review"] = ""
    else:
        entry["review_stage"] = stage
        entry["next_review"] = _next_review_date(stage)
        # 状态跟自评走
        if score == SCORE_HARD:
            entry["status"] = STATUS_FORGOT
        elif score == SCORE_OK:
            entry["status"] = STATUS_SHAKY
        else:  # easy
            entry["status"] = STATUS_SOLID
    return entry


# ---------- 今日看板动态计算 ----------

def _get_status(prog: dict, pid: int) -> str:
    return prog.get(str(pid), {}).get("status", STATUS_TODO)


def _get_next_review(prog: dict, pid: int) -> str:
    return prog.get(str(pid), {}).get("next_review", "")


def _daily_quota() -> int:
    cfg = load_config().get("daily_quota", {"weekday": 3, "weekend": 6})
    is_weekend = _today().weekday() >= 5
    return cfg["weekend"] if is_weekend else cfg["weekday"]


def _done_today(prog: dict) -> tuple[set[int], set[int]]:
    """今天完成的 pid 集合，拆成 (solved_ids, reviewed_ids)。

    - solve：新题第一次刷完 → 消耗新题配额
    - review：复习到期的题 → 不消耗新题配额（复习自成一路）
    - 推迟 / 归档：都不算完成

    返回两个 disjoint 集合。同一天既 solve 又 review 同一题（极端情况）
    只算 solve。
    """
    today = _today().isoformat()
    solved: set[int] = set()
    reviewed: set[int] = set()
    for pid, entry in prog.items():
        pid_int = int(pid)
        for h in entry.get("history", []):
            if h.get("date") != today:
                continue
            action = h.get("action")
            if action == "solve":
                solved.add(pid_int)
                reviewed.discard(pid_int)
                break
            elif action == "review":
                if pid_int not in solved:
                    reviewed.add(pid_int)
    return solved, reviewed


def _balanced_pick(todo_pool: list[dict], n: int) -> list[dict]:
    """从未刷池里按难度尽量均衡挑 n 道。

    策略：给每档难度定一个 target 数（大致贴合 hot100 简/中/困 = 20/68/12
    的分布 + "别一天全一种" 的诉求），先按 target 取，池子空了再用其他档补。
    保持返回顺序 = todo_pool 里的原顺序（沿用分类推进感）。
    """
    targets_by_n = {
        1: {"简单": 0, "中等": 1, "困难": 0},
        2: {"简单": 1, "中等": 1, "困难": 0},
        3: {"简单": 1, "中等": 1, "困难": 1},
        4: {"简单": 1, "中等": 2, "困难": 1},
        5: {"简单": 2, "中等": 2, "困难": 1},
        6: {"简单": 2, "中等": 3, "困难": 1},
    }
    target = targets_by_n.get(n)
    if target is None:
        # 大 quota 场景：按 2:6:2 大致分
        target = {
            "简单": max(1, n // 4),
            "中等": max(1, n // 2),
            "困难": max(1, n // 6),
        }

    by_diff: dict[str, list[dict]] = {"简单": [], "中等": [], "困难": []}
    for p in todo_pool:
        by_diff.setdefault(p["difficulty"], []).append(p)

    picked_ids: set[int] = set()
    for diff, need in target.items():
        for p in by_diff.get(diff, [])[:need]:
            picked_ids.add(p["id"])

    # 不够 n 个 → 按 todo_pool 原顺序补
    if len(picked_ids) < n:
        for p in todo_pool:
            if len(picked_ids) >= n:
                break
            picked_ids.add(p["id"])

    # 保持原顺序返回，且截断到 n
    return [p for p in todo_pool if p["id"] in picked_ids][:n]


def _estimate_finish(todo_left: int, weekday_q: int, weekend_q: int, done_today: int, quota_today: int) -> dict:
    """精确日历模拟：从今天剩余配额开始，逐日按 weekday/weekend 扣，算完成日。

    返回:
        {
          "days_left": int | None,      # 距离刷完还有几天（含今天）；None = 无解
          "finish_date": "YYYY-MM-DD" | None,
          "reachable": bool,            # False = 配额全 0 时 unreachable
        }
    """
    if todo_left <= 0:
        return {"days_left": 0, "finish_date": _today().isoformat(), "reachable": True}
    if weekday_q <= 0 and weekend_q <= 0:
        return {"days_left": None, "finish_date": None, "reachable": False}

    remaining = todo_left
    # 今天：能挤出来的 = quota_today - done_today (最少 0)
    today = _today()
    today_slot = max(0, quota_today - done_today)
    if today_slot > 0:
        remaining -= min(remaining, today_slot)
        if remaining <= 0:
            return {"days_left": 0, "finish_date": today.isoformat(), "reachable": True}

    # 从明天开始逐日累计
    d = today
    days_counted = 0    # 从今天起过了几个整天
    max_iter = 3650     # 硬顶 10 年，防止死循环
    while remaining > 0 and days_counted < max_iter:
        d = d + timedelta(days=1)
        days_counted += 1
        slot = weekend_q if d.weekday() >= 5 else weekday_q
        if slot <= 0:
            continue
        remaining -= min(remaining, slot)

    if remaining > 0:
        return {"days_left": None, "finish_date": None, "reachable": False}
    return {
        "days_left": days_counted,
        "finish_date": d.isoformat(),
        "reachable": True,
    }


def build_dashboard() -> dict:
    """动态构造今日看板。"""
    problems = load_problems()
    prog = load_progress()
    today = _today().isoformat()
    overdue_days = load_config().get("overdue_alert_days", 3)

    by_id = {p["id"]: p for p in problems}
    solved_today_ids, reviewed_today_ids = _done_today(prog)
    done_today_ids = solved_today_ids | reviewed_today_ids

    # 到期复习：next_review <= today 且状态在复习队列内
    due_review = []
    overdue = []
    for pid_str, entry in prog.items():
        if entry.get("status") in (STATUS_ARCHIVED, STATUS_TODO):
            continue
        nr = entry.get("next_review", "")
        if not nr:
            continue
        pid = int(pid_str)
        if pid in done_today_ids:
            continue
        if nr <= today:
            item = {**by_id.get(pid, {"id": pid, "title": "?", "difficulty": "?"}),
                    "status": entry["status"],
                    "next_review": nr,
                    "review_stage": entry.get("review_stage", 0),
                    "note": entry.get("note", "")}
            due_review.append(item)
            # 逾期红牌
            try:
                if (_today() - date.fromisoformat(nr)).days > overdue_days:
                    overdue.append(pid)
            except ValueError:
                pass

    # 未刷池按分类原顺序排；今日新题配额只由"今天已刷新题"扣减 —— 复习不吃新题配额
    quota = _daily_quota()
    new_slots = max(0, quota - len(solved_today_ids))

    todo_pool = []
    for p in problems:
        if _get_status(prog, p["id"]) == STATUS_TODO:
            todo_pool.append(p)
    today_new = _balanced_pick(todo_pool, new_slots)
    # 新题也带上 note（新题多半为空，但复用同一模板简化前端）
    for p in today_new:
        p["note"] = prog.get(str(p["id"]), {}).get("note", "")

    # 加练池：todo_pool 里除去今日新题的下 10 道，按原顺序
    today_new_ids = {p["id"] for p in today_new}
    extras_pool = [p for p in todo_pool if p["id"] not in today_new_ids][:10]
    for p in extras_pool:
        p["note"] = prog.get(str(p["id"]), {}).get("note", "")

    # 逾期数（红牌题的 id 集）
    overdue_set = set(overdue)
    for r in due_review:
        r["is_overdue"] = r["id"] in overdue_set

    total = len(problems)
    counts = {
        STATUS_TODO: sum(1 for p in problems if _get_status(prog, p["id"]) == STATUS_TODO),
        STATUS_FORGOT: sum(1 for p in problems if _get_status(prog, p["id"]) == STATUS_FORGOT),
        STATUS_SHAKY: sum(1 for p in problems if _get_status(prog, p["id"]) == STATUS_SHAKY),
        STATUS_SOLID: sum(1 for p in problems if _get_status(prog, p["id"]) == STATUS_SOLID),
        STATUS_ARCHIVED: sum(1 for p in problems if _get_status(prog, p["id"]) == STATUS_ARCHIVED),
    }

    # 完成预估：只算未刷题（复习是终身的，永远刷不完）
    dq = load_config().get("daily_quota", {"weekday": 3, "weekend": 6})
    finish = _estimate_finish(
        todo_left=len(todo_pool),
        weekday_q=int(dq.get("weekday", 0)),
        weekend_q=int(dq.get("weekend", 0)),
        done_today=len(solved_today_ids),
        quota_today=quota,
    )

    return {
        "date": today,
        "is_weekend": _today().weekday() >= 5,
        "quota": quota,
        "done_today": sorted(done_today_ids),
        "solved_today": sorted(solved_today_ids),
        "reviewed_today": sorted(reviewed_today_ids),
        "due_review": due_review,
        "today_new": today_new,
        "extras_pool": extras_pool,
        "todo_left": len(todo_pool),
        "counts": counts,
        "total": total,
        "finish": finish,
    }


def build_preview(target: date) -> dict:
    """预测某一天（通常是明天）打开看板会看到什么。

    只读快照：模拟 target 那天进看板时 build_dashboard 会算出的数据。
    - 复习列表 = 那天到期或已过期（next_review <= target），且不在"今天已做"里
    - 新题列表 = 从当前 todo 池里按难度均衡取 quota 道（quota 按 target 是工作日/周末算）
    """
    problems = load_problems()
    prog = load_progress()
    by_id = {p["id"]: p for p in problems}
    target_str = target.isoformat()
    overdue_days = load_config().get("overdue_alert_days", 3)

    # 复习到期（假设 today 到 target 之间用户没做题；如果做了会自动从 todo 池里减）
    due_review = []
    for pid_str, entry in prog.items():
        if entry.get("status") in (STATUS_ARCHIVED, STATUS_TODO):
            continue
        nr = entry.get("next_review", "")
        if not nr or nr > target_str:
            continue
        pid = int(pid_str)
        item = {
            **by_id.get(pid, {"id": pid, "title": "?", "difficulty": "?", "slug": ""}),
            "status": entry["status"],
            "next_review": nr,
            "review_stage": entry.get("review_stage", 0),
            "note": entry.get("note", ""),
        }
        try:
            days_overdue = (target - date.fromisoformat(nr)).days
            item["is_overdue"] = days_overdue > overdue_days
        except ValueError:
            item["is_overdue"] = False
        due_review.append(item)

    # 新题：quota 按 target 是否周末算
    dq = load_config().get("daily_quota", {"weekday": 3, "weekend": 6})
    quota = dq["weekend"] if target.weekday() >= 5 else dq["weekday"]

    todo_pool = [p for p in problems if _get_status(prog, p["id"]) == STATUS_TODO]
    today_new = _balanced_pick(todo_pool, quota)
    for p in today_new:
        p["note"] = prog.get(str(p["id"]), {}).get("note", "")

    return {
        "date": target_str,
        "is_weekend": target.weekday() >= 5,
        "quota": quota,
        "due_review": due_review,
        "today_new": today_new,
    }


# ---------- 代码文件 ----------

_SAFE_TITLE_RE = re.compile(r"[\\/:*?\"<>|\s]+")

_LANG_META = {
    "python": {"ext": "py", "comment": "# ", "template": '''"""
{header}
"""


class Solution:
    def solve(self):
        pass
'''},
    "go": {"ext": "go", "comment": "// ", "template": '''// {header}

package solution

// TODO
'''},
    "cpp": {"ext": "cpp", "comment": "// ", "template": '''// {header}

class Solution {{
public:
    // TODO
}};
'''},
    "java": {"ext": "java", "comment": "// ", "template": '''// {header}

class Solution {{
    // TODO
}}
'''},
}


def _valid_lang(lang: str) -> str:
    langs = load_config().get("languages", ["python"])
    default = load_config().get("default_language", "python")
    return lang if lang in langs and lang in _LANG_META else default


def _code_path_for(pid: int, title: str, lang: str) -> Path:
    safe = _SAFE_TITLE_RE.sub("_", title.strip())
    ext = _LANG_META[lang]["ext"]
    fname = f"{pid:03d}_{safe}.{ext}"
    return SOLUTIONS_DIR / lang / fname


def _migrate_legacy_code_file(entry: dict) -> None:
    """老数据 code_file 字段迁移到 code_files['python']。"""
    if entry.get("code_file") and not entry.get("code_files"):
        entry["code_files"] = {"python": entry["code_file"]}


def ensure_code_file(pid: int, lang: str = "python") -> str:
    """确保指定语言的代码文件存在；返回相对项目根的路径。"""
    lang = _valid_lang(lang)
    problems = load_problems()
    p = next((x for x in problems if x["id"] == pid), None)
    if not p:
        abort(404)
    path = _code_path_for(pid, p["title"], lang)
    if not path.exists():
        path.parent.mkdir(parents=True, exist_ok=True)
        header = f'{p["id"]}. {p["title"]} ({p["difficulty"]}) · {p["category"]}\nhttps://leetcode.cn/problems/{p["slug"]}/'
        content = _LANG_META[lang]["template"].format(header=header)
        path.write_text(content, encoding="utf-8")
    rel = path.relative_to(ROOT).as_posix()
    prog = load_progress()
    entry = prog.get(str(pid), _default_entry())
    _migrate_legacy_code_file(entry)
    if "code_files" not in entry:
        entry["code_files"] = {}
    entry["code_files"][lang] = rel
    # 兼容老字段：存默认语言的路径
    if lang == load_config().get("default_language", "python"):
        entry["code_file"] = rel
    prog[str(pid)] = entry
    save_progress(prog)
    return rel


def open_in_editor(path: Path) -> bool:
    try:
        subprocess.Popen(["open", str(path)])
        return True
    except Exception:
        return False


# ---------- 路由 ----------

@app.route("/")
def dashboard():
    return render_template("dashboard.html", d=build_dashboard())


@app.route("/problems")
def problems_page():
    prog = load_progress()
    cats = load_categories()
    for cat in cats:
        for p in cat["problems"]:
            entry = prog.get(str(p["id"]), _default_entry())
            p["status"] = entry.get("status", STATUS_TODO)
            p["note"] = entry.get("note", "")
            p["next_review"] = entry.get("next_review", "")
    return render_template("problems.html", categories=cats)


@app.route("/problem/<int:pid>")
def problem_detail(pid: int):
    problems = load_problems()
    p = next((x for x in problems if x["id"] == pid), None)
    if not p:
        abort(404)
    prog = load_progress()
    entry = prog.get(str(pid), _default_entry())
    return render_template("problem_detail.html", p=p, entry=entry)


@app.route("/cheatsheet")
def cheatsheet_page():
    """Cheatsheet 首页：按最近编辑倒序平铺每题的 cheatsheet。"""
    prog = load_progress()
    problems = load_problems()
    by_id = {p["id"]: p for p in problems}

    entries = []
    for pid_str, entry in prog.items():
        cs = (entry.get("cheatsheet") or "").strip()
        if not cs:
            continue
        pid = int(pid_str)
        p = by_id.get(pid)
        if not p:
            continue
        # 找最近一次跟这题相关的 history 时间戳；没有就用 last_done；再没有就 date.min
        last = entry.get("last_done", "") or ""
        for h in entry.get("history", []):
            if h.get("date", "") > last:
                last = h["date"]
        entries.append({
            "id": pid,
            "title": p["title"],
            "slug": p["slug"],
            "difficulty": p["difficulty"],
            "category": p["category"],
            "cheatsheet": cs,
            "last_edit": last or "0000-00-00",
        })
    entries.sort(key=lambda e: e["last_edit"], reverse=True)
    return render_template("cheatsheet.html", entries=entries)


@app.route("/cheatsheet/global")
def cheatsheet_global_page():
    """全局 Python 语法速查，独立子页。"""
    md = ""
    if CHEATSHEET_PATH.exists():
        md = CHEATSHEET_PATH.read_text(encoding="utf-8")
    return render_template("cheatsheet_global.html", markdown=md)


@app.route("/preview")
def preview_page():
    """明日 preview：只读展示明天预计要刷/复习的题。"""
    tomorrow = _today() + timedelta(days=1)
    d = build_preview(tomorrow)
    return render_template("preview.html", d=d)


@app.route("/calendar")
def calendar_page():
    """打卡日历：两种视图（条形图 = 最近 30 天；月历 = 当月）共用同一份数据。

    URL 参数 `month=YYYY-MM` 用于月历视图切月份；不传则显示当月。
    """
    prog = load_progress()
    today = _today()
    problems = load_problems()
    by_id = {p["id"]: p for p in problems}

    # ---- 收集完整 history: date -> {solve: [pid,...], review: [pid,...]} ----
    counted_actions = {"solve", "review"}
    per_day: dict[str, dict] = {}
    for pid_str, entry in prog.items():
        pid = int(pid_str)
        for h in entry.get("history", []):
            action = h.get("action")
            if action not in counted_actions:
                continue
            d_str = h.get("date", "")
            if not d_str:
                continue
            per_day.setdefault(d_str, {"solve": [], "review": []})
            per_day[d_str][action].append(pid)

    # ---- 找有数据的最早月份，用于月历视图的翻页边界 ----
    earliest_month = None
    if per_day:
        earliest_str = min(per_day.keys())
        earliest_date = date.fromisoformat(earliest_str)
        earliest_month = earliest_date.replace(day=1)

    def _day_detail(d_str: str) -> dict:
        raw = per_day.get(d_str, {"solve": [], "review": []})
        # 拼出题名列表用于 tooltip
        solve_titles = [f"#{pid} {by_id.get(pid,{}).get('title','?')}" for pid in raw["solve"]]
        review_titles = [f"#{pid} {by_id.get(pid,{}).get('title','?')}" for pid in raw["review"]]
        return {
            "solve": len(raw["solve"]),
            "review": len(raw["review"]),
            "total": len(raw["solve"]) + len(raw["review"]),
            "solve_titles": solve_titles,
            "review_titles": review_titles,
        }

    # ============================================================
    # 条形图视图：最近 30 天
    # ============================================================
    days = [today - timedelta(days=i) for i in range(29, -1, -1)]
    zh_weekdays = ["一", "二", "三", "四", "五", "六", "日"]
    series = []
    max_total_bar = 0
    total_all = 0
    for d in days:
        d_str = d.isoformat()
        detail = _day_detail(d_str)
        max_total_bar = max(max_total_bar, detail["total"])
        total_all += detail["total"]
        series.append({
            "date": d_str,
            "day": d.day,
            "month": d.month,
            "weekday": zh_weekdays[d.weekday()],
            "is_weekend": d.weekday() >= 5,
            "is_today": d == today,
            **detail,
        })

    # 连续天：从今天倒推
    streak = 0
    for i, day in enumerate(reversed(series)):
        if day["total"] > 0:
            streak += 1
        elif i == 0 and day["is_today"]:
            continue
        else:
            break

    active_days = sum(1 for d in series if d["total"] > 0)

    # ============================================================
    # 月历视图：目标月份（默认当月）
    # ============================================================
    month_param = request.args.get("month", "")
    try:
        year, mon = map(int, month_param.split("-"))
        target_month = date(year, mon, 1)
    except (ValueError, AttributeError):
        target_month = today.replace(day=1)

    # 生成本月所有日期 + weekday-of-week-start
    if target_month.month == 12:
        next_month = target_month.replace(year=target_month.year + 1, month=1)
    else:
        next_month = target_month.replace(month=target_month.month + 1)
    days_in_month = (next_month - target_month).days
    # 周一开始的 week，Monday = 0
    first_weekday = target_month.weekday()  # 0..6
    month_days = []
    for i in range(days_in_month):
        d = target_month + timedelta(days=i)
        d_str = d.isoformat()
        detail = _day_detail(d_str)
        month_days.append({
            "date": d_str,
            "day": d.day,
            "weekday": zh_weekdays[d.weekday()],
            "is_weekend": d.weekday() >= 5,
            "is_today": d == today,
            "is_future": d > today,
            **detail,
        })

    # 拼成 weeks（每周 7 格，前后不属于本月的留空）
    weeks: list[list] = []
    leading = [None] * first_weekday
    tail_needed = (7 - (len(leading) + len(month_days)) % 7) % 7
    trailing = [None] * tail_needed
    cells = leading + month_days + trailing
    for i in range(0, len(cells), 7):
        weeks.append(cells[i:i + 7])

    # 上/下月导航
    def _shift(dt: date, months: int) -> date:
        m = dt.month + months
        y = dt.year + (m - 1) // 12
        m = ((m - 1) % 12) + 1
        return date(y, m, 1)

    prev_month = _shift(target_month, -1)
    next_month_start = _shift(target_month, 1)
    can_prev = (earliest_month is None) or (prev_month >= earliest_month)
    # 未来月不给翻
    today_month = today.replace(day=1)
    can_next = next_month_start <= today_month

    return render_template(
        "calendar.html",
        # 条形图数据
        series=series,
        max_total=max_total_bar,
        total_all=total_all,
        streak=streak,
        active_days=active_days,
        # 月历数据
        target_month=target_month,
        weeks=weeks,
        month_label=f"{target_month.year} 年 {target_month.month} 月",
        prev_month_str=prev_month.strftime("%Y-%m") if can_prev else "",
        next_month_str=next_month_start.strftime("%Y-%m") if can_next else "",
    )


# ---------- API ----------

@app.post("/api/problem/<int:pid>/status")
def api_set_status(pid: int):
    """手动改状态 / 首次记录一道题。body: {"status": "forgot"|"shaky"|"solid"|"todo"|"archived"}"""
    body = request.get_json(force=True)
    status = body.get("status")
    if status not in {STATUS_TODO, STATUS_FORGOT, STATUS_SHAKY, STATUS_SOLID, STATUS_ARCHIVED}:
        return jsonify({"error": "bad status"}), 400
    prog = load_progress()
    entry = prog.get(str(pid), _default_entry())
    if status == STATUS_TODO:
        # 重置这道题
        entry = _default_entry()
    elif status == STATUS_ARCHIVED:
        entry["status"] = STATUS_ARCHIVED
        entry["next_review"] = ""
        entry["history"].append({"date": _today().isoformat(), "action": "archive"})
    else:
        entry = apply_first_solve(entry, status)
    prog[str(pid)] = entry
    save_progress(prog)
    return jsonify({"ok": True, "entry": entry})


@app.post("/api/problem/<int:pid>/review")
def api_review(pid: int):
    """复习打分。body: {"score": "easy"|"ok"|"hard"}"""
    body = request.get_json(force=True)
    score = body.get("score")
    if score not in {SCORE_EASY, SCORE_OK, SCORE_HARD}:
        return jsonify({"error": "bad score"}), 400
    prog = load_progress()
    entry = prog.get(str(pid), _default_entry())
    if entry.get("review_stage", -1) < 0:
        # 没进过复习队列，先当首刷（按 score 映射到 status）
        mapping = {SCORE_EASY: STATUS_SOLID, SCORE_OK: STATUS_SHAKY, SCORE_HARD: STATUS_FORGOT}
        entry = apply_first_solve(entry, mapping[score])
    else:
        entry = apply_review(entry, score)
    prog[str(pid)] = entry
    save_progress(prog)
    return jsonify({"ok": True, "entry": entry})


@app.post("/api/problem/<int:pid>/note")
def api_note(pid: int):
    body = request.get_json(force=True)
    note = body.get("note", "")
    prog = load_progress()
    entry = prog.get(str(pid), _default_entry())
    entry["note"] = note
    prog[str(pid)] = entry
    save_progress(prog)
    return jsonify({"ok": True})


@app.get("/api/problem/<int:pid>/note")
def api_note_get(pid: int):
    prog = load_progress()
    entry = prog.get(str(pid), _default_entry())
    return jsonify({"note": entry.get("note", "")})


@app.post("/api/problem/<int:pid>/cheatsheet")
def api_problem_cheatsheet(pid: int):
    body = request.get_json(force=True)
    md = body.get("cheatsheet", "")
    prog = load_progress()
    entry = prog.get(str(pid), _default_entry())
    entry["cheatsheet"] = md
    prog[str(pid)] = entry
    save_progress(prog)
    return jsonify({"ok": True})


@app.get("/api/problem/<int:pid>/cheatsheet")
def api_problem_cheatsheet_get(pid: int):
    prog = load_progress()
    entry = prog.get(str(pid), _default_entry())
    return jsonify({"cheatsheet": entry.get("cheatsheet", "")})


@app.post("/api/problem/<int:pid>/open-code")
def api_open_code(pid: int):
    body = request.get_json(silent=True) or {}
    lang = body.get("lang") or request.args.get("lang") or "python"
    rel = ensure_code_file(pid, lang)
    open_in_editor(ROOT / rel)
    return jsonify({"ok": True, "path": rel, "lang": lang})


@app.get("/api/problem/<int:pid>/code-files")
def api_code_files(pid: int):
    """返回这道题在各语言下已有代码文件的列表。"""
    prog = load_progress()
    entry = prog.get(str(pid), _default_entry())
    _migrate_legacy_code_file(entry)
    files = {}
    for lang, rel in (entry.get("code_files") or {}).items():
        # 校验文件是否还在磁盘
        if (ROOT / rel).exists():
            files[lang] = rel
    return jsonify({"files": files})


@app.post("/api/problem/<int:pid>/postpone")
def api_postpone(pid: int):
    """今天不想做，把 next_review 推到明天。"""
    prog = load_progress()
    entry = prog.get(str(pid))
    if not entry or not entry.get("next_review"):
        return jsonify({"error": "not in review queue"}), 400
    tomorrow = (_today() + timedelta(days=1)).isoformat()
    entry["next_review"] = tomorrow
    entry["history"].append({"date": _today().isoformat(), "action": "postpone"})
    prog[str(pid)] = entry
    save_progress(prog)
    return jsonify({"ok": True})


@app.post("/api/postpone-overdue")
def api_postpone_overdue():
    """把所有逾期（next_review <= today）的复习题一键推到明天。

    body 可选 {"only_overdue_days": N} —— 仅推迟逾期超过 N 天的（默认 0，即所有到期/逾期）
    返回 {"ok": True, "count": 推迟数}
    """
    body = request.get_json(silent=True) or {}
    threshold = int(body.get("only_overdue_days", 0))
    today = _today()
    tomorrow_iso = (today + timedelta(days=1)).isoformat()
    today_iso = today.isoformat()

    prog = load_progress()
    count = 0
    for pid_str, entry in prog.items():
        if entry.get("status") in (STATUS_ARCHIVED, STATUS_TODO):
            continue
        nr = entry.get("next_review", "")
        if not nr or nr > today_iso:
            continue
        try:
            overdue_days = (today - date.fromisoformat(nr)).days
        except ValueError:
            continue
        if overdue_days < threshold:
            continue
        entry["next_review"] = tomorrow_iso
        entry["history"].append({"date": today_iso, "action": "postpone-batch"})
        count += 1
    save_progress(prog)
    return jsonify({"ok": True, "count": count})


@app.post("/api/cheatsheet")
def api_cheatsheet_save():
    body = request.get_json(force=True)
    md = body.get("markdown", "")
    CHEATSHEET_PATH.write_text(md, encoding="utf-8")
    return jsonify({"ok": True})


@app.get("/api/dashboard")
def api_dashboard():
    return jsonify(build_dashboard())


@app.get("/api/checkin")
def api_checkin():
    """给打卡卡片用：dashboard 关键数字 + streak + finish + today 具体题。"""
    prog = load_progress()
    problems = load_problems()
    by_id = {p["id"]: p for p in problems}
    today = _today()
    today_str = today.isoformat()

    solved_ids, reviewed_ids = _done_today(prog)
    solved = [{
        "id": pid,
        "title": by_id.get(pid, {}).get("title", "?"),
        "difficulty": by_id.get(pid, {}).get("difficulty", "?"),
    } for pid in sorted(solved_ids)]
    reviewed = [{
        "id": pid,
        "title": by_id.get(pid, {}).get("title", "?"),
        "difficulty": by_id.get(pid, {}).get("difficulty", "?"),
    } for pid in sorted(reviewed_ids)]

    # streak: 从今天倒推，直到遇到"没打卡"的一天
    counted = {"solve", "review"}
    active_dates: set[str] = set()
    for pid, entry in prog.items():
        for h in entry.get("history", []):
            if h.get("action") in counted:
                active_dates.add(h.get("date", ""))
    streak = 0
    cursor = today
    while True:
        if cursor.isoformat() in active_dates:
            streak += 1
            cursor -= timedelta(days=1)
        else:
            # 今天还没打卡不算断
            if cursor == today:
                cursor -= timedelta(days=1)
                continue
            break

    # counts + finish 复用 dashboard 里的逻辑
    total = len(problems)
    counts = {
        STATUS_TODO: sum(1 for p in problems if _get_status(prog, p["id"]) == STATUS_TODO),
        STATUS_FORGOT: sum(1 for p in problems if _get_status(prog, p["id"]) == STATUS_FORGOT),
        STATUS_SHAKY: sum(1 for p in problems if _get_status(prog, p["id"]) == STATUS_SHAKY),
        STATUS_SOLID: sum(1 for p in problems if _get_status(prog, p["id"]) == STATUS_SOLID),
        STATUS_ARCHIVED: sum(1 for p in problems if _get_status(prog, p["id"]) == STATUS_ARCHIVED),
    }
    done_count = total - counts[STATUS_TODO]

    dq = load_config().get("daily_quota", {"weekday": 3, "weekend": 6})
    quota = dq["weekend"] if today.weekday() >= 5 else dq["weekday"]
    todo_pool_size = counts[STATUS_TODO]
    finish = _estimate_finish(
        todo_left=todo_pool_size,
        weekday_q=int(dq.get("weekday", 0)),
        weekend_q=int(dq.get("weekend", 0)),
        done_today=len(solved_ids),
        quota_today=quota,
    )

    # 今日活跃题目的难度分布（只算已 solve 或 reviewed）
    today_diff = {"简单": 0, "中等": 0, "困难": 0}
    for item in solved + reviewed:
        d_ = item.get("difficulty")
        if d_ in today_diff:
            today_diff[d_] += 1

    # 全部有笔记的题里各难度总数（可选，用于卡片下方展示"总体分布"）
    overall_diff = {"简单": 0, "中等": 0, "困难": 0}
    for p in problems:
        s = _get_status(prog, p["id"])
        if s == STATUS_TODO:
            continue
        d_ = p["difficulty"]
        if d_ in overall_diff:
            overall_diff[d_] += 1

    # 一句励志话（按 streak / 完成度 分段；中间态从随机池抽）
    BLURB_POOL = [
        "一天一点，不着急",
        "慢一点也是往前",
        "做了就是做了",
        "与 bug 和解的一天",
        "AC 一下，人生小胜",
        "稳住节奏，稳住手感",
        "保持出场率",
        "今天也守住了",
    ]
    if done_count == 0:
        blurb = "起点即出发"
    elif done_count == total:
        blurb = "刷完 hot100，稳。"
    elif streak >= 7:
        blurb = f"连续 {streak} 天，节奏很稳"
    elif streak >= 3:
        blurb = f"连续 {streak} 天，继续保持"
    elif len(solved_ids) + len(reviewed_ids) > 0:
        # 每次打开随机一句 —— 增加打开卡片的小惊喜
        import random
        blurb = random.choice(BLURB_POOL)
    else:
        blurb = "明天再来"

    return jsonify({
        "date": today_str,
        "is_weekend": today.weekday() >= 5,
        "weekday": ["一","二","三","四","五","六","日"][today.weekday()],
        "quota": quota,
        "solved": solved,
        "reviewed": reviewed,
        "streak": streak,
        "counts": counts,
        "total": total,
        "done_count": done_count,
        "todo_left": todo_pool_size,
        "finish": finish,
        "today_diff": today_diff,
        "overall_diff": overall_diff,
        "blurb": blurb,
    })


@app.post("/api/checkin/send-to-feishu")
def api_send_checkin_to_feishu():
    """接收前端 html2canvas 生成的 PNG，直接上传并发到飞书私聊。

    body: multipart/form-data，字段 `image` 是 PNG blob。
    需要 .env 里的 FEISHU_APP_ID + FEISHU_APP_SECRET + FEISHU_TARGET_CHAT。
    """
    app_id = os.environ.get("FEISHU_APP_ID", "")
    app_secret = os.environ.get("FEISHU_APP_SECRET", "")
    chat_id = os.environ.get("FEISHU_TARGET_CHAT", "")
    if not (app_id and app_secret and chat_id):
        return jsonify({"error": "飞书凭证未配置 (FEISHU_APP_ID / _SECRET / _TARGET_CHAT)"}), 400

    if "image" not in request.files:
        return jsonify({"error": "缺少 image 字段"}), 400
    upload = request.files["image"]

    # 复用 feishu_daily.py 里的 helper
    sys.path.insert(0, str(ROOT / "scripts"))
    try:
        from feishu_daily import _tenant_token, _upload_image, _send_image
    except Exception as e:
        return jsonify({"error": f"import failed: {e}"}), 500

    # 存到临时文件（_upload_image 需要 Path）
    import tempfile
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".png")
    try:
        upload.save(tmp.name)
        tmp.close()
        token = _tenant_token(app_id, app_secret)
        image_key = _upload_image(token, Path(tmp.name))
        _send_image(token, chat_id, image_key)
        return jsonify({"ok": True, "image_key": image_key})
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    finally:
        try:
            os.unlink(tmp.name)
        except Exception:
            pass


@app.get("/api/settings")
def api_settings_get():
    """返回可编辑的设置项。"""
    cfg = load_config()
    return jsonify({
        "daily_quota": cfg.get("daily_quota", {"weekday": 3, "weekend": 6}),
        "review_intervals_days": cfg.get("review_intervals_days", [1, 3, 7, 15, 30]),
        "overdue_alert_days": cfg.get("overdue_alert_days", 3),
        "day_boundary_hour": cfg.get("day_boundary_hour", 0),
    })


@app.post("/api/settings")
def api_settings_save():
    """把设置项写入 config.local.json（覆盖 config.json 里的默认值）。"""
    body = request.get_json(force=True)
    dq = body.get("daily_quota", {})
    intervals = body.get("review_intervals_days", [])
    overdue = body.get("overdue_alert_days", 3)
    boundary = body.get("day_boundary_hour", 0)

    if not isinstance(dq.get("weekday"), int) or not isinstance(dq.get("weekend"), int):
        return jsonify({"error": "daily_quota.weekday / weekend must be int"}), 400
    if dq["weekday"] < 0 or dq["weekend"] < 0 or dq["weekday"] > 30 or dq["weekend"] > 30:
        return jsonify({"error": "daily_quota out of range 0..30"}), 400
    if not isinstance(intervals, list) or not all(isinstance(x, int) and x > 0 for x in intervals):
        return jsonify({"error": "review_intervals_days must be list of positive ints"}), 400
    if len(intervals) < 1 or len(intervals) > 10:
        return jsonify({"error": "review_intervals_days must have 1..10 elements"}), 400
    if not isinstance(overdue, int) or overdue < 0:
        return jsonify({"error": "overdue_alert_days must be non-negative int"}), 400
    if not isinstance(boundary, (int, float)) or boundary < 0 or boundary > 6:
        return jsonify({"error": "day_boundary_hour must be within [0, 6]"}), 400

    local = load_json(CONFIG_LOCAL_PATH, {})
    local["daily_quota"] = {"weekday": dq["weekday"], "weekend": dq["weekend"]}
    local["review_intervals_days"] = intervals
    local["overdue_alert_days"] = overdue
    local["day_boundary_hour"] = boundary
    save_json(CONFIG_LOCAL_PATH, local)
    return jsonify({"ok": True})


# ---------- Entry ----------

if __name__ == "__main__":
    port = load_config().get("port", 5001)
    app.run(debug=True, port=port, host="127.0.0.1")
