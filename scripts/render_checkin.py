"""
Render the check-in card to PNG via Playwright.

用法：
    python scripts/render_checkin.py [--out /tmp/hot100-checkin.png]

流程：
    1. 起（或复用）本地 Flask 服务 http://127.0.0.1:5001
    2. 用 headless Chromium 打开 dashboard
    3. 点 Share 按钮 → 等卡片渲染完
    4. 截 .checkin-card 元素 → 存 PNG
"""
from __future__ import annotations

import argparse
import os
import subprocess
import sys
import time
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_PORT = 5001
DEFAULT_OUT = Path("/tmp") / "hot100-checkin.png"


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
    """如果服务没在跑，起一个临时的（子进程，脚本退出时收拾）。"""
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
    # 等端口就绪
    for _ in range(30):
        if _port_open(DEFAULT_PORT):
            return proc
        time.sleep(0.2)
    proc.terminate()
    raise RuntimeError("Flask 服务起不来")


def render(out_path: Path) -> Path:
    started_flask = _start_flask()
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            # 卡片是 540 宽 + modal 有 padding；用 1080 视口保证 2x 清晰
            ctx = browser.new_context(
                viewport={"width": 1080, "height": 1200},
                device_scale_factor=2,
            )
            page = ctx.new_page()
            page.goto(f"http://127.0.0.1:{DEFAULT_PORT}/", wait_until="networkidle")

            # 点开 Share 按钮
            page.click("#open-checkin-card")
            # 等卡片被填充（.cc-head 出现即代表 render() 跑完）
            page.wait_for_selector(".checkin-card .cc-head", timeout=10000)
            # 稍等字体和图完全加载
            page.wait_for_timeout(600)

            # 截 .checkin-card 这一个元素
            card = page.locator(".checkin-card")
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
    ap.add_argument("--out", type=Path, default=DEFAULT_OUT, help="输出 PNG 路径")
    args = ap.parse_args()
    out = render(args.out)
    size = out.stat().st_size
    print(f"[render_checkin] wrote {out} ({size} bytes)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
