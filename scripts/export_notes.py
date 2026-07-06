#!/usr/bin/env python3
"""
Export personal cheatsheets/notes to a human-readable markdown file.

用法：
    python scripts/export_notes.py

读取:
    data/progress.local.json  (fallback: data/progress.json)
    data/problems.json
输出:
    data/study-notes.md

被 sync_personal_data.sh 调用；也可以手动跑。

生成的 md 会跟着 progress.local.json 一起 push 到 data-<user> 分支，
方便在手机上用 Working Copy / GitHub app 直接看渲染好的笔记。
"""
from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PROBLEMS_PATH = ROOT / "data" / "problems.json"
PROGRESS_LOCAL = ROOT / "data" / "progress.local.json"
PROGRESS_SEED = ROOT / "data" / "progress.json"
OUT_PATH = ROOT / "data" / "study-notes.md"

STATUS_ZH = {
    "todo": "未刷",
    "forgot": "卡住",
    "shaky": "磕绊",
    "solid": "很稳",
    "archived": "归档",
}


def load_progress() -> dict:
    src = PROGRESS_LOCAL if PROGRESS_LOCAL.exists() else PROGRESS_SEED
    if not src.exists():
        return {}
    text = src.read_text(encoding="utf-8").strip()
    return json.loads(text) if text else {}


def load_problems() -> dict:
    """返回 {pid: {title, slug, difficulty, category}}."""
    raw = json.loads(PROBLEMS_PATH.read_text(encoding="utf-8"))
    out = {}
    for cat in raw["categories"]:
        for p in cat["problems"]:
            out[p["id"]] = {
                "title": p["title"],
                "slug": p["slug"],
                "difficulty": p["difficulty"],
                "category": cat["name"],
            }
    return out


def _last_edit(entry: dict) -> str:
    """Latest date across last_done + all history entries."""
    latest = entry.get("last_done", "") or ""
    for h in entry.get("history", []):
        d = h.get("date", "") or ""
        if d > latest:
            latest = d
    return latest or "0000-00-00"


def build_md(prog: dict, probs: dict) -> str:
    entries = []
    for pid_str, entry in prog.items():
        note = (entry.get("note") or "").strip()
        cs = (entry.get("cheatsheet") or "").strip()
        if not note and not cs:
            continue  # skip empty
        pid = int(pid_str)
        p = probs.get(pid)
        if not p:
            continue
        entries.append({
            "id": pid,
            "title": p["title"],
            "slug": p["slug"],
            "difficulty": p["difficulty"],
            "category": p["category"],
            "status": entry.get("status", "todo"),
            "note": note,
            "cheatsheet": cs,
            "last_edit": _last_edit(entry),
            "review_stage": entry.get("review_stage", -1),
            "next_review": entry.get("next_review", ""),
        })
    entries.sort(key=lambda e: e["last_edit"], reverse=True)

    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    lines = [
        "# 刷题笔记",
        "",
        f"由 [`export_notes.py`](../scripts/export_notes.py) 于 **{now}** 自动生成 · 按最近编辑倒序。",
        "",
        f"共 **{len(entries)}** 道题有笔记。",
        "",
        "---",
        "",
    ]

    for e in entries:
        lc_url = f"https://leetcode.cn/problems/{e['slug']}/"
        status_zh = STATUS_ZH.get(e["status"], e["status"])
        lines.append(f"## #{e['id']} [{e['title']}]({lc_url})")
        lines.append("")
        meta_bits = [
            f"**{e['category']}**",
            e["difficulty"],
            f"状态：{status_zh}",
        ]
        if e["review_stage"] >= 0:
            meta_bits.append(f"档位：{e['review_stage']}")
        if e["next_review"]:
            meta_bits.append(f"下次复习：{e['next_review']}")
        meta_bits.append(f"最近编辑：{e['last_edit']}")
        lines.append(" · ".join(meta_bits))
        lines.append("")

        if e["note"]:
            lines.append("### 思路")
            lines.append("")
            lines.append("> " + e["note"].replace("\n", "\n> "))
            lines.append("")

        if e["cheatsheet"]:
            lines.append("### Cheatsheet")
            lines.append("")
            lines.append(e["cheatsheet"])
            lines.append("")

        lines.append("---")
        lines.append("")

    if not entries:
        lines.append("_还没有任何笔记。去看板 / 题库写第一份吧。_")
        lines.append("")

    return "\n".join(lines)


def main() -> int:
    prog = load_progress()
    probs = load_problems()
    md = build_md(prog, probs)
    OUT_PATH.write_text(md, encoding="utf-8")
    entry_count = md.count("\n## #")
    print(f"[export_notes] wrote {OUT_PATH.relative_to(ROOT)} · {entry_count} problems")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
