#!/bin/bash
# 每晚跑：如果有变更就 commit + push，没有就静默跳过。
# 由 launchd (com.wyt.leetcode-hot100.autocommit) 触发。

set -e

REPO="/Users/bytedance/leetcode-hot100"
cd "$REPO"

# 确保 SSH agent 能找到 key（launchd 环境很干净）
export SSH_AUTH_SOCK="${SSH_AUTH_SOCK:-$HOME/.ssh/ssh-auth.sock}"
export PATH="/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin"

# 有变更才 commit
if [[ -z "$(git status --porcelain)" ]]; then
  echo "$(date '+%Y-%m-%d %H:%M:%S') no changes, skipping"
  exit 0
fi

git add -A
git commit -q -m "chore: daily snapshot $(date '+%Y-%m-%d')"
git push -q origin main
echo "$(date '+%Y-%m-%d %H:%M:%S') pushed $(git log -1 --oneline)"
