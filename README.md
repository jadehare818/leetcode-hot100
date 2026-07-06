# LeetCode Hot 100 Tracker

用 Flask + JSON 文件搭的本地 web 刷题追踪器：动态看板 + 遗忘曲线复习 + 多语言代码归档 +（可选）飞书推送。

## 特性

- 🎯 **动态看板**：每天现算 = 到期复习 + 未刷池按配额抽今日新题（尝试难度均衡：简/中/困各一）
- 🔁 **遗忘曲线**：+1 → +3 → +7 → +15 → +30 天五档，复习时打分调档
  - 😄 秒A → 前进一档
  - 🙂 磕绊 → 保持
  - 😩 卡住 → 回退到档 0
- ⚡ **动态调整**：多刷/犯懒都不打乱节奏，"推迟全部"一键处理逾期堆积
- 💪 **加练池**：今日目标之外多推 10 道，方便加餐
- 📝 **多语言代码**：Python / Go / C++ / Java 各自一个目录，右上角切换
- 💡 **思路** + 📝 **Cheatsheet**：每题两个字段，看板卡片 / 全部题目 / 详情页处处可编辑
- 🤖 **飞书推送**：可选

## 起服务

```bash
cd leetcode-hot100
python -m venv .venv && .venv/bin/pip install -r requirements.txt
.venv/bin/python app.py
# → http://localhost:5001
```

## 隐私架构

这个仓库是模板 —— 你的**私人数据不上传公开仓库**。设计如下：

| 文件 | 是否进 git | 说明 |
|---|---|---|
| `data/problems.json` | ✅ | hot100 题目分类数据（公开）|
| `data/cheatsheet.md` | ✅ | 语法模板（公开）|
| `app.py` / `templates/` / `static/` | ✅ | 代码 |
| **`data/progress.json`** | ✅（空 seed）| 上传时是 `{}`，仅作为其他人克隆时的种子 |
| **`data/progress.local.json`** | ❌ | 你的真实进度、思路、per-problem cheatsheet；`load_progress()` 优先读它 |
| **`config.local.json`** | ❌ | 敏感字段（feishu webhook / secret 等）|
| **`solutions/*/[0-9]*.{py,go,cpp,java}`** | ❌ | 你的题解代码；`.gitkeep` 保留目录结构 |

第一次跑：`cp config.local.json.example config.local.json` 后填入 webhook。

## 目录结构

```
leetcode-hot100/
├── app.py
├── config.json                 # 公开配置：配额、间隔、语言列表
├── config.local.json           # (gitignored) 私人：飞书凭证
├── config.local.json.example
├── data/
│   ├── problems.json           # 公开的 101 题分类数据
│   ├── progress.json           # 公开：空 seed
│   ├── progress.local.json     # (gitignored) 你的真实进度
│   └── cheatsheet.md
├── solutions/                  # 各语言目录 + .gitkeep，代码本身 gitignored
│   ├── python/
│   ├── go/
│   ├── cpp/
│   └── java/
├── templates/
├── static/
└── scripts/
    ├── feishu_daily.py
    ├── feishu_daily.launchd.plist
    ├── daily_autocommit.sh
    └── daily_autocommit.launchd.plist
```

## 状态语义

| 标签 | 含义 |
|---|---|
| ⚪ todo | 未刷 |
| 🔴 forgot | 思路忘 / 卡住 |
| 🟡 shaky | 磕绊 / 语法忘 |
| 🟢 solid | 稳，直接进复习后段 |
| 📦 archived | 归档，不再复习 |

## 飞书推送（可选）

1. 飞书群 → 群设置 → 群机器人 → 添加"自定义机器人"，拿到 webhook + secret
2. `cp config.local.json.example config.local.json`，填入
3. 测一发：`.venv/bin/python scripts/feishu_daily.py`
4. 每日定时（09:00 早提醒 + 22:00 自动 commit）：

   ```bash
   cp scripts/feishu_daily.launchd.plist ~/Library/LaunchAgents/com.wyt.leetcode-hot100.feishu.plist
   cp scripts/daily_autocommit.launchd.plist ~/Library/LaunchAgents/com.wyt.leetcode-hot100.autocommit.plist
   launchctl load ~/Library/LaunchAgents/com.wyt.leetcode-hot100.feishu.plist
   launchctl load ~/Library/LaunchAgents/com.wyt.leetcode-hot100.autocommit.plist
   ```

## 常见操作

- **今日多刷了几题** → 直接刷；第二天新题配额自动少给
- **今日犯懒没刷** → 到期题下次进看板还在；点标题右侧"推迟全部"批量顺延
- **调节奏** → `config.json.daily_quota` 或 `review_intervals_days`
- **切换代码语言** → 右上角下拉；已有文件不删，各语言独立保存

## License

MIT，供参考。
