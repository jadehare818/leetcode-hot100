#!/usr/bin/env python3
"""
每日推送今日看板到 Feishu 自建群机器人。

用法：
    python scripts/feishu_daily.py

需要在 config.json 里配置：
    "feishu_webhook": "https://open.feishu.cn/open-apis/bot/v2/hook/xxxx"

配 launchd 每天早 9 点自动跑（可选，见 README）。
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import json
import sys
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from app import build_dashboard, load_config  # noqa: E402


def format_message(d: dict) -> str:
    lines = [f"🔥 Hot 100 · {d['date']}"]
    lines.append(f"📊 进度：{d['total'] - d['counts']['todo']}/{d['total']}"
                 f"（🟢{d['counts']['solid']} 🟡{d['counts']['shaky']} 🔴{d['counts']['forgot']}）")
    lines.append(f"🎯 今日目标：{d['quota']} 题（{'周末' if d['is_weekend'] else '工作日'}）")
    lines.append("")

    if d["due_review"]:
        lines.append(f"🔁 复习（{len(d['due_review'])}）")
        for p in d["due_review"]:
            tag = "⚠️" if p.get("is_overdue") else "·"
            lines.append(f"  {tag} #{p['id']} {p['title']} [{p['difficulty']}]")
    else:
        lines.append("🔁 今天没有到期复习")
    lines.append("")

    if d["today_new"]:
        lines.append(f"🆕 新题（{len(d['today_new'])}）")
        for p in d["today_new"]:
            lines.append(f"  · #{p['id']} {p['title']} [{p['difficulty']}] · {p['category']}")
    else:
        lines.append("🆕 未刷池空了 or 今日新题配额已被复习占满")

    port = load_config().get("port", 5001)
    lines.append("")
    lines.append(f"🖥 http://localhost:{port}/")
    return "\n".join(lines)


def _sign(secret: str, ts: str) -> str:
    """飞书自定义机器人 HmacSHA256 签名。"""
    string_to_sign = f"{ts}\n{secret}"
    digest = hmac.new(
        string_to_sign.encode("utf-8"),
        digestmod=hashlib.sha256,
    ).digest()
    return base64.b64encode(digest).decode()


def send(webhook: str, secret: str, text: str) -> None:
    body = {"msg_type": "text", "content": {"text": text}}
    if secret:
        ts = str(int(time.time()))
        body["timestamp"] = ts
        body["sign"] = _sign(secret, ts)
    payload = json.dumps(body, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(
        webhook,
        data=payload,
        headers={"Content-Type": "application/json; charset=utf-8"},
    )
    with urllib.request.urlopen(req, timeout=15) as r:
        resp = r.read().decode("utf-8")
        print(f"[{r.status}] {resp}")


def main() -> int:
    cfg = load_config()
    webhook = cfg.get("feishu_webhook", "").strip()
    secret = cfg.get("feishu_secret", "").strip()
    text = format_message(build_dashboard())
    print(text)
    print("---")
    if not webhook:
        print("⚠️  config.json 里 feishu_webhook 为空，跳过推送。")
        return 0
    send(webhook, secret, text)
    return 0


if __name__ == "__main__":
    sys.exit(main())
