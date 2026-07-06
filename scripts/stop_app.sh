#!/bin/bash
# Stop the Hot 100 tracker (kill the Flask process listening on 5001).

PORT=5001
PIDS=$(lsof -tiTCP:$PORT -sTCP:LISTEN 2>/dev/null || true)
if [[ -z "$PIDS" ]]; then
  osascript -e 'display notification "服务本来就没在跑" with title "Hot 100"'
  exit 0
fi
kill $PIDS 2>/dev/null || true
sleep 0.5
if lsof -iTCP:$PORT -sTCP:LISTEN -n -P >/dev/null 2>&1; then
  # 顽强的进程强杀
  kill -9 $PIDS 2>/dev/null || true
fi
osascript -e 'display notification "已停止" with title "Hot 100"'
