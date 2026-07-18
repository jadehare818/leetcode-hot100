#!/usr/bin/env python3
"""把 progress.local.json 中 next_review >= --from 的题目整体后移 --days 天。

用途：某一天完全没打卡时,不希望原本那天的复习堆到今天,而是把整个日程平移。

Example:
    python3 scripts/shift_from_date.py --from 2026-07-18 --days 1 --dry-run
    python3 scripts/shift_from_date.py --from 2026-07-18 --days 1
"""
from __future__ import annotations

import argparse
import json
import shutil
from collections import Counter
from datetime import date, datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PROGRESS_PATH = ROOT / "data" / "progress.local.json"

# 归档/未刷的题不进复习队列,不参与平移
SKIP_STATUS = {"archived", "todo"}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--from", dest="from_date", required=True,
                    help="起始日期(含),YYYY-MM-DD。next_review >= 该日期的题都会被平移")
    ap.add_argument("--days", type=int, default=1, help="平移多少天(默认 1)")
    ap.add_argument("--dry-run", action="store_true", help="只打印分布,不写入")
    ap.add_argument("--path", default=str(PROGRESS_PATH),
                    help=f"progress 文件路径(默认 {PROGRESS_PATH})")
    args = ap.parse_args()

    try:
        from_d = date.fromisoformat(args.from_date)
    except ValueError:
        print(f"[!] --from 格式错误: {args.from_date}")
        return 2
    if args.days <= 0:
        print("[!] --days 必须 > 0")
        return 2

    p = Path(args.path)
    if not p.exists():
        print(f"[!] 文件不存在: {p}")
        return 2

    prog = json.loads(p.read_text(encoding="utf-8"))

    before: Counter[str] = Counter()
    plan: list[tuple[str, str, str]] = []  # (pid, old, new)
    for pid, entry in prog.items():
        if entry.get("status") in SKIP_STATUS:
            continue
        nr = entry.get("next_review", "")
        if not nr:
            continue
        try:
            nr_d = date.fromisoformat(nr)
        except ValueError:
            continue
        if nr_d < from_d:
            continue
        before[nr] += 1
        new_nr = (nr_d + timedelta(days=args.days)).isoformat()
        plan.append((pid, nr, new_nr))

    if not plan:
        print(f"[i] 没有 next_review >= {from_d} 的题目,无需平移。")
        return 0

    print(f"[i] 将平移 {len(plan)} 道题,平移 +{args.days} 天:")
    for d_str in sorted(before):
        new_d = (date.fromisoformat(d_str) + timedelta(days=args.days)).isoformat()
        print(f"    {d_str} → {new_d} : {before[d_str]} 题")

    if args.dry_run:
        print("[i] --dry-run,不写入。")
        return 0

    # 备份
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    bak = p.with_suffix(p.suffix + f".bak-{stamp}")
    shutil.copy2(p, bak)
    print(f"[i] 备份 → {bak}")

    today_iso = date.today().isoformat()
    for pid, old, new in plan:
        entry = prog[pid]
        entry["next_review"] = new
        entry.setdefault("history", []).append({
            "date": today_iso,
            "action": "shift-forward",
            "from": old,
            "to": new,
            "shift_days": args.days,
        })

    p.write_text(json.dumps(prog, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"[✓] 已写入 {p}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
