"""
每日推送打卡卡片到飞书。

三条路径，按顺序 fallback：
    1. 图片模式（需要 FEISHU_APP_ID + APP_SECRET + TARGET_CHAT）：
       playwright 生成 PNG → 上传到飞书 → 发 image 消息给指定 chat
    2. Webhook 文本模式（老路径，需要 FEISHU_WEBHOOK + secret）：
       格式化文本消息 → 走自定义机器人 webhook
    3. 打印到 stdout（凭证都没配时的最终 fallback）

launchd 每天早 09:00 自动跑，见 README。
"""
from __future__ import annotations

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
# 文本消息（webhook 路径）
# ============================================================

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
    lines.append("")
    lines.append("🖥 http://localhost:5001/")
    return "\n".join(lines)


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
# 图片消息（自建应用路径）
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
    """multipart 上传，飞书返回 image_key。"""
    boundary = f"----hot100_{int(time.time())}"
    data = png_path.read_bytes()
    body_parts = []
    body_parts.append(f"--{boundary}".encode())
    body_parts.append(b'Content-Disposition: form-data; name="image_type"')
    body_parts.append(b"")
    body_parts.append(b"message")
    body_parts.append(f"--{boundary}".encode())
    body_parts.append(
        f'Content-Disposition: form-data; name="image"; filename="{png_path.name}"'.encode()
    )
    body_parts.append(b"Content-Type: image/png")
    body_parts.append(b"")
    body_parts.append(data)
    body_parts.append(f"--{boundary}--".encode())
    body_parts.append(b"")
    body = b"\r\n".join(body_parts)

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


def _send_image(token: str, chat_id: str, image_key: str) -> None:
    body = json.dumps({
        "receive_id": chat_id,
        "msg_type": "image",
        "content": json.dumps({"image_key": image_key}),
    }).encode("utf-8")
    req = urllib.request.Request(
        "https://open.feishu.cn/open-apis/im/v1/messages?receive_id_type=chat_id",
        data=body,
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        },
    )
    with urllib.request.urlopen(req, timeout=15) as r:
        d = json.load(r)
    if d.get("code") != 0:
        raise RuntimeError(f"send image failed: {d}")
    print(f"[image sent] message_id={d.get('data', {}).get('message_id', '?')}")


def send_image_via_app() -> bool:
    """图片路径：需要 APP_ID + APP_SECRET + TARGET_CHAT + playwright。"""
    app_id = os.environ.get("FEISHU_APP_ID", "").strip()
    app_secret = os.environ.get("FEISHU_APP_SECRET", "").strip()
    chat_id = os.environ.get("FEISHU_TARGET_CHAT", "").strip()
    if not (app_id and app_secret and chat_id):
        return False

    # 生成 PNG
    from scripts.render_checkin import render, DEFAULT_OUT  # noqa: E402
    print("[image] rendering PNG via playwright…")
    png = render(DEFAULT_OUT)

    print("[image] getting tenant token…")
    token = _tenant_token(app_id, app_secret)
    print("[image] uploading PNG…")
    image_key = _upload_image(token, png)
    print(f"[image] image_key={image_key}, sending…")
    _send_image(token, chat_id, image_key)
    return True


# ============================================================
# Entry
# ============================================================

def main() -> int:
    cfg = load_config()

    # 1. 优先图片
    try:
        if send_image_via_app():
            return 0
    except Exception as e:
        print(f"[image path failed] {e}", file=sys.stderr)

    # 2. Fallback 到 webhook 文本
    webhook = cfg.get("feishu_webhook", "").strip()
    secret = cfg.get("feishu_secret", "").strip()
    text = format_message(build_dashboard())
    if webhook:
        try:
            send_webhook(webhook, secret, text)
            return 0
        except Exception as e:
            print(f"[webhook failed] {e}", file=sys.stderr)

    # 3. 只 print
    print(text)
    print("---")
    print("⚠️  没有可用的推送通道，仅打印。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
