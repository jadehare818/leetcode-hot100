#!/bin/bash
# 把「本地完整快照」推到远程 data-<user> 分支：
#   arm(main 最新代码) + arm(本地私人数据：progress.local / solutions 代码 / study-notes)
#
# 语义：数据分支 = origin/main 最新 HEAD + 一个补齐个人数据的 commit
# 每次跑都 hard-reset 到 origin/main 再叠一个 snapshot commit 上去，force-push。
# 历史不干净但也无所谓 —— 这个分支只是给我一台新机器 clone 就跑起来的。
#
# 排除项（gitignore 里就有的私人/机器级/易变文件）：
#   .env / .venv / __pycache__ / *.pyc / .DS_Store / dist / .claude
#   data/*.log / data/*.err.log / data/progress.backup.*.json
#
# 手动跑：./scripts/sync_personal_data.sh
# 定时跑：挂 launchd（daily_autocommit 之后 5 分钟，确保 main 已 push）
#
# 前提：远程已有 data-<user> 分支；否则先手动创：
#   git checkout --orphan data-jadehare818 && git commit ...

set -e

REPO="/Users/bytedance/leetcode-hot100"
BRANCH="data-jadehare818"
cd "$REPO"

export SSH_AUTH_SOCK="${SSH_AUTH_SOCK:-$HOME/.ssh/ssh-auth.sock}"
export PATH="/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin"

# 先拉最新 main
git fetch -q origin main

# 生成人类可读的 markdown 笔记（供手机阅读用）
if [[ -x "$REPO/.venv/bin/python" ]]; then
  "$REPO/.venv/bin/python" "$REPO/scripts/export_notes.py" > /dev/null || true
elif command -v python3 > /dev/null; then
  python3 "$REPO/scripts/export_notes.py" > /dev/null || true
fi

# worktree 副本操作，不打扰主工作树
WORKTREE=$(mktemp -d)
trap "cd '$REPO' && git worktree remove -f '$WORKTREE' 2>/dev/null || rm -rf '$WORKTREE'" EXIT

# 从 origin/main 起一个 worktree（分支不存在也无所谓，稍后 force-push）
git worktree add -f --detach "$WORKTREE" origin/main

# 用 rsync 把本地整个仓库同步过去，剔除机器级/易变/敏感文件
# --delete 保证 worktree 完全等于源目录（不会残留 orphan 分支上的老文件）
# 但不清 .git（worktree 需要它指向主仓库的 gitdir 文件）
rsync -a --delete \
  --exclude=".git" \
  --exclude=".venv" \
  --exclude="__pycache__" \
  --exclude="*.pyc" \
  --exclude=".DS_Store" \
  --exclude="dist" \
  --exclude=".claude" \
  --exclude=".env" \
  --exclude="data/*.log" \
  --exclude="data/*.err.log" \
  --exclude="data/progress.backup.*.json" \
  "$REPO/" "$WORKTREE/"

cd "$WORKTREE"

# 显式删除 origin/main 上跟踪着但不该跟到 data 分支的机器级/运行时文件
# （这些理想上不该在 main 上，但眼下先在 sync 阶段清一次）
rm -f data/app.log

# 用 -A -f：-f 强制加入 gitignored 的文件（progress.local.json / config.local.json / solutions 代码等）
git add -A -f

# 没有任何差异就不 commit（意味着本地 = origin/main + 已同步过的个人数据）
if git diff --cached --quiet; then
  echo "$(date '+%F %T') no changes vs origin/main; nothing to push"
  exit 0
fi

# 设置作者身份（避免 launchd 环境下缺失）
git -c user.name="jadehare818" -c user.email="jadehare818@gmail.com" \
    commit -q -m "snapshot: personal data + main $(date '+%Y-%m-%d %H:%M')"

# force-push：数据分支的语义就是「main 最新 + 一层 personal snapshot」，历史干净与否不重要
git push -q --force origin "HEAD:refs/heads/$BRANCH"
echo "$(date '+%F %T') force-pushed to $BRANCH (main + personal snapshot)"
