# 自定义题目（Custom Problems）设计

**日期**: 2026-07-30
**作者**: 雨桐（brainstorm w/ Claude）
**目标**: 在现有 Hot100 刷题系统上，允许用户**添加**自定义题目、并对自定义题**软删**；官方 100 道题保持只读。

---

## §0 术语

- **官方题** (`official`)：`data/problems.json` 里的 100 道，来自公共 seed，不可删。
- **自定义题** (`custom`)：新增文件 `data/problems.custom.local.json` 里的题，可软删；数据只在本机，进 `.gitignore`。

---

## §1 存储与数据模型

### 1.1 新增文件

`data/problems.custom.local.json`（**加入 `.gitignore`**），结构：

```json
{
  "categories": [
    {
      "name": "自定义",
      "problems": [
        {
          "id": 10001,
          "title": "找茬题",
          "difficulty": "中等",
          "url": "https://leetcode.cn/problems/xxx/",
          "desc": "补充说明,选填",
          "custom": true,
          "deleted": false,
          "created_at": "2026-07-30"
        }
      ]
    }
  ],
  "next_id": 10002
}
```

**字段约定**:

| 字段 | 类型 | 说明 |
|---|---|---|
| `id` | int | 自增,从 `10001` 起;规避力扣真实题号(目前 3000 出头) |
| `title` | str | 必填 |
| `difficulty` | enum | `简单` / `中等` / `困难`,必填,默认「中等」 |
| `url` | str \| null | 题目来源链接,选填;前端 `↗` 直接跳它 |
| `desc` | str \| null | 备注,选填 |
| `custom` | bool | 恒为 `true`,读时由 loader 强制打上,写时也存下来 |
| `deleted` | bool | 软删标记,默认 `false` |
| `created_at` | str (ISO date) | 创建当天日期,YYYY-MM-DD |
| `next_id` (顶层) | int | 下一个可用 ID,避免每次扫全表求 max |

**没有 `slug`**——`slug` 是官方题拼力扣 URL 用的;自定义题用完整 `url`,前端跳链逻辑分岔一次(见 §3.4 前端模板)。

### 1.2 分类归属

自定义题**永远且只**属于「自定义」分类。这个分类只存在于 `problems.custom.local.json` 里;`problems.json` 不动。渲染时把这个分类**拼在**官方 17 类**后面**,排在页面最下方。

### 1.3 已删除题的处理

- 删除 = 把该题的 `deleted` 从 `false` 改成 `true`,不做真删。
- 所有对外读取路径(题库页、dashboard、复习、日历、打卡、cheatsheet、preview、bot API 等)一律**过滤掉 `deleted == true`**。
- **不做**回收站页面 / 恢复入口。软删的意义是让 `progress.local.json` 里的孤儿 entry(状态、笔记、复习历史)能通过 id 追回来,而不是让用户能翻回题。
- 若「自定义」分类下**全部题都被软删或没题**,题库页**不渲染**这个 section(避免空 section 视觉噪音)。

### 1.4 进度 / 笔记 / 复习数据

- 完全**复用** `progress.local.json`,key = `str(id)`,和现在官方题一模一样(`"1"`, `"10001"` 是同类)。
- 删除自定义题时**不动** `progress.local.json`——孤儿 entry 会留下。用户第 6 个问题选择的就是这个行为(选项 C)。

---

## §2 业务规则

### 2.1 一视同仁原则

除「能否删除」外,自定义题与官方题**完全相同**:

| 场景 | 行为 |
|---|---|
| Dashboard 分母(已刷 X / 总数) | 分母 = 100 + 未删除自定义题数 |
| 每日 quota / 复习队列 / next_review | 一视同仁进队列 |
| `/calendar`、打卡卡片 | 全量参与 |
| `/cheatsheet` / `/cheatsheet/global` | 全量参与 |
| `/preview`、`api_checkin`、`api_dashboard` | 全量参与 |
| 状态修改、复习打分、写笔记、写 cheatsheet | 全部支持 |
| 关联本地代码文件(`code_file`,`api_open_code`) | 支持;文件名规则 `solutions/{lang}/{id}_{title}.{ext}`,和官方题一致 |

一句话:后端所有走 `load_problems()` 的地方,合并后的 flat list **自动**包含自定义题;不需要在每个消费点写特殊逻辑。

### 2.2 只读保护

- **官方题不可删**:后端删除 API 收到 `id ∈ 官方题库` 时返回 400 `{"error": "official problem cannot be deleted"}`。
- **官方题库 `problems.json` 永不被写**:所有写操作只落在 `problems.custom.local.json`。

### 2.3 ID 分配

- 首次写自定义题库时,若 `next_id` 缺失,取 `max(10000, 现有所有 custom id) + 1` 作为起点。
- 每次新增题时,取当前 `next_id` 作为新题 ID,然后 `next_id += 1`,一起持久化。
- ID 一旦分配**永不复用**——即使该题被软删。

### 2.4 分类冲突

自定义题的分类固定叫 `自定义`。若未来官方 `problems.json` 里出现同名分类(不太可能,但保险起见),合并时**不合并两个 section**,自定义 section 永远独立追加在末尾,标题就叫「自定义」。若视觉需要区分,可以给这个 section 加一个 `data-custom="true"` 的属性,前端 CSS 单独装饰(可选)。

---

## §3 API 与后端改动

### 3.1 数据加载层(`app.py`)

新增常量:

```python
PROBLEMS_CUSTOM_PATH = DATA_DIR / "problems.custom.local.json"
CUSTOM_ID_START = 10001
CUSTOM_CATEGORY_NAME = "自定义"
```

新增函数:

```python
def load_custom_problems() -> dict:
    """读自定义题库文件;不存在则返回空壳。永不 write 到磁盘除非用户真新增。"""
    return load_json(PROBLEMS_CUSTOM_PATH, {"categories": [{"name": CUSTOM_CATEGORY_NAME, "problems": []}], "next_id": CUSTOM_ID_START})

def save_custom_problems(data: dict) -> None:
    save_json(PROBLEMS_CUSTOM_PATH, data)

def _alive_custom_problems() -> list[dict]:
    """未软删的 custom 题,已打上 custom=True。"""
    data = load_custom_problems()
    return [{**p, "custom": True} for p in data["categories"][0]["problems"] if not p.get("deleted")]
```

**改造** `load_problems()` 与 `load_categories()`:合并官方 + 未删的自定义,`custom` 字段透传。官方题在返回时补 `custom: False`。

### 3.2 CRUD API

| Method | Path | Body / 说明 |
|---|---|---|
| `POST` | `/api/custom-problem` | `{"title": str, "category": "自定义", "difficulty": "简单"\|"中等"\|"困难", "url"?: str, "desc"?: str}`;返回新题完整字段。分类字段实际忽略(永远归自定义),但前端仍然传,为未来扩展留口子 |
| `DELETE` | `/api/custom-problem/<int:pid>` | 软删;若 pid 是官方题返回 400;若 pid 不存在或已 `deleted` 返回 404 |

**服务端校验**:

- `title`: 非空,`strip()` 后 ≤ 200 字符
- `difficulty`: 必须 ∈ `{"简单", "中等", "困难"}`
- `url`: 若非空,基础 URL 格式(`https?://`),否则拒绝
- `desc`: 长度 ≤ 2000 字符
- **并发写**:目前系统是单进程 Flask debug 模式,不做文件锁;`save_json` 现有实现是**读–改–写**(非原子),但 CRUD 操作触发频率极低,忽略并发。若未来切多进程,`save_json` 统一改成 atomic write(临时文件 + rename)——**不属于本次 scope**。

### 3.3 兼容性:官方题只读保护

- `DELETE /api/custom-problem/<pid>` 收到官方 ID(即在 `problems.json` 的 categories 里能找到的):`400 {"error": "official problem cannot be deleted"}`。
- 前端也不给官方题渲染 🗑 按钮(见 §4);后端 400 是双重防线。

### 3.4 前端跳链模板

现在 `problems.html` 里跳链是硬编码 `https://leetcode.cn/problems/{{ p.slug }}/`。要改成:

```jinja
{% if p.custom %}
  {% if p.url %}<a href="{{ p.url }}" target="_blank" rel="noopener" class="lc-link" title="题目链接">↗</a>{% endif %}
{% else %}
  <a href="https://leetcode.cn/problems/{{ p.slug }}/" target="_blank" rel="noopener" class="lc-link" title="在力扣打开">↗</a>
{% endif %}
```

自定义题若没填 `url` 就**不显示** `↗`。

`problem_detail.html`(题目详情页)同样处理。

---

## §4 前端 / UI

### 4.1 `/problems` 页新增控件

**A. 顶部「+ 添加题目」按钮**

放在现有 `.filters` 行右侧(或紧跟其后),按钮样式复用现有 `.btn` 类(不是 ghost)。点击 → 弹 modal。

**B. 添加题目 modal**

复用 `.modal-backdrop / .modal / .modal-head / .modal-body / .modal-foot`(settings modal 已经用过一套,直接复用)。字段:

| 字段 | 控件 | 校验 |
|---|---|---|
| 题名 * | `<input type="text">` | 必填,前端也做非空 |
| 难度 * | `<select>` 三选 | 默认「中等」 |
| 题目链接 | `<input type="url" placeholder="https://…">` | 选填 |
| 备注 | `<textarea rows=3>` | 选填 |

分类字段**不出现在 UI 上**——固定「自定义」;等未来真的需要选分类时再加。

Footer:`取消` / `保存`。保存成功后:关闭 modal → 局部插入新分类 section 或新行(若「自定义」section 已存在则往里插一行,否则**整个页面刷新**避免复杂 DOM 操作)。

**C. 自定义题行的删除按钮**

在 `templates/problems.html` 的操作列末尾加:

```jinja
{% if p.custom %}
  <button class="btn ghost cp-del" data-pid="{{ p.id }}" title="删除自定义题">🗑</button>
{% endif %}
```

点击 → `confirm("删除这道自定义题?题的进度/笔记会保留但从题库中隐藏。")` → 通过则 `DELETE /api/custom-problem/{pid}` → 成功后**移除该行 DOM**(不刷页)。若这是「自定义」分类下最后一道未删的题,把整个 section 也移除。

### 4.2 JS(`static/app.js`)

新增以下事件绑定:

1. `#btn-add-problem` click → 打开 modal
2. Modal 保存 button click → `POST /api/custom-problem` → 成功刷新或局部插入
3. `.cp-del` click(事件委托) → confirm → `DELETE` → 移除 DOM

### 4.3 视觉细节(不阻塞)

- 自定义题行可加一个 `data-custom="true"` 属性,便于未来加特殊装饰(比如题号旁一个小 `✎` 图标)。**第一版不加装饰**,只做功能。
- 「自定义」section 的 `.cat-count` 显示未删数量。

---

## §5 影响面 / 需要检查的点

| 位置 | 需要动吗 |
|---|---|
| `load_problems()` / `load_categories()` | ✅ 合并 custom |
| `problems.html` 跳链 | ✅ 按 `p.custom` 分岔 |
| `problems.html` 操作列 | ✅ 加 🗑(仅 custom) |
| `problems.html` 顶部 | ✅ 加「+ 添加题目」按钮 |
| `app.js` | ✅ 新增 modal / 保存 / 删除逻辑 |
| `style.css` | 复用 `.modal-*`,不新增样式,除非发现空白 |
| `.gitignore` | ✅ 加 `data/problems.custom.local.json` |
| Dashboard / calendar / cheatsheet / preview / checkin / bot API | ❌ 无需改;它们全部走 `load_problems()`,合并后自动包含 |
| `progress.local.json` | ❌ 结构不变,key 仍是 `str(id)` |
| Review / postpone / status API | ❌ 已经 `str(pid)` 索引,自动兼容 10001+ |
| `<int:pid>` 路由 | ❌ 保留 int,10001 仍是 int |

---

## §6 测试计划(手工验收)

1. 空 custom 文件下加载 `/problems`——页面正常,只有 17 分类,没有「自定义」section。
2. 通过 UI 新增一道题(填标题+难度)——顶部按钮 → modal → 保存,页面出现「自定义」section 和这道题。
3. 新增题**不填** URL——行里没有 `↗` 图标。
4. 新增题填了 URL——`↗` 跳该 URL。
5. 对自定义题标状态、写笔记、写 cheatsheet、复习打分——`progress.local.json` 里 key = 该题 ID 的 entry 正常生成/更新。
6. Dashboard 已刷计数分母 = 100 + 未删自定义题数。
7. Calendar / cheatsheet / preview / 打卡卡片——都能看到自定义题。
8. 删除一道自定义题——confirm 后消失,行 DOM 从表中移除;`problems.custom.local.json` 里该题 `deleted: true`;`progress.local.json` 里孤儿 entry 保留。
9. 删完自定义分类下所有题——「自定义」section 消失。
10. 试图 `DELETE /api/custom-problem/1`(官方题)——返回 400。
11. 试图 `POST /api/custom-problem` 空标题——返回 400。
12. `next_id` 单调递增,即使删了题也不复用。
13. 复习 due 时,自定义题会跟官方题一样出现在推荐/日历里。

---

## §7 非目标(明确不做)

- 编辑自定义题的元数据(改标题/难度/URL/备注)——第一版只做「增」和「删」,改字段以后另开工单。
- 回收站 / 恢复删除的题——软删只为保住孤儿进度数据,不给用户视觉入口。
- 官方题的元数据修改。
- 自定义分类的自定义命名(第 4 个问题选了固定「自定义」分类)。
- 多进程并发写的原子性保证。
- 自定义题的图片附件、markdown 描述预览等富交互。
