#!/bin/bash
# Launch the Hot 100 tracker: start Flask in background, open browser.
# Called by the double-click .app in /Applications or elsewhere.

set -e

REPO="/Users/bytedance/leetcode-hot100"
PORT=5001
LOG="$REPO/data/app.log"

cd "$REPO"

# 已经在跑就直接开浏览器
if lsof -iTCP:$PORT -sTCP:LISTEN -n -P >/dev/null 2>&1; then
  open "http://localhost:$PORT/"
  exit 0
fi

# 起服务（nohup 让它脱离父进程，关掉 Automator app 也不影响）
mkdir -p "$REPO/data"
nohup "$REPO/.venv/bin/python" "$REPO/app.py" > "$LOG" 2>&1 &
disown

# 等端口就绪，最多 5 秒
for i in {1..20}; do
  if lsof -iTCP:$PORT -sTCP:LISTEN -n -P >/dev/null 2>&1; then
    open "http://localhost:$PORT/"
    exit 0
  fi
  sleep 0.25
done

# 超时也开浏览器（说不定慢一点起来）
open "http://localhost:$PORT/"
