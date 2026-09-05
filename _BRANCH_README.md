# data-jadehare818 分支

这是 [jadehare818](https://github.com/jadehare818) 的**个人完整环境分支**：代码 + 私人数据都在，直接 clone 就能跑。

## 里面装了什么

- 完整的 Flask 应用代码（跟 `main` 分支保持同步）
- `data/progress.local.json` — 每题状态、复习档位、思路、per-problem cheatsheet
- `data/study-notes.md` — 自动生成的手机可读笔记
- `solutions/<lang>/*.py|go|cpp|java` — 我自己的题解代码

**不含**：`.env`（飞书凭证）、`config.local.json`（本机偏好）、`.venv/`（依赖）—— 这些每台机器单独配。

## 你为什么会看到它

我在多台设备之间同步刷题环境用的。**如果你就是我**，克隆这个分支就能开箱即用；如果不是，clone `main` 分支才是可运行的公开版本。

## 我自己在新机器上恢复

```bash
git clone -b data-jadehare818 https://github.com/jadehare818/leetcode-hot100.git
cd leetcode-hot100
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt

# 配飞书（可选）
cp .env.example .env
# 编辑 .env 填入 FEISHU_WEBHOOK 和 FEISHU_SECRET

# 起服务
.venv/bin/python app.py
```

## 同步策略

- 每晚 22:00 `daily_autocommit.sh` push 代码变更到 `main`
- 每晚 22:05 `sync_personal_data.sh` push 私人数据到 **本分支**
- **本分支不会自动跟随 main 的代码更新**：手动 cherry-pick 或者：

  ```bash
  git checkout data-jadehare818
  git checkout main -- app.py templates/ static/ scripts/
  git commit -am "sync from main $(date +%F)"
  git push origin data-jadehare818
  ```
