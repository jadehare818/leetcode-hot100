#!/bin/bash
# 构建两个 macOS .app（Hot100 启动 + Hot100 Stop 停止），装到 /Applications。
# 幂等：重跑覆盖之前的版本。
#
# 用法：./scripts/build_mac_app.sh

set -e
REPO="/Users/bytedance/leetcode-hot100"
DIST="$REPO/dist"
mkdir -p "$DIST"

# ---- Launch app ----
LAUNCH_AS=$(mktemp -t hot100-launch.XXXXXX.applescript)
cat > "$LAUNCH_AS" <<AS
do shell script "$REPO/scripts/launch_app.sh"
AS
rm -rf "$DIST/Hot100.app"
osacompile -o "$DIST/Hot100.app" "$LAUNCH_AS"
rm "$LAUNCH_AS"

# ---- Stop app ----
STOP_AS=$(mktemp -t hot100-stop.XXXXXX.applescript)
cat > "$STOP_AS" <<AS
do shell script "$REPO/scripts/stop_app.sh"
AS
rm -rf "$DIST/Hot100 Stop.app"
osacompile -o "$DIST/Hot100 Stop.app" "$STOP_AS"
rm "$STOP_AS"

# ---- Install to /Applications ----
cp -R "$DIST/Hot100.app" /Applications/
cp -R "$DIST/Hot100 Stop.app" /Applications/

echo "✅ Built + installed:"
echo "  /Applications/Hot100.app"
echo "  /Applications/Hot100 Stop.app"
echo ""
echo "从此双击 Hot100.app 启动，双击 Hot100 Stop.app 停止。"
echo "Spotlight (Cmd+Space) 输 hot100 也能找到。"
