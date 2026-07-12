#!/bin/bash
# 启动飞书 Bot（前台跑，Ctrl+C 停）
# 依赖：先跑 app.py (localhost:5001)

cd "$(dirname "$0")"

if [ ! -f .env ]; then
  echo "!! 缺少 .env 文件（需要 FEISHU_APP_ID / FEISHU_APP_SECRET）"
  exit 1
fi

if [ ! -d .venv ]; then
  echo "!! 缺少 .venv"
  exit 1
fi

if ! ./.venv/bin/python -c "import lark_oapi" 2>/dev/null; then
  echo "▸ 首次跑：装 lark-oapi…"
  ./.venv/bin/pip install lark-oapi
fi

exec ./.venv/bin/python hot100_bot.py
