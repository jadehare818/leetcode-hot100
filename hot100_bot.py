"""
Hot 100 · 飞书 Bot（WebSocket 长连接）

架构参考 baguwen：lark-oapi 长连接 → 不需要公网穿透。

命令（中英双语）：
  /help  帮助          → 命令清单卡片
  /today 今日          → 今日复习 + 新题，每题带打分按钮
  /preview [N] 预告[N]  → N 天后预告（默认 N=1 明天，最大 30）
  /checkin 打卡        → 打卡卡片图片
  /calendar 节奏       → Calendar 卡片图片
  /cancel              → 退出当前多轮

启动：
  .venv/bin/python hot100_bot.py

依赖 .env（同项目根）：
  FEISHU_APP_ID=cli_xxx
  FEISHU_APP_SECRET=xxx
  HOT100_API=http://127.0.0.1:5001   # 可选，默认这个
"""
from __future__ import annotations

import json
import os
import re
import sys
import time
import traceback
import urllib.error
import urllib.request
from pathlib import Path

import lark_oapi as lark
from lark_oapi.api.im.v1 import (
    CreateMessageRequest,
    CreateMessageRequestBody,
    P2ImMessageReceiveV1,
)
from lark_oapi.event.callback.model.p2_card_action_trigger import (
    P2CardActionTrigger,
    P2CardActionTriggerResponse,
)


ROOT = Path(__file__).resolve().parent
ENV_PATH = ROOT / ".env"


# ---------- .env ----------
def _load_env():
    if not ENV_PATH.exists():
        return
    for line in ENV_PATH.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, _, v = line.partition("=")
        k, v = k.strip(), v.strip()
        if len(v) >= 2 and v[0] == v[-1] and v[0] in ("'", '"'):
            v = v[1:-1]
        os.environ.setdefault(k, v)


_load_env()

APP_ID = os.environ.get("FEISHU_APP_ID", "")
APP_SECRET = os.environ.get("FEISHU_APP_SECRET", "")
API_BASE = os.environ.get("HOT100_API", "http://127.0.0.1:5001")

if not APP_ID or not APP_SECRET:
    sys.stderr.write("!! 缺少 FEISHU_APP_ID / FEISHU_APP_SECRET，填 .env\n")
    sys.exit(1)


# ==========================================================================
# 后端 API client
# ==========================================================================
def api_get(path: str) -> dict:
    with urllib.request.urlopen(f"{API_BASE}{path}", timeout=10) as r:
        return json.loads(r.read().decode("utf-8"))


def api_call(method: str, path: str, body: dict | None = None) -> tuple[int, dict]:
    data = None
    headers = {}
    if body is not None:
        data = json.dumps(body).encode("utf-8")
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request(f"{API_BASE}{path}", method=method, data=data, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=15) as r:
            return r.status, json.loads(r.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        try:
            return e.code, json.loads(e.read().decode("utf-8"))
        except Exception:
            return e.code, {"error": str(e)}


# ==========================================================================
# 飞书客户端 & 消息发送
# ==========================================================================
client = lark.Client.builder() \
    .app_id(APP_ID) \
    .app_secret(APP_SECRET) \
    .log_level(lark.LogLevel.INFO) \
    .build()


def _send(chat_id: str, msg_type: str, content: dict) -> None:
    try:
        req = CreateMessageRequest.builder() \
            .receive_id_type("chat_id") \
            .request_body(
                CreateMessageRequestBody.builder()
                    .receive_id(chat_id)
                    .msg_type(msg_type)
                    .content(json.dumps(content, ensure_ascii=False))
                    .build()
            ).build()
        resp = client.im.v1.message.create(req)
        if not resp.success():
            print(f"!! send failed: code={resp.code} msg={resp.msg}", flush=True)
        else:
            print(f"[SEND] {msg_type} -> chat={chat_id} ok", flush=True)
    except Exception as e:
        print(f"!! send exception: {e!r}", flush=True)
        traceback.print_exc()


def send_text(chat_id: str, text: str) -> None:
    _send(chat_id, "text", {"text": text})


def send_card(chat_id: str, card: dict) -> None:
    _send(chat_id, "interactive", card)


# ==========================================================================
# 卡片 builder
# ==========================================================================
def card_menu(title: str, subtitle: str | None = None, buttons: list[list[dict]] | None = None,
              body: list[dict] | None = None, theme: str = "blue") -> dict:
    elements = []
    if subtitle:
        elements.append({"tag": "markdown", "content": subtitle})
    if body:
        elements.extend(body)
    if buttons:
        for row in buttons:
            actions = []
            for b in row:
                actions.append({
                    "tag": "button",
                    "text": {"tag": "plain_text", "content": b["text"]},
                    "type": b.get("type", "default"),
                    "value": b.get("value", {}),
                })
            elements.append({"tag": "action", "actions": actions})
    return {
        "config": {"wide_screen_mode": True, "update_multi": True},
        "header": {
            "title": {"tag": "plain_text", "content": title},
            "template": theme,
        },
        "elements": elements,
    }


DIFF_ICON = {"简单": "🟢", "中等": "🟡", "困难": "🔴"}


# ==========================================================================
# 命令实现
# ==========================================================================
HELP_TEXT = """**Hot 100 Bot 命令**

- `/today` 或 `今日` — 今日复习 + 新题（带打分按钮）
- `/preview [N]` 或 `预告 [N]` — N 天后预告（默认 1 天）
- `/checkin` 或 `打卡` — 生成打卡卡片
- `/calendar` 或 `节奏` — 生成 Calendar 卡片
- `/help` 或 `帮助` — 显示这条
- `/cancel` — 退出当前操作
"""


def cmd_help(chat_id: str) -> None:
    send_card(chat_id, card_menu(
        "📓 Hot 100 · Journal Bot",
        HELP_TEXT,
        buttons=[
            [
                {"text": "▸ 今日", "value": {"action": "cmd_today"}, "type": "primary"},
                {"text": "预告", "value": {"action": "cmd_preview", "n": 1}},
            ],
            [
                {"text": "打卡卡片", "value": {"action": "cmd_checkin"}},
                {"text": "Calendar 卡片", "value": {"action": "cmd_calendar"}},
            ],
        ],
    ))


def _fmt_review_line(p: dict) -> str:
    tag = " ⚠️" if p.get("is_overdue") else ""
    stage = p.get("review_stage", 0)
    return f"- `#{p['id']}` · {p['title']} · {p['difficulty']} · Stage {stage}{tag}"


def _fmt_new_line(p: dict) -> str:
    return f"- `#{p['id']}` · {p['title']} · {p['difficulty']} · {p.get('category','')}"


def _diff_type(diff: str) -> str:
    """把难度映射到 button type（视觉上跟难度色对齐，但飞书 button 只有 default/primary/danger）"""
    return "danger" if diff == "困难" else ("primary" if diff == "中等" else "default")


def _problem_action_row(p: dict, kind: str) -> list[dict]:
    """kind='review' → 秒A/磕绊/卡住 走 review API；kind='new' → 很稳/磕绊/卡住 走 status API。"""
    pid = p["id"]
    if kind == "review":
        return [
            {"text": "😄 秒A", "value": {"action": "review", "pid": pid, "score": "easy"}, "type": "primary"},
            {"text": "🙂 磕绊", "value": {"action": "review", "pid": pid, "score": "ok"}},
            {"text": "😩 卡住", "value": {"action": "review", "pid": pid, "score": "hard"}, "type": "danger"},
            {"text": "推迟", "value": {"action": "postpone", "pid": pid}},
        ]
    else:
        return [
            {"text": "很稳", "value": {"action": "solve", "pid": pid, "status": "solid"}, "type": "primary"},
            {"text": "磕绊", "value": {"action": "solve", "pid": pid, "status": "shaky"}},
            {"text": "卡住", "value": {"action": "solve", "pid": pid, "status": "forgot"}, "type": "danger"},
        ]


def cmd_today(chat_id: str) -> None:
    """今日复习 + 新题，每题一张小卡片（含打分按钮）。"""
    try:
        d = api_get("/api/dashboard")
    except Exception as e:
        send_text(chat_id, f"✗ 拉今日数据失败：{e}")
        return

    reviews = d.get("due_review") or []
    news = d.get("today_new") or []

    if not reviews and not news:
        send_text(chat_id, "今天没题，收工 🎉")
        return

    # 用一张 header 卡片打头
    header_lines = [f"**Hot 100 · {d['date']}**"]
    if reviews:
        header_lines.append(f"\n🔁 今日复习（{len(reviews)}）")
    if news:
        header_lines.append(f"🆕 今日新题（{len(news)}）")
    send_card(chat_id, card_menu(
        "📓 今日",
        "\n".join(header_lines),
        theme="blue",
    ))

    # 每道复习题一张卡（带打分按钮）
    for p in reviews:
        subtitle = (
            f"**{DIFF_ICON.get(p['difficulty'], '')} #{p['id']} · {p['title']}**\n\n"
            f"分类：{p.get('category','')} · Stage {p.get('review_stage',0)} · "
            f"Due {p.get('next_review','')}"
            + (" · ⚠️ 逾期" if p.get('is_overdue') else "")
        )
        send_card(chat_id, card_menu(
            f"🔁 复习 · #{p['id']}",
            subtitle,
            buttons=[_problem_action_row(p, kind="review")],
            theme="turquoise",
        ))

    # 每道新题一张卡（带首刷状态按钮）
    for p in news:
        subtitle = (
            f"**{DIFF_ICON.get(p['difficulty'], '')} #{p['id']} · {p['title']}**\n\n"
            f"分类：{p.get('category','')}"
        )
        send_card(chat_id, card_menu(
            f"🆕 新题 · #{p['id']}",
            subtitle,
            buttons=[_problem_action_row(p, kind="new")],
            theme="green",
        ))


def cmd_preview(chat_id: str, n: int = 1) -> None:
    """N 天后预告（只文字）。"""
    if n < 1:
        n = 1
    if n > 30:
        n = 30
    try:
        # /preview 页面接受 ?day=N，但我们要 JSON —— 用 dashboard 的兄弟接口？
        # baguwen 走 build_preview，我们这里直接 GET dashboard 拿 due_review 未来时段太复杂
        # 走一个专门的 API：/api/preview?day=N
        d = api_get(f"/api/preview?day={n}")
    except Exception as e:
        send_text(chat_id, f"✗ 拉预告数据失败：{e}\n（可能需要在 Flask app.py 里加 /api/preview 端点）")
        return

    reviews = d.get("due_review") or []
    news = d.get("today_new") or []
    date_str = d.get("date", "")
    is_tomorrow = n == 1

    label = "明日" if is_tomorrow else f"{n} 天后"
    lines = [f"**Preview · {label}（{date_str}）**"]

    if not reviews and not news:
        lines.append("\n那天没题。")
    else:
        if reviews:
            lines.append(f"\n🔁 到期复习（{len(reviews)}）")
            for p in reviews:
                lines.append(_fmt_review_line(p))
        if news:
            lines.append(f"\n🆕 新题（{len(news)}）")
            for p in news:
                lines.append(_fmt_new_line(p))

    send_card(chat_id, card_menu(f"🔮 预告 · {label}", "\n".join(lines), theme="purple"))


def _send_card_image(chat_id: str, which: str) -> None:
    """which ∈ {'checkin', 'calendar'}。走 playwright + 飞书 App API 发图。"""
    sys.path.insert(0, str(ROOT / "scripts"))
    try:
        from feishu_daily import _tenant_token, _upload_image, _send_image
        from render_checkin import render
    except Exception as e:
        send_text(chat_id, f"✗ 加载渲染依赖失败：{e}")
        return

    send_text(chat_id, f"⏳ 正在生成 {which} 卡片…")
    try:
        out = Path("/tmp") / f"hot100-{which}-bot.png"
        render(out, which=which)
        token = _tenant_token(APP_ID, APP_SECRET)
        image_key = _upload_image(token, out)
        _send_image(token, chat_id, image_key)
    except Exception as e:
        send_text(chat_id, f"✗ 生成/发送失败：{e}")
        traceback.print_exc()


def cmd_checkin(chat_id: str) -> None:
    _send_card_image(chat_id, "checkin")


def cmd_calendar(chat_id: str) -> None:
    _send_card_image(chat_id, "calendar")


# ==========================================================================
# 命令 dispatcher
# ==========================================================================
def dispatch_command(chat_id: str, uid: str, text: str) -> None:
    text = text.strip()
    if not text:
        return

    lower = text.lower()

    # help
    if text in ("/help", "帮助", "/?", "?") or lower == "help":
        cmd_help(chat_id)
        return

    # today
    if text in ("/today", "今日", "今天") or lower == "today":
        cmd_today(chat_id)
        return

    # checkin
    if text in ("/checkin", "打卡") or lower == "checkin":
        cmd_checkin(chat_id)
        return

    # calendar
    if text in ("/calendar", "节奏") or lower == "calendar":
        cmd_calendar(chat_id)
        return

    # preview（可选参数 N）
    m = re.match(r"^(?:/preview|preview|预告)(?:\s+(\d+))?$", text, re.IGNORECASE)
    if m:
        n = int(m.group(1)) if m.group(1) else 1
        cmd_preview(chat_id, n)
        return

    # cancel（没有多轮时就是提示）
    if text in ("/cancel", "取消") or lower == "cancel":
        send_text(chat_id, "当前没有进行中的操作")
        return

    send_text(chat_id, f"未识别的命令：`{text}`\n发 `/help` 查看命令列表。")


# ==========================================================================
# 卡片按钮 dispatch
# ==========================================================================
def handle_card_action(user_id: str, chat_id: str, action: dict) -> None:
    a = action.get("action")

    if a == "cmd_today":
        cmd_today(chat_id)
    elif a == "cmd_preview":
        cmd_preview(chat_id, int(action.get("n", 1)))
    elif a == "cmd_checkin":
        cmd_checkin(chat_id)
    elif a == "cmd_calendar":
        cmd_calendar(chat_id)
    elif a == "review":
        pid = action.get("pid")
        score = action.get("score")
        code, resp = api_call("POST", f"/api/problem/{pid}/review", {"score": score})
        if code == 200 and resp.get("ok"):
            label = {"easy": "秒A", "ok": "磕绊", "hard": "卡住"}.get(score, score)
            send_text(chat_id, f"✓ #{pid} · {label} 已记录")
        else:
            send_text(chat_id, f"✗ 记录失败：{resp.get('error') or resp}")
    elif a == "solve":
        pid = action.get("pid")
        status = action.get("status")
        code, resp = api_call("POST", f"/api/problem/{pid}/status", {"status": status})
        if code == 200 and resp.get("ok"):
            label = {"solid": "很稳", "shaky": "磕绊", "forgot": "卡住"}.get(status, status)
            send_text(chat_id, f"✓ #{pid} · {label} 已记录")
        else:
            send_text(chat_id, f"✗ 记录失败：{resp.get('error') or resp}")
    elif a == "postpone":
        pid = action.get("pid")
        code, resp = api_call("POST", f"/api/problem/{pid}/postpone")
        if code == 200 and resp.get("ok"):
            send_text(chat_id, f"✓ #{pid} 已推迟到明天")
        else:
            send_text(chat_id, f"✗ 推迟失败：{resp.get('error') or resp}")
    else:
        send_text(chat_id, f"未识别的按钮 action: {a}")


# ==========================================================================
# 事件回调
# ==========================================================================
def on_message(data: P2ImMessageReceiveV1) -> None:
    try:
        msg = data.event.message
        chat_id = msg.chat_id
        sender = data.event.sender
        uid = sender.sender_id.user_id or sender.sender_id.open_id
        if not uid:
            return
        if msg.message_type != "text":
            send_text(chat_id, "目前只支持文本命令。发 `/help` 查看。")
            return
        content = json.loads(msg.content)
        text = content.get("text", "").strip()
        text = re.sub(r"^@_user_\d+\s*", "", text).strip()
        print(f"[MSG] uid={uid} chat={chat_id} text={text!r}", flush=True)
        dispatch_command(chat_id, uid, text)
    except Exception:
        traceback.print_exc()


def on_card_action(data: P2CardActionTrigger) -> P2CardActionTriggerResponse:
    try:
        value = data.event.action.value or {}
        operator = data.event.operator
        chat_id = data.event.context.open_chat_id
        uid = operator.user_id or operator.open_id
        print(f"[BTN] uid={uid} chat={chat_id} value={value}", flush=True)
        handle_card_action(uid, chat_id, value)
    except Exception:
        traceback.print_exc()
    return P2CardActionTriggerResponse({})


# ==========================================================================
# 启动
# ==========================================================================
def main():
    print(f"▸ Hot 100 Bot 启动")
    print(f"  APP_ID:   {APP_ID}")
    print(f"  API_BASE: {API_BASE}")

    try:
        d = api_get("/api/dashboard")
        print(f"  ✓ 后端 {API_BASE} 可达（quota={d.get('quota')}）")
    except Exception as e:
        print(f"  ⚠ 后端不可达：{e}（bot 仍启动，但命令会失败）")

    handler = lark.EventDispatcherHandler.builder("", "") \
        .register_p2_im_message_receive_v1(on_message) \
        .register_p2_card_action_trigger(on_card_action) \
        .build()

    ws_client = lark.ws.Client(
        APP_ID, APP_SECRET,
        event_handler=handler,
        log_level=lark.LogLevel.INFO,
    )
    ws_client.start()


if __name__ == "__main__":
    main()
