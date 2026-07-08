# LeetCode Hot 100 Tracker

> 本地跑的 LeetCode 热题 100 刷题追踪器：**动态每日看板 + 遗忘曲线复习 + 多语言代码归档 + 未来 30 日预告 + 打卡卡片**。可选**飞书每日推送**。

<p>
  <img alt="python" src="https://img.shields.io/badge/python-3.10%2B-blue">
  <img alt="stack" src="https://img.shields.io/badge/stack-Flask%20%2B%20JSON-lightgrey">
  <img alt="license" src="https://img.shields.io/badge/license-MIT-green">
  <img alt="platform" src="https://img.shields.io/badge/platform-macOS%20%7C%20Linux%20%7C%20Windows-informational">
</p>

一个用 Python + Flask 搭的单机 Web 应用，数据全部落在 JSON 文件里。**没有数据库、没有账号系统、没有云端依赖**，一条命令启动，浏览器打开即用。

---

## 目录

- [为什么做这个](#为什么做这个)
- [核心功能](#核心功能)
- [截图](#截图)
- [快速开始](#快速开始)
- [配置](#配置)
- [状态与打分语义](#状态与打分语义)
- [文件与数据布局](#文件与数据布局)
- [飞书推送（可选）](#飞书推送可选)
- [定时任务（可选，macOS）](#定时任务可选macos)
- [常见问题](#常见问题)
- [Roadmap](#roadmap)
- [贡献](#贡献)
- [License](#license)

---

## 为什么做这个

刷 hot100 的三种典型痛点：

1. **一部分题思路记得，但 Python 语法忘了**（`sorted(key=...)` / `defaultdict` / `heapq` / `bisect` 一停手就想不起来）
2. **一部分复杂题（DP、回溯）思路完全忘了**
3. **还有一部分从没刷过**

市面上的 OJ 平台只记录"你做没做过"，不管**你现在还记不记得**。刷过的题隔一个月就忘光；每天进 LeetCode 又不知道该刷新题还是复习。

这个工具的核心价值：**把"该刷的新题"和"该复习的老题"合并成一个每日看板**，按遗忘曲线自动调度。你只需要打开浏览器看今天要做什么。

---

## 核心功能

### 🎯 动态每日看板

进页面时**当场现算**今天要做什么，不是提前排好的表：

```
今日看板 = 到期复习题（next_review ≤ today）+ 未刷池按配额抽新题
```

- 多刷几道 → 后续新题配额自动扣减
- 今天犯懒没刷 → 到期题第二天还在，累积过 3 天飘红报警
- **新题按难度均衡抽**，默认工作日 3 道（1 简 + 1 中 + 1 困），周末 6 道（2 简 + 3 中 + 1 困）

### 🔁 简化 SM-2 遗忘曲线

每题维护"复习档位"，默认五档：**+1 → +3 → +7 → +15 → +30 天**。

复习后打分：

| 打分 | 效果 |
|------|------|
| 😄 **秒 A** | 档位 +1，间隔拉长 |
| 🙂 **磕绊** | 保持当前档 |
| 😩 **卡住** | 回退到档 0（明天再见）|

档位跑完 5 档（+30 天间隔那次仍秒 A）→ **自动归档**，不再复习。间隔可在 [config.json](config.json) 里改。

### 📅 未来 30 日预告 + SM-2 前向模拟

**Preview** tab 显示未来 30 天的复习节奏 **柱状图**：

- 假设「每次都按时复习 + 每次都秒 A」推演每题档位晋级路径
- 一道 stage 2 明天到期的题，会显示在明天出现一次；不会天天冒头
- **点柱子切天**，用 fetch swap 无刷新
- **点图例标签**可切显隐"复习到期" / "新题 quota"两段
- Day+1 显示具体题目；Day+2..+30 显示占位（未来的新题池当天才现算）

### 🧑‍💻 状态改动的 2 秒可撤销

看板卡片上点复习打分 / 首刷状态时：

- 卡片**淡出 2 秒**再提交
- 2 秒内**再点同一按钮** → 撤销，卡片恢复
- 2 秒内**点了别的按钮** → 卡片瞬间恢复不透明，用新选择重新 2 秒淡出
- 每张卡独立，互不影响

**点错状态不再纠结**。

### 💪 加练池

今日目标之外多推 10 道未刷题，作为"想再来几道？"的加餐区。有空就顺手多刷，没空就当没看见。

### 📝 多语言代码归档

Python / Go / C++ / Java 各自一个目录（`solutions/<lang>/`），右上角下拉切换。

**目的不是本地跑代码**，是让你不用点开 LeetCode 也能查看自己以前写过的代码。切换语言不删已有文件，四种语言的题解各自独立保存。

### 💡 思路 + 📝 Cheatsheet

每题两个字段：

- **思路**（`note`）：短，一两句话记关键 idea
- **Cheatsheet**（`cheatsheet`）：markdown 支持代码块，记这题涉及的语法/套路

三处入口全打通：**看板卡片** / **全部题目表格** / **详情页**，都能内联展开编辑。看板卡片上如果有思路会直接显示摘要，60 字截断。

另有一份**全局 Cheatsheet**（[data/cheatsheet.md](data/cheatsheet.md)），预置 15+ 个高频 Python 语法 section（`sorted` / `defaultdict` / `heapq` / `bisect` / `deque` / `itertools` / DP 模板 / 回溯模板 / 位运算 / 字符串技巧 / 常见坑等），可在网页里编辑。

### 📊 Calendar 日历

Calendar tab 显示两个视图并排：

- **左侧 30 天条形图**：每天首刷 + 复习拆分显示
- **右侧当月月历**：色块深浅 = 当天做题量，可切换月份 / 悬停查看当天做过哪些题
- 顶部展示 30 天总量、活跃天数、连续 streak、峰值

### 📸 打卡卡片

任何页面点顶栏 📸 Share 按钮：

- 生成当日的**打卡卡片**（进度环、连续天数、今日题目列表、8 条策展 blurb 随机选一）
- 用 html2canvas 导出 PNG，一键保存
- 配置飞书凭证后可**直接推到飞书群**

### 📅 逾期批量处理

到期未做题堆到一屏？"今日复习"标题右侧有两个按钮：

- **推迟全部** —— 到期的都推到明天
- **仅推迟逾期** —— 只推超过 3 天没做的

推迟只改 `next_review`，**不动档位**，间隔曲线不受惩罚。

### ⚙️ 网页内设置

顶栏齿轮按钮打开 modal，可调：

- 每日配额（工作日 / 周末）
- 遗忘曲线间隔数组
- 逾期阈值
- 每日结束时间（凌晨 0:00 - 6:00 半小时步进 —— 熬夜党友好）

改完立刻生效，无需重启。

### 🤖 飞书推送（可选）

字节 / 飞书用户可以配置每天早上自动推送**打卡卡片图片**到飞书群（详见下文）。**其他公司或个人用户可跳过**。

---

## 截图

> 建议在这里放 dashboard / preview / calendar / share card 的截图，让别人一眼看到长什么样。

（暂缺 —— 欢迎 PR 补充）

---

## 快速开始

### 1. 环境要求

- **Python 3.10+**（用了 `dict[str, list]` 之类的现代类型标注）
- macOS / Linux / Windows 均可

### 2. 克隆与安装

```bash
git clone https://github.com/jadehare818/leetcode-hot100.git
cd leetcode-hot100

python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
```

依赖只有两个：`flask`（Web 框架）和 `playwright`（可选，仅飞书图片模式用到；不发飞书可以不装）。

### 3. 启动

```bash
.venv/bin/python app.py
```

打开 [http://localhost:5001](http://localhost:5001)。

**就这么简单**。首次进入所有题都是"未刷"状态，你从 Today tab 开始随手标状态即可。数据自动写入 `data/progress.local.json`（gitignored，不进公开仓库）。

### 4. 停止

`Ctrl+C` 即可。

---

## 配置

### 公开配置：[config.json](config.json)

```json
{
  "daily_quota": {"weekday": 3, "weekend": 6},
  "review_intervals_days": [1, 3, 7, 15, 30],
  "overdue_alert_days": 3,
  "day_boundary_hour": 0,
  "port": 5001,
  "languages": ["python", "go", "cpp", "java"],
  "default_language": "python"
}
```

各字段：

| 字段 | 含义 | 默认 |
|------|------|------|
| `daily_quota` | 每日新题配额 | 工作日 3 / 周末 6 |
| `review_intervals_days` | 五档复习间隔（天）| `[1, 3, 7, 15, 30]` |
| `overdue_alert_days` | 逾期几天飘红 | 3 |
| `day_boundary_hour` | 一天几点结束（0-6，允许 .5）| 0（自然日）|
| `port` | Flask 端口 | 5001 |
| `languages` | 支持的语言目录 | python / go / cpp / java |
| `default_language` | 默认选中语言 | python |

**改配置可以直接在网页设置里改**，也可以手动编辑 `config.json`。改完立即生效，无需重启。

### 覆盖配置：`config.local.json`（可选，gitignored）

不想改公开的 `config.json` 但想本地覆盖某几项，就建一份 `config.local.json`：

```json
{
  "daily_quota": {"weekday": 5, "weekend": 8},
  "port": 5555
}
```

`app.py` 加载顺序：`config.json` → `config.local.json` 覆盖 → 环境变量注入敏感字段。

### 敏感凭证：`.env`（可选，gitignored）

只有配了飞书推送才用到。见下文[飞书推送](#飞书推送可选)一节。

---

## 状态与打分语义

### 题目状态

| 标签 | 含义 | 何时进入 |
|------|------|----------|
| ⚪ `todo` | 未刷 | 初始状态 |
| 🔴 `forgot` | 思路忘 / 卡住 | 复习点 😩 卡住，或首刷标"卡住" |
| 🟡 `shaky` | 磕绊 / 语法忘 | 复习点 🙂 磕绊，或首刷标"磕绊" |
| 🟢 `solid` | 稳，进复习后段 | 复习点 😄 秒 A，或首刷标"很稳" |
| 📦 `archived` | 归档，不再复习 | 档位跑满 5 档后自动归档 |

### 复习打分

- **秒 A** → 档位 +1，间隔拉长
- **磕绊** → 保持当前档，隔天再见
- **卡住** → 档位归 0，明天从头来

打分不满意可以在 2 秒淡出窗口内点撤销 / 换选择（见[核心功能 → 状态改动的 2 秒可撤销](#-状态改动的-2-秒可撤销)）。

---

## 文件与数据布局

```
leetcode-hot100/
├── app.py                       # Flask 主入口：路由 + 看板计算 + 遗忘曲线 + SM-2 前向模拟
├── config.json                  # 公开配置
├── config.local.json            # (gitignored) 本地覆盖
├── .env / .env.example          # (.env gitignored) 飞书凭证
├── data/
│   ├── problems.json            # hot100 题目分类数据（17 大类）
│   ├── cheatsheet.md            # 全局 Python 语法速查
│   ├── progress.json            # 空 seed（公开）
│   └── progress.local.json      # (gitignored) 你的真实刷题进度
├── solutions/                   # 各语言目录（.gitkeep 保结构，代码文件 gitignored）
│   ├── python/  └─ 001_两数之和.py  ...
│   ├── go/
│   ├── cpp/
│   └── java/
├── templates/                   # Jinja2 模板
│   ├── base.html                # 顶栏 + 页面骨架
│   ├── dashboard.html           # Today
│   ├── preview.html             # 未来 30 日预告
│   ├── problems.html            # 全部题目 · 分类表格 + 状态筛选
│   ├── problem_detail.html      # 详情页
│   ├── calendar.html            # Calendar 日历
│   ├── cheatsheet.html          # per-problem cheatsheet 索引
│   └── cheatsheet_global.html   # 全局 cheatsheet 编辑器
├── static/
│   ├── style.css                # 手账风格样式表
│   ├── app.js                   # 主交互：状态改动 / 复习 / 笔记 / 代码
│   ├── checkin.js               # 打卡卡片
│   ├── cheat.js / cheatsheet_inline.js / note_inline.js
├── scripts/
│   ├── feishu_daily.py          # 飞书推送脚本（图片模式 + webhook fallback）
│   ├── render_checkin.py        # 打卡卡片 PNG 渲染（playwright）
│   ├── export_notes.py          # 导出人类可读 study-notes.md
│   ├── daily_autocommit.sh      # 每晚自动 git commit + push
│   ├── sync_personal_data.sh    # 私人数据分支同步
│   ├── *.launchd.plist          # macOS 定时任务
│   └── build_mac_app.sh         # 打包 macOS .app 图标启动器
└── requirements.txt
```

### 隐私架构

**这是一个模板仓库**：核心逻辑、题目数据、cheatsheet 模板都上传公开；**你的私人刷题进度、代码、飞书凭证不进 git**。

| 文件 | 进 git | 说明 |
|------|--------|------|
| `app.py` / `templates/` / `static/` | ✅ | 代码 |
| `data/problems.json` | ✅ | hot100 题目数据 |
| `data/cheatsheet.md` | ✅ | 全局语法模板 |
| `config.json` | ✅ | 公开配置 |
| `data/progress.json` | ✅（空）| 克隆种子 |
| **`data/progress.local.json`** | ❌ | 你的真实进度、思路、per-problem cheatsheet |
| **`.env`** | ❌ | 敏感凭证（飞书）|
| **`config.local.json`** | ❌ | 本地覆盖（可选）|
| **`solutions/*/[0-9]*.{py,go,cpp,java}`** | ❌ | 你的题解代码（`.gitkeep` 保留目录）|

`app.py` 读取顺序：`.env`（敏感字段）→ `config.local.json`（非敏感覆盖）→ `config.json`（默认）。

**Fork 建议**：如果你也想把自己的 fork 公开分享，请沿用这套架构，别把 `progress.local.json` 或 `config.local.json` 提交上去。

---

## 飞书推送（可选）

字节 / 飞书用户可以配置每天早上自动推送打卡卡片到飞书群。**其他公司或个人用户可跳过这节**。

### 两种模式

推送脚本 `scripts/feishu_daily.py` 支持两条路径，按顺序 fallback：

1. **图片模式**（推荐）：playwright 渲染 PNG 打卡卡片 → 上传飞书 → 发 image 消息
   - 需要飞书**自建应用**的 `APP_ID + APP_SECRET`，以及 `TARGET_CHAT` chat_id
   - 需要装 `playwright` 依赖（默认已在 requirements.txt）
2. **文本 webhook 模式**（老路径）：格式化文本消息 → 走自定义机器人 webhook
   - 只需要飞书**群机器人**的 `webhook URL` + `secret`

**推荐用图片模式** —— 视觉效果好，且自建应用比群机器人 API 权限更完整。

### 配置步骤

1. 复制模板：

   ```bash
   cp .env.example .env
   ```

2. 编辑 `.env`，按你选的模式填对应变量：

   ```bash
   # 图片模式（推荐）—— 需要飞书开放平台建自建应用
   FEISHU_APP_ID=cli_xxxxxxxx
   FEISHU_APP_SECRET=xxxxxxxxxxxxxxxx
   FEISHU_TARGET_CHAT=oc_xxxxxxxxxxxxxxxxxxxxxxxxxxxx

   # webhook 模式（简单）—— 群机器人
   FEISHU_WEBHOOK=https://open.larkoffice.com/open-apis/bot/v2/hook/YOUR_HOOK_ID
   FEISHU_SECRET=YOUR_SECRET
   ```

   **两种都填也行**，图片模式失败会自动 fallback 到 webhook。

3. 安装 playwright 浏览器（仅图片模式需要，第一次装完永久生效）：

   ```bash
   .venv/bin/playwright install chromium
   ```

4. 手动测一发：

   ```bash
   .venv/bin/python scripts/feishu_daily.py
   ```

   飞书群里应该收到一张打卡图片（或文本消息）。

### 用其他 IM？

飞书脚本简明可改，见 [scripts/feishu_daily.py](scripts/feishu_daily.py)。改成 Slack / Telegram / DingTalk / Email 都不难 —— 主要就是签名和 payload 格式。**欢迎 PR**。

---

## 定时任务（可选，macOS）

macOS 用 launchd 挂两个定时任务：

```bash
# 每天早 09:00 推送打卡卡片到飞书
cp scripts/feishu_daily.launchd.plist    ~/Library/LaunchAgents/com.wyt.leetcode-hot100.feishu.plist

# 每晚 22:00 自动 git commit + push 到你自己的 GitHub fork
cp scripts/daily_autocommit.launchd.plist ~/Library/LaunchAgents/com.wyt.leetcode-hot100.autocommit.plist

launchctl load ~/Library/LaunchAgents/com.wyt.leetcode-hot100.feishu.plist
launchctl load ~/Library/LaunchAgents/com.wyt.leetcode-hot100.autocommit.plist
```

⚠️ plist 里绝对路径 `/Users/bytedance/leetcode-hot100/...` 需要改成你自己的，`daily_autocommit.sh` 里 SSH agent socket 路径也可能要调。

停止：

```bash
launchctl unload ~/Library/LaunchAgents/com.wyt.leetcode-hot100.feishu.plist
launchctl unload ~/Library/LaunchAgents/com.wyt.leetcode-hot100.autocommit.plist
```

**Linux 用户** —— 用 cron / systemd timer 类比即可，逻辑就是"每天早上跑一次 `python scripts/feishu_daily.py`"。**Windows** —— Task Scheduler。

---

## 常见问题

**Q：一定要每天都刷吗？间隔不刚好会打乱吗？**
A：不会。到期日的判定是 `next_review ≤ 今天`，不是 `== 今天`。昨天没做的今天还在，前天没做的也还在。逾期超过 3 天会飘红警告，你可以点"推迟全部"批量顺延。**推迟不惩罚档位**。

**Q：我以前刷过一部分了，怎么标进度？**
A：默认全部标"未刷"。以自然节奏往下推，重逢老朋友时看题名如果记得就当场标 🟢/🟡/🔴。或者在"全部题目"页手动一批一批改状态。

**Q：为什么 solid 状态也要复习？**
A：遗忘曲线的本质是"越不复习忘得越快"，solid 只是间隔更长（+15、+30 天），不是永久免疫。

**Q：hot100 的分类和题目数据能改吗？**
A：可以。[data/problems.json](data/problems.json) 结构简单，加题、改分类、改难度都行。改完刷新页面即可，无需重启。

**Q：Windows 上能跑吗？**
A：核心 Flask 应用能跑（Python 跨平台）。飞书 launchd 定时那部分是 macOS 独有的，Windows 上得用 Task Scheduler 替换（欢迎 PR）。

**Q：想改遗忘曲线间隔？**
A：改 [config.json](config.json) 里 `review_intervals_days` 数组，或者顶栏齿轮设置 modal 里直接改。

- 更陡（激进遗忘）：`[1, 2, 5, 12, 30]`
- 更平（保守）：`[2, 5, 10, 20, 45]`
- 更多档（Anki 风）：`[1, 2, 4, 7, 14, 30, 60]`

改完立即生效，不用重启（每次读 config 都是热加载）。

**Q：点错状态怎么办？**
A：看板卡片打分有 **2 秒淡出撤销窗口** —— 再点同一按钮撤销，点别的按钮换选择。已经提交过的状态可以在"全部题目"页把状态改回"未刷"（会重置该题所有进度）。

**Q：数据备份？**
A：`data/progress.local.json` 是纯 JSON，随便备份到哪都行（网盘 / iCloud / 私有 git 分支）。仓库自带的 `scripts/sync_personal_data.sh` 就是一个方案：把私人数据推到自己的 `data-<user>` 分支（force-push，覆盖式快照）。

---

## Roadmap

- [ ] 全部题目页加搜索框
- [ ] 状态过滤器保存到 URL / localStorage
- [ ] 进度可视化增强（月度热力图、每周走势）
- [ ] 支持导入自己的题库（LeetCode 精选 200、剑指 offer、自定义题单）
- [ ] Slack / Telegram / DingTalk / Email 推送脚本
- [ ] Windows Task Scheduler 支持
- [ ] Docker 化
- [ ] AI 提示（分级提示 / 代码点评 / cheatsheet 自动生成）—— 走 Anthropic Claude / OpenAI / Volcengine Ark 均可

**欢迎 PR。**

---

## 贡献

- **Issue** 报 bug / 提 feature，尽量给复现步骤和期望行为
- **PR** 建议先开 issue 讨论方向，再动手
- **代码风格**：跟着现有代码走，Python 无强制 formatter，JS 无 build step（原生 vanilla），CSS 手写
- **Commit message** 走 conventional commits：`feat(scope): message` / `fix(scope): message` / `chore: ...`

---

## License

[MIT](LICENSE)

---

## 致谢

- 灵感来源：[Anki](https://apps.ankiweb.net/) 的 SM-2 算法（简化后适配刷题场景）
- 题目分类沿用 [LeetCode 官方"热题 100"学习计划](https://leetcode.cn/studyplan/top-100-liked/) 的 17 大类
- Cheatsheet 内容基于长期刷题的踩坑积累

如果这个工具对你有帮助，欢迎 **star ⭐ / fork / PR**。
