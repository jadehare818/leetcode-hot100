"""
每日推送到飞书。默认发两条：
    1. 文字：今日复习列表 + 今日新题列表（空节隐藏）
    2. Calendar 卡片图片（16:9 · 柱状图 + 月历）

也可以只发一条（--only=text 或 --only=image）。
launchd 每天早 09:00 自动跑，见 README。
"""
from __future__ import annotations

import argparse
import base64
import hashlib
import hmac
import json
import os
import sys
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from app import build_dashboard, load_config  # noqa: E402


# ============================================================
# 文字消息
# ============================================================

_ZH_WEEKDAY = ["一", "二", "三", "四", "五", "六", "日"]


def format_daily_text(d: dict) -> str:
    """
    📓 Hot 100 · 2026-07-11 (周六)

    🔁 今日复习（2）
      · #49 字母异位词分组 · 中等
      · #76 最小覆盖子串 · 困难

    🆕 今日新题（3）
      · #160 相交链表 · 简单
      · #11 盛最多水的容器 · 中等
      · #42 接雨水 · 困难

    空节隐藏；两个都空时返回 "今天没题，收工"。
    """
    from datetime import date
    dt = date.fromisoformat(d["date"])
    wd = _ZH_WEEKDAY[dt.weekday()]

    lines = [f"📓 Hot 100 · {d['date']} (周{wd})"]

    reviews = d.get("due_review") or []
    news = d.get("today_new") or []

    if not reviews and not news:
        lines.append("")
        lines.append("今天没题，收工 🎉")
        return "\n".join(lines)

    if reviews:
        lines.append("")
        lines.append(f"🔁 今日复习（{len(reviews)}）")
        for p in reviews:
            tag = " ⚠️" if p.get("is_overdue") else ""
            lines.append(f"  · #{p['id']} {p['title']} · {p['difficulty']}{tag}")

    if news:
        lines.append("")
        lines.append(f"🆕 今日新题（{len(news)}）")
        for p in news:
            lines.append(f"  · #{p['id']} {p['title']} · {p['difficulty']}")

    return "\n".join(lines)


# ============================================================
# 老 webhook（保留作为兜底路径）
# ============================================================

def _sign(secret: str, ts: str) -> str:
    string_to_sign = f"{ts}\n{secret}"
    digest = hmac.new(string_to_sign.encode("utf-8"), digestmod=hashlib.sha256).digest()
    return base64.b64encode(digest).decode()


def send_webhook(webhook: str, secret: str, text: str) -> None:
    body = {"msg_type": "text", "content": {"text": text}}
    if secret:
        ts = str(int(time.time()))
        body["timestamp"] = ts
        body["sign"] = _sign(secret, ts)
    payload = json.dumps(body, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(
        webhook, data=payload,
        headers={"Content-Type": "application/json; charset=utf-8"},
    )
    with urllib.request.urlopen(req, timeout=15) as r:
        print(f"[webhook {r.status}] {r.read().decode()}")


# ============================================================
# 飞书 App API（自建应用路径）
# ============================================================

def _tenant_token(app_id: str, app_secret: str) -> str:
    body = json.dumps({"app_id": app_id, "app_secret": app_secret}).encode("utf-8")
    req = urllib.request.Request(
        "https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal",
        data=body,
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=15) as r:
        d = json.load(r)
    tok = d.get("tenant_access_token")
    if not tok:
        raise RuntimeError(f"failed to get tenant token: {d}")
    return tok


def _upload_image(token: str, png_path: Path) -> str:
    import mimetypes
    boundary = "----hot100boundary" + hashlib.md5(os.urandom(16)).hexdigest()[:8]
    with png_path.open("rb") as f:
        img_bytes = f.read()
    mime = mimetypes.guess_type(str(png_path))[0] or "image/png"
    body = (
        f"--{boundary}\r\n"
        f'Content-Disposition: form-data; name="image_type"\r\n\r\n'
        f"message\r\n"
        f"--{boundary}\r\n"
        f'Content-Disposition: form-data; name="image"; filename="{png_path.name}"\r\n'
        f"Content-Type: {mime}\r\n\r\n"
    ).encode("utf-8") + img_bytes + f"\r\n--{boundary}--\r\n".encode("utf-8")
    req = urllib.request.Request(
        "https://open.feishu.cn/open-apis/im/v1/images",
        data=body,
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": f"multipart/form-data; boundary={boundary}",
        },
    )
    with urllib.request.urlopen(req, timeout=30) as r:
        d = json.load(r)
    if d.get("code") != 0:
        raise RuntimeError(f"upload failed: {d}")
    return d["data"]["image_key"]


def _receive_id_type(receive_id: str) -> str:
    """根据前缀选 receive_id_type。"""
    if receive_id.startswith("oc_"):
        return "chat_id"
    if receive_id.startswith("ou_"):
        return "open_id"
    if receive_id.startswith("on_"):
        return "union_id"
    if "@" in receive_id:
        return "email"
    return "user_id"


def _send_message(token: str, receive_id: str, msg_type: str, content: dict) -> None:
    rtype = _receive_id_type(receive_id)
    body = json.dumps({
        "receive_id": receive_id,
        "msg_type": msg_type,
        "content": json.dumps(content, ensure_ascii=False),
    }).encode("utf-8")
    req = urllib.request.Request(
        f"https://open.feishu.cn/open-apis/im/v1/messages?receive_id_type={rtype}",
        data=body,
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        },
    )
    with urllib.request.urlopen(req, timeout=15) as r:
        d = json.load(r)
    if d.get("code") != 0:
        raise RuntimeError(f"send {msg_type} failed: {d}")
    print(f"[{msg_type} sent · via {rtype}] message_id={d.get('data', {}).get('message_id', '?')}")


def _send_text(token: str, receive_id: str, text: str) -> None:
    _send_message(token, receive_id, "text", {"text": text})


def _send_image(token: str, receive_id: str, image_key: str) -> None:
    _send_message(token, receive_id, "image", {"image_key": image_key})


# ============================================================
# 高层路径
# ============================================================

def send_text_via_app(text: str) -> bool:
    """文字路径。"""
    app_id = os.environ.get("FEISHU_APP_ID", "").strip()
    app_secret = os.environ.get("FEISHU_APP_SECRET", "").strip()
    receive_id = os.environ.get("FEISHU_TARGET_CHAT", "").strip()
    if not (app_id and app_secret and receive_id):
        return False
    token = _tenant_token(app_id, app_secret)
    _send_text(token, receive_id, text)
    return True


def send_card_image_via_app(which: str) -> bool:
    """图片路径。which ∈ {'checkin', 'calendar'}。"""
    app_id = os.environ.get("FEISHU_APP_ID", "").strip()
    app_secret = os.environ.get("FEISHU_APP_SECRET", "").strip()
    receive_id = os.environ.get("FEISHU_TARGET_CHAT", "").strip()
    if not (app_id and app_secret and receive_id):
        return False

    # 生成 PNG（复用 render_checkin.py 里的通用 render）
    from scripts.render_checkin import render, DEFAULT_OUT  # noqa: E402
    out = DEFAULT_OUT.with_name(f"hot100-{which}.png")
    print(f"[{which}] rendering PNG via playwright…")
    png = render(out, which=which)

    print(f"[{which}] getting tenant token…")
    token = _tenant_token(app_id, app_secret)
    print(f"[{which}] uploading PNG…")
    image_key = _upload_image(token, png)
    print(f"[{which}] image_key={image_key}, sending…")
    _send_image(token, receive_id, image_key)
    return True


# ============================================================
# Entry
# ============================================================

def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--only", choices=["text", "checkin", "calendar"],
                        help="只发某一条；不给就发默认组合（text + calendar）")
    args = parser.parse_args()

    d = build_dashboard()
    text = format_daily_text(d)

    tasks = [args.only] if args.only else ["text", "calendar"]

    all_ok = True
    for kind in tasks:
        try:
            if kind == "text":
                ok = send_text_via_app(text)
                if not ok:
                    # 兜底：老 webhook
                    cfg = load_config()
                    if cfg.get("feishu_webhook"):
                        send_webhook(cfg["feishu_webhook"], cfg.get("feishu_secret", ""), text)
                    else:
                        print(text)
                        print("---\n⚠️  没配飞书凭证，仅打印")
                        all_ok = False
            elif kind in ("checkin", "calendar"):
                ok = send_card_image_via_app(kind)
                if not ok:
                    print(f"⚠️  没配飞书 App 凭证，无法发 {kind} 卡片")
                    all_ok = False
        except Exception as e:
            print(f"[{kind} failed] {e}", file=sys.stderr)
            all_ok = False

    return 0 if all_ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
