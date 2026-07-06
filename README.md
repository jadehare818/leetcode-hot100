# LeetCode Hot 100 Tracker

一个本地跑的 LeetCode 热题 100 刷题追踪器：**动态每日看板 + 遗忘曲线复习 + 多语言代码归档**，可选**飞书每日推送**。

用 Python + Flask 搭的单机 web 应用，数据全部落 JSON 文件，**没有数据库、没有账号系统、没有云端依赖**。开箱一条命令启动，浏览器打开就能用。

<img alt="dashboard" src="https://img.shields.io/badge/python-3.10%2B-blue"> <img alt="license" src="https://img.shields.io/badge/license-MIT-green"> <img alt="stack" src="https://img.shields.io/badge/stack-Flask%20%2B%20JSON-lightgrey">

---

## 为什么做这个

刷 hot100 的三种典型痛点：

1. **一部分题思路记得，但 Python 语法忘了**（`sorted(key=...)` / `defaultdict` / `heapq` / `bisect` 一停手就想不起来）
2. **一部分复杂题（DP、回溯）思路完全忘了**
3. **还有一部分从没刷过**

市面上的题库/OJ 平台不太对症 —— 它们只记录"你做没做过"，不管**你现在还记不记得**。刷过的题隔一个月就忘光；每天进 leetcode 又不知道该刷新题还是复习。

这个工具解决的核心问题：**帮你把"该刷的新题"和"该复习的老题"合并成一个每日看板**，按遗忘曲线自动调度。你只管点开看今天要做什么。

---

## 特性

### 🎯 动态每日看板

每天进页面时**现算**今天要做什么 —— 不是提前排好的表，而是：

```
今日看板 = 到期复习题（next_review ≤ today）+ 未刷池按配额抽新题
```

一时兴起多刷几道 → 后续新题配额自动变少
今天犯懒没刷 → 到期题第二天还在，堆积会飘红警告

**新题挑选还会尝试难度均衡**，不会一天全给简单题、一天全给困难题。默认工作日 3 道（1 简 + 1 中 + 1 困）、周末 6 道（2 简 + 3 中 + 1 困）。

### 🔁 遗忘曲线复习（简化 SM-2）

每题有个"复习档位"，五档：**+1 → +3 → +7 → +15 → +30 天**。

复习完打分：
- 😄 **秒 A** → 前进一档（间隔拉长）
- 🙂 **磕绊** → 保持当前档
- 😩 **卡住** → 回退到档 0（明天再见）

一道题至少要过 5 面才归档（1+3+7+15+30 = 56 天）；中间任何一次卡住又重来。间隔可在 [config.json](config.json) 里改。

### 💪 加练池

今日目标之外多推 10 道未刷题，作为"想再来几道？"的加餐区。有空就顺手多刷，没空就当没看见。

### 📝 多语言代码归档

Python / Go / C++ / Java 各自一个目录（`solutions/<lang>/`），右上角下拉切换。

**目的不是本地跑代码**，是让你不用点开 leetcode 也能查看自己以前写过的代码。切换语言不删已有文件，四种语言的题解各自独立保存。

### 💡 思路 + 📝 Cheatsheet

每题两个字段：
- **思路**（`note`）：短，一两句话记关键 idea
- **Cheatsheet**（`cheatsheet`）：markdown 支持代码块，记这题涉及的语法/套路

三处入口全打通：**看板卡片** / **全部题目表格** / **详情页**，都能内联展开编辑。看板卡片上如果有思路会直接显示摘要，60 字截断。

另有一份**全局 Cheatsheet**（[data/cheatsheet.md](data/cheatsheet.md)），预置 15+ 个高频 Python 语法 section（`sorted` / `defaultdict` / `heapq` / `bisect` / `deque` / `itertools` / DP 模板 / 回溯模板 / 位运算 / 字符串技巧 / 常见坑等），可在网页里编辑。

### 📅 逾期批量处理

出差 / 忙一周回来看到一屏逾期题？"今日复习"标题右侧有两个按钮：
- **推迟全部** —— 到期的都推到明天
- **仅推迟逾期** —— 只推超过 3 天没做的

推迟只改 `next_review`，**不动档位**，间隔曲线不受惩罚。

### 🤖 飞书自定义机器人推送（可选）

配置飞书自建群机器人的 webhook 后，每天早上定时把今日看板推到你的飞书群。见下方"[飞书推送配置](#飞书推送配置可选)"。

---

## 技术栈 & 目录结构

- **后端**：Python 3.10+ + Flask
- **前端**：原生 HTML/CSS/JS + [marked](https://marked.js.org/) 渲染 markdown（CDN 加载）
- **存储**：JSON 文件，没有数据库
- **依赖**：`pip install flask`（就这一个）

```
leetcode-hot100/
├── app.py                       # Flask 主入口，路由 + 看板计算 + 遗忘曲线
├── config.json                  # 公开配置：配额、间隔、语言、端口
├── config.local.json.example    # 你复制成 config.local.json 填敏感字段
├── data/
│   ├── problems.json            # hot100 题目分类数据
│   ├── progress.json            # 空 seed，克隆下来 fork 用
│   ├── progress.local.json      # (gitignored) 你的真实刷题进度
│   └── cheatsheet.md            # 全局 Python 语法速查
├── solutions/                   # 各语言目录（.gitkeep 保结构，代码文件 gitignored）
│   ├── python/
│   ├── go/
│   ├── cpp/
│   └── java/
├── templates/                   # Jinja2
├── static/                      # CSS + JS
├── scripts/
│   ├── feishu_daily.py          # 飞书推送脚本
│   ├── feishu_daily.launchd.plist    # macOS 定时（每天 09:00 推送）
│   ├── daily_autocommit.sh      # 每晚自动 git commit + push
│   └── daily_autocommit.launchd.plist
└── README.md
```

---

## 快速上手

### 1. 克隆 & 安装

```bash
git clone https://github.com/jadehare818/leetcode-hot100.git
cd leetcode-hot100

python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
```

需要 Python **3.10+**（用了 `dict[str, list]` 之类的类型标注）。

### 2. 起服务

```bash
.venv/bin/python app.py
```

浏览器访问 [http://localhost:5001](http://localhost:5001) 即可开刷。

### 3.（可选）改端口 / 配额 / 间隔

编辑 [config.json](config.json)：

```json
{
  "daily_quota": {"weekday": 3, "weekend": 6},
  "review_intervals_days": [1, 3, 7, 15, 30],
  "overdue_alert_days": 3,
  "port": 5001,
  "languages": ["python", "go", "cpp", "java"],
  "default_language": "python"
}
```

---

## 状态语义

| 标签 | 含义 | 何时进入 |
|---|---|---|
| ⚪ `todo` | 未刷 | 初始状态 |
| 🔴 `forgot` | 思路忘 / 卡住 | 复习点 😩 卡住，或首刷标"忘" |
| 🟡 `shaky` | 磕绊 / 语法忘 | 复习点 🙂 磕绊，或首刷标"磕绊" |
| 🟢 `solid` | 稳，进复习后段（起始档 1）| 复习点 😄 秒A，或首刷标"稳" |
| 📦 `archived` | 归档，不再复习 | 档位超过最大档后自动归档 |

---

## 隐私架构

**这是一个模板仓库**：核心逻辑、题目数据、cheatsheet 模板都上传公开；**你的私人刷题进度、代码、飞书凭证不进 git**。

设计如下：

| 文件 | 是否进 git | 说明 |
|---|---|---|
| [app.py](app.py) / [templates/](templates/) / [static/](static/) | ✅ | 代码 |
| [data/problems.json](data/problems.json) | ✅ | hot100 题目分类数据 |
| [data/cheatsheet.md](data/cheatsheet.md) | ✅ | 全局语法模板 |
| [config.json](config.json) | ✅ | 公开配置：配额、间隔、语言 |
| **[data/progress.json](data/progress.json)** | ✅（空 seed）| 上传时是 `{}`，作克隆种子 |
| **`data/progress.local.json`** | ❌ | 你的真实进度、思路、per-problem cheatsheet |
| **`.env`** | ❌ | 敏感凭证（飞书 webhook / secret）|
| **`config.local.json`** | ❌ | 覆盖 `config.json` 的非敏感字段（可选，多数人不需要）|
| **`solutions/*/[0-9]*.{py,go,cpp,java}`** | ❌ | 你的题解代码（`.gitkeep` 保留目录）|

`app.py` 的 `load_config()` 会**优先读 `.env`（敏感字段）+ `config.local.json`（非敏感覆盖）+ `config.json`（默认）**。你 fork 后：

1. 直接用即可 —— local 文件在你首次改状态时自动创建
2. 想要飞书推送就 `cp .env.example .env` 填入 webhook

**Fork 建议**：如果你也想把自己的 fork 公开分享，请沿用这套架构，别把 `progress.local.json` 或 `config.local.json` 提交上去。

---

## 飞书推送配置（可选）

字节 / 飞书用户可以配置每天早上自动推送今日看板到飞书群。**其他公司或个人用户可跳过这节**。

### 步骤

1. 飞书群 → 群设置 → 群机器人 → 添加 **自定义机器人**
2. 勾选"签名校验"（推荐），拿到 `webhook URL` + `secret`
3. 复制模板文件并填入：

   ```bash
   cp .env.example .env
   # 编辑 .env，填入 FEISHU_WEBHOOK 和 FEISHU_SECRET
   ```

4. 手动测一发：

   ```bash
   .venv/bin/python scripts/feishu_daily.py
   ```

   飞书群里应该收到一条今日看板消息。

### macOS 定时推送（launchd）

每天早上 09:00 自动推送 + 每晚 22:00 自动 commit + push 到你自己的 GitHub fork：

```bash
cp scripts/feishu_daily.launchd.plist    ~/Library/LaunchAgents/com.wyt.leetcode-hot100.feishu.plist
cp scripts/daily_autocommit.launchd.plist ~/Library/LaunchAgents/com.wyt.leetcode-hot100.autocommit.plist
launchctl load ~/Library/LaunchAgents/com.wyt.leetcode-hot100.feishu.plist
launchctl load ~/Library/LaunchAgents/com.wyt.leetcode-hot100.autocommit.plist
```

⚠️ plist 里绝对路径 `/Users/bytedance/leetcode-hot100/...` 需要改成你自己的路径，`daily_autocommit.sh` 里 SSH agent socket 路径也可能要调。

停止：

```bash
launchctl unload ~/Library/LaunchAgents/com.wyt.leetcode-hot100.feishu.plist
launchctl unload ~/Library/LaunchAgents/com.wyt.leetcode-hot100.autocommit.plist
```

### 用其他 IM？

飞书脚本很短，见 [scripts/feishu_daily.py](scripts/feishu_daily.py)。改成 Slack / Telegram / DingTalk / 邮件都不难 —— 主要就是签名和 payload 格式。欢迎 PR。

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
A：改 [config.json](config.json) 里 `review_intervals_days` 数组。

- 更陡（激进遗忘）：`[1, 2, 5, 12, 30]`
- 更平（保守）：`[2, 5, 10, 20, 45]`
- 更多档（Anki 风）：`[1, 2, 4, 7, 14, 30, 60]`

改完立即生效，不用重启（每次读 config 都是热加载）。

---

## Roadmap（欢迎 PR）

- [ ] 状态过滤器保存到 URL / localStorage
- [ ] 全部题目页面加搜索框
- [ ] 进度可视化（热力图、每日打卡曲线）
- [ ] 支持导入自己的题库（不止 hot100）
- [ ] Windows Task Scheduler 支持
- [ ] Slack / Telegram / DingTalk 推送脚本
- [ ] Docker 化

---

## License

[MIT](LICENSE)

---

## 致谢

- 灵感来源：Anki 的 SM-2 算法（简化后适配刷题场景）
- 题目分类沿用 [LeetCode 官方"热题 100"学习计划](https://leetcode.cn/studyplan/top-100-liked/) 的 17 大类
- Cheatsheet 内容基于长期刷题的踩坑积累

如果这个工具对你有帮助，欢迎 star ⭐ / fork / PR。
