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
import re
import unicodedata
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PROBLEMS_PATH = ROOT / "data" / "problems.json"
PROGRESS_LOCAL = ROOT / "data" / "progress.local.json"
PROGRESS_SEED = ROOT / "data" / "progress.json"
OUT_PATH = ROOT / "data" / "study-notes.md"

STATUS_LABEL = {
    "todo":     ("⚪", "未刷"),
    "forgot":   ("🔴", "卡住"),
    "shaky":    ("🟡", "磕绊"),
    "solid":    ("🟢", "很稳"),
    "archived": ("📦", "归档"),
}
DIFF_ICON = {
    "简单": "🟢",
    "中等": "🟡",
    "困难": "🔴",
}


def load_progress() -> dict:
    src = PROGRESS_LOCAL if PROGRESS_LOCAL.exists() else PROGRESS_SEED
    if not src.exists():
        return {}
    text = src.read_text(encoding="utf-8").strip()
    return json.loads(text) if text else {}


def load_problems() -> dict:
    """返回 {pid: {title, slug, difficulty, category, order}}. order = original hot100 order."""
    raw = json.loads(PROBLEMS_PATH.read_text(encoding="utf-8"))
    out = {}
    order = 0
    for cat in raw["categories"]:
        for p in cat["problems"]:
            out[p["id"]] = {
                "title": p["title"],
                "slug": p["slug"],
                "difficulty": p["difficulty"],
                "category": cat["name"],
                "order": order,
            }
            order += 1
    return out


def load_categories() -> list[str]:
    """按官方分类顺序返回 category 名称列表。"""
    raw = json.loads(PROBLEMS_PATH.read_text(encoding="utf-8"))
    return [c["name"] for c in raw["categories"]]


def _last_edit(entry: dict) -> str:
    latest = entry.get("last_done", "") or ""
    for h in entry.get("history", []):
        d = h.get("date", "") or ""
        if d > latest:
            latest = d
    return latest or "0000-00-00"


def _slugify_anchor(pid: int, title: str) -> str:
    """GitHub 的 markdown TOC 锚点规则：小写、汉字保留、空格换 `-`、
    去掉大部分标点。这里我们只需生成 `1-两数之和` 这种。"""
    text = f"{pid}-{title}"
    text = text.lower()
    text = re.sub(r"[\s]+", "-", text)
    text = re.sub(r"[^\w一-鿿\-]", "", text)  # 保留中文、字母数字下划线
    return text


def _detect_lang(text: str) -> str:
    """启发式：如果里面有 def / class Solution / print / import → python；
    package / func → go；#include → cpp；public class → java。"""
    t = text
    if re.search(r"\bpackage\s+\w+|\bfunc\s+\w+", t):
        return "go"
    if re.search(r"#include\s*<", t):
        return "cpp"
    if re.search(r"\bpublic\s+(class|static)", t):
        return "java"
    # default: python (most cheatsheets we see are python-flavored)
    return "python"


def build_md(prog: dict, probs: dict) -> str:
    entries = []
    for pid_str, entry in prog.items():
        note = (entry.get("note") or "").strip()
        cs = (entry.get("cheatsheet") or "").strip()
        if not note and not cs:
            continue
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
            "order": p["order"],
            "status": entry.get("status", "todo"),
            "note": note,
            "cheatsheet": cs,
            "last_edit": _last_edit(entry),
            "review_stage": entry.get("review_stage", -1),
            "next_review": entry.get("next_review", ""),
        })

    # ---- header + summary ----
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    total_all = len(probs)
    total_with_notes = len(entries)
    solid = sum(1 for e in prog.values() if e.get("status") == "solid")
    shaky = sum(1 for e in prog.values() if e.get("status") == "shaky")
    forgot = sum(1 for e in prog.values() if e.get("status") == "forgot")
    todo = sum(1 for e in prog.values() if e.get("status") == "todo")
    archived = sum(1 for e in prog.values() if e.get("status") == "archived")
    # 有可能没有任何 status 记录（seed 空）→ todo 兜底
    if solid + shaky + forgot + archived == 0 and not prog:
        todo = total_all
    else:
        todo = max(0, total_all - solid - shaky - forgot - archived)

    # progress bar (10 blocks)
    done = solid + shaky + forgot + archived
    filled = int(round(done / total_all * 10)) if total_all else 0
    bar = "█" * filled + "░" * (10 - filled)
    pct = int(round(done / total_all * 100)) if total_all else 0

    # difficulty split among noted entries
    diff_easy = sum(1 for e in entries if e["difficulty"] == "简单")
    diff_med = sum(1 for e in entries if e["difficulty"] == "中等")
    diff_hard = sum(1 for e in entries if e["difficulty"] == "困难")

    lines: list[str] = []
    lines.append("# 📓 刷题笔记")
    lines.append("")
    lines.append(f"<sub>自动生成于 **{now}** · 记录 **{total_with_notes} / {total_all}** 道</sub>")
    lines.append("")
    lines.append(f"**进度**  `{bar}`  {pct}% ({done}/{total_all})")
    lines.append("")
    lines.append("| 🟢 很稳 | 🟡 磕绊 | 🔴 卡住 | 📦 归档 | ⚪ 未刷 |")
    lines.append("| :-: | :-: | :-: | :-: | :-: |")
    lines.append(f"| **{solid}** | **{shaky}** | **{forgot}** | **{archived}** | **{todo}** |")
    lines.append("")
    lines.append(f"**已记笔记的难度分布** · 🟢 简单 {diff_easy} · 🟡 中等 {diff_med} · 🔴 困难 {diff_hard}")
    lines.append("")
    lines.append("---")
    lines.append("")

    if not entries:
        lines.append("_还没有任何笔记。去看板 / 题库写第一份吧。_")
        lines.append("")
        return "\n".join(lines)

    # ---- TOC by category (only categories that have noted entries) ----
    categories = load_categories()
    entries_by_cat: dict[str, list[dict]] = {}
    for e in entries:
        entries_by_cat.setdefault(e["category"], []).append(e)
    for lst in entries_by_cat.values():
        lst.sort(key=lambda e: e["order"])

    lines.append("## 📚 目录")
    lines.append("")
    for cat in categories:
        lst = entries_by_cat.get(cat)
        if not lst:
            continue
        lines.append(f"### 🔖 {cat} · {len(lst)}")
        lines.append("")
        for e in lst:
            emoji, _ = STATUS_LABEL.get(e["status"], ("⚪", ""))
            anchor = _slugify_anchor(e["id"], e["title"])
            lines.append(f"- [`#{e['id']}`](#{anchor}) · {e['title']} · {emoji}")
        lines.append("")

    lines.append("---")
    lines.append("")

    # ---- entries by category ----
    for cat in categories:
        lst = entries_by_cat.get(cat)
        if not lst:
            continue
        lines.append(f"# 🔖 {cat}")
        lines.append("")
        for e in lst:
            lc_url = f"https://leetcode.cn/problems/{e['slug']}/"
            se, sn = STATUS_LABEL.get(e["status"], ("⚪", e["status"]))
            de = DIFF_ICON.get(e["difficulty"], "·")
            stage = e["review_stage"]
            stage_txt = f"档位 {stage}" if stage >= 0 else "尚未进复习队列"
            next_txt = e["next_review"] or "—"

            lines.append(f"## `#{e['id']}` {e['title']}")
            lines.append("")
            lines.append("| | |")
            lines.append("|---|---|")
            lines.append(f"| 分类 | {cat} |")
            lines.append(f"| 难度 | {de} {e['difficulty']} |")
            lines.append(f"| 状态 | {se} {sn} · {stage_txt} · 下次复习 {next_txt} |")
            lines.append(f"| 最近编辑 | {e['last_edit']} · [🔗 力扣]({lc_url}) |")
            lines.append("")

            if e["note"]:
                lines.append("**💡 思路**")
                lines.append("")
                for ln in e["note"].splitlines() or [e["note"]]:
                    lines.append(f"> {ln}")
                lines.append("")

            if e["cheatsheet"]:
                lines.append("**📝 Cheatsheet**")
                lines.append("")
                # 如果原文已经含代码围栏，就原样输出；否则用启发式判定语言包一层
                if "```" in e["cheatsheet"]:
                    lines.append(e["cheatsheet"])
                else:
                    lang = _detect_lang(e["cheatsheet"])
                    lines.append(f"```{lang}")
                    lines.append(e["cheatsheet"])
                    lines.append("```")
                lines.append("")

            lines.append("<sup>[↑ 回目录](#-目录)</sup>")
            lines.append("")
            lines.append("---")
            lines.append("")

    return "\n".join(lines)


def main() -> int:
    prog = load_progress()
    probs = load_problems()
    md = build_md(prog, probs)
    OUT_PATH.write_text(md, encoding="utf-8")
    entry_count = md.count("\n## `#")
    print(f"[export_notes] wrote {OUT_PATH.relative_to(ROOT)} · {entry_count} problems")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
