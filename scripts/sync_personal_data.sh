#!/bin/bash
# 把私人数据（progress.local.json + solutions/）同步到远程 data-<user> 分支。
# 独立于 daily_autocommit.sh：一个管公开 main，一个管私人分支。
#
# 手动跑：./scripts/sync_personal_data.sh
# 定时跑：把这个脚本挂 launchd（跟 daily_autocommit 同一时刻，或者更晚 5 分钟）
#
# 前提：远程已有 data-<user> 分支（用孤儿分支创建过一次）

set -e

REPO="/Users/bytedance/leetcode-hot100"
BRANCH="data-jadehare818"     # 改成你自己的分支名
cd "$REPO"

export SSH_AUTH_SOCK="${SSH_AUTH_SOCK:-$HOME/.ssh/ssh-auth.sock}"
export PATH="/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin"

# 1. 记住当前 main 分支的 commit
CURRENT_BRANCH=$(git branch --show-current)
STASH=""

# 2. 用 git stash --include-untracked 把工作树里的所有变更（含私人文件）暂存
if [[ -n "$(git status --porcelain --ignored=matching)" ]] || \
   [[ -f "data/progress.local.json" ]] || \
   ls solutions/*/[0-9]*.* 2>/dev/null | head -1 > /dev/null; then
  # 用 update-index 强制忽略 gitignore，把私人文件放到临时索引
  :
fi

# 3. 简化做法：worktree 副本操作，不打扰主工作树
WORKTREE=$(mktemp -d)
trap "rm -rf $WORKTREE" EXIT

git worktree add -f "$WORKTREE" "$BRANCH" 2>/dev/null || {
  # 如果分支不存在，从 origin 创建
  git fetch origin "$BRANCH":"$BRANCH" 2>/dev/null || {
    echo "$(date '+%F %T') branch $BRANCH not found on remote, aborting" >&2
    exit 1
  }
  git worktree add -f "$WORKTREE" "$BRANCH"
}

# 4. 同步私人文件到 worktree
mkdir -p "$WORKTREE/data" "$WORKTREE/solutions"
[[ -f "$REPO/data/progress.local.json" ]] && cp "$REPO/data/progress.local.json" "$WORKTREE/data/"

# 生成人类可读的 markdown 笔记（供手机阅读用）
if [[ -x "$REPO/.venv/bin/python" ]]; then
  "$REPO/.venv/bin/python" "$REPO/scripts/export_notes.py" > /dev/null || true
elif command -v python3 > /dev/null; then
  python3 "$REPO/scripts/export_notes.py" > /dev/null || true
fi
[[ -f "$REPO/data/study-notes.md" ]] && cp "$REPO/data/study-notes.md" "$WORKTREE/data/"

# 用 rsync 复制 solutions（保留目录结构，只带代码文件）
rsync -a --include="*/" \
    --include="[0-9]*.py" --include="[0-9]*.go" \
    --include="[0-9]*.cpp" --include="[0-9]*.java" \
    --exclude="*" \
    "$REPO/solutions/" "$WORKTREE/solutions/"

# 5. 在 worktree 里 commit + push
cd "$WORKTREE"
if [[ -z "$(git status --porcelain)" ]]; then
  echo "$(date '+%F %T') no personal changes, skipping"
  cd "$REPO"
  git worktree remove -f "$WORKTREE"
  exit 0
fi

git add -A
git commit -q -m "sync: personal data $(date '+%Y-%m-%d')"
git push -q origin "$BRANCH"
echo "$(date '+%F %T') pushed personal data to $BRANCH"

cd "$REPO"
git worktree remove -f "$WORKTREE"
