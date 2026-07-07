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


def _done_today(prog: dict) -> set[int]:
    """今天真正做完题的 pid 集合。

    只算 action == 'solve' | 'review'。推迟（postpone / postpone-batch）
    和归档（archive）不算完成 —— 它们是维护动作，不是刷题。
    """
    today = _today().isoformat()
    counted_actions = {"solve", "review"}
    done = set()
    for pid, entry in prog.items():
        for h in entry.get("history", []):
            if h.get("date") == today and h.get("action") in counted_actions:
                done.add(int(pid))
                break
    return done


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
    done_today_ids = _done_today(prog)

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

    # 未刷池按分类原顺序排；今日新题配额只由"今天已刷"扣减 —— 复习不吃新题配额
    quota = _daily_quota()
    new_slots = max(0, quota - len(done_today_ids))

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
        done_today=len(done_today_ids),
        quota_today=quota,
    )

    return {
        "date": today,
        "is_weekend": _today().weekday() >= 5,
        "quota": quota,
        "done_today": sorted(done_today_ids),
        "due_review": due_review,
        "today_new": today_new,
        "extras_pool": extras_pool,
        "todo_left": len(todo_pool),
        "counts": counts,
        "total": total,
        "finish": finish,
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
