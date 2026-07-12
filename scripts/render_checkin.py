"""
Render Hot 100 卡片到 PNG（via Playwright）。

用法：
    python scripts/render_checkin.py                    # 默认渲染 checkin 卡
    python scripts/render_checkin.py --which=calendar   # 渲染 Calendar 卡
    python scripts/render_checkin.py --out /tmp/x.png

流程：
    1. 起（或复用）本地 Flask 服务
    2. Chromium 打开对应页面
    3. 等卡片渲染完 → 截图 → PNG
"""
from __future__ import annotations

import argparse
import subprocess
import sys
import time
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_PORT = 5001
DEFAULT_OUT = Path("/tmp") / "hot100-checkin.png"

# 每种卡片：URL 路径 · 触发选择器（None 表示卡片直接在页面上） · 卡片元素选择器 · 视口尺寸
CARD_SPECS = {
    "checkin": {
        "url": "/",
        "trigger": "#open-checkin-card",
        "card": ".checkin-card",
        "ready": ".checkin-card .cc-head",
        "viewport": (1080, 1300),
    },
    "calendar": {
        "url": "/calendar-card",   # 独立页面，卡片直接在里面
        "trigger": None,
        "card": ".calendar-card",
        "ready": ".calendar-card .cal-hero",
        "viewport": (1600, 1000),   # 16:9 横版
    },
}


def _port_open(port: int) -> bool:
    import socket
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(0.2)
        try:
            s.connect(("127.0.0.1", port))
            return True
        except OSError:
            return False


def _start_flask() -> subprocess.Popen | None:
    if _port_open(DEFAULT_PORT):
        return None
    py = ROOT / ".venv" / "bin" / "python"
    if not py.exists():
        py = Path(sys.executable)
    log = open("/tmp/hot100-flask-tmp.log", "w")
    proc = subprocess.Popen(
        [str(py), str(ROOT / "app.py")],
        stdout=log, stderr=log,
    )
    for _ in range(30):
        if _port_open(DEFAULT_PORT):
            return proc
        time.sleep(0.2)
    proc.terminate()
    raise RuntimeError("Flask 服务起不来")


def render(out_path: Path, which: str = "checkin") -> Path:
    """渲染指定的卡片到 PNG。which ∈ {'checkin', 'calendar'}。"""
    if which not in CARD_SPECS:
        raise ValueError(f"unknown card kind: {which}")
    spec = CARD_SPECS[which]

    started_flask = _start_flask()
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            vw, vh = spec["viewport"]
            ctx = browser.new_context(
                viewport={"width": vw, "height": vh},
                device_scale_factor=2,
            )
            page = ctx.new_page()
            page.goto(f"http://127.0.0.1:{DEFAULT_PORT}{spec['url']}", wait_until="networkidle")

            if spec["trigger"]:
                page.click(spec["trigger"])
            page.wait_for_selector(spec["ready"], timeout=10000)
            page.wait_for_timeout(600)

            card = page.locator(spec["card"])
            out_path.parent.mkdir(parents=True, exist_ok=True)
            card.screenshot(path=str(out_path), omit_background=False)
            browser.close()
        return out_path
    finally:
        if started_flask is not None:
            started_flask.terminate()
            try:
                started_flask.wait(timeout=5)
            except subprocess.TimeoutExpired:
                started_flask.kill()


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--which", choices=list(CARD_SPECS.keys()), default="checkin",
                    help="要渲染哪种卡片")
    ap.add_argument("--out", type=Path, default=None, help="输出 PNG 路径（默认 /tmp/hot100-{which}.png）")
    args = ap.parse_args()
    out = args.out or Path("/tmp") / f"hot100-{args.which}.png"
    result = render(out, which=args.which)
    size = result.stat().st_size
    print(f"[render] wrote {result} ({size} bytes, which={args.which})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
