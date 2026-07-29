# 自定义题目 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 让用户从 `/problems` 页新增自定义题目并软删,官方 100 道题保持只读。

**Architecture:** 新增私有文件 `data/problems.custom.local.json` 存储自定义题(不进 git);后端 loader 合并官方 + 未软删的自定义,前端所有下游消费点自动包含。CRUD 通过两条 REST API:`POST /api/custom-problem` 新增、`DELETE /api/custom-problem/<pid>` 软删。UI 复用现有 `.modal-*` 样式。

**Tech Stack:** Flask (Python 3.9+ 系统解释器,`app.py` 单文件后端)、Jinja2、原生 JS(`static/app.js`)、无测试框架(手工 curl + 页面回归)。

## Global Constraints

- 官方题库 `data/problems.json` **永远不被写**——所有写操作只落 `data/problems.custom.local.json`。
- 自定义题 ID 起点 `CUSTOM_ID_START = 10001`,单调递增,永不复用。
- 分类固定 `CUSTOM_CATEGORY_NAME = "自定义"`,拼在官方 17 类**后面**。
- 软删标记 `deleted: true`;所有读路径过滤该字段;不做回收站/恢复入口。
- `progress.local.json` 结构不动,key 仍是 `str(id)`。
- 删除自定义题时**不动** progress 数据(留孤儿 entry)。
- 官方题 = `problems.json` 里 ID 集合,收到 DELETE 该集合内的 pid 返回 400。
- `save_json` 已是 atomic write(tmp + rename),沿用即可。
- Spec: `docs/superpowers/specs/2026-07-30-custom-problems-design.md`。

---

## File Structure

| 文件 | 动作 | 责任 |
|---|---|---|
| `data/problems.custom.local.json` | 由代码首次写入自动创建 | 自定义题存储;进 .gitignore |
| `.gitignore` | Modify | 加一行 `data/problems.custom.local.json` |
| `app.py` | Modify | 新增 loader / 保存函数 / CRUD API;改造 `load_problems` / `load_categories` |
| `templates/problems.html` | Modify | 顶部 + 添加按钮、Modal、跳链模板分岔、🗑 按钮 |
| `static/app.js` | Modify | Modal 开关、保存请求、删除请求、DOM 局部更新 |
| `static/style.css` | 复用现有 `.modal-*` | 不新增样式 |
| `templates/problem_detail.html` | Modify | 跳链模板分岔(和 problems.html 一致) |

**任务粒度切分**:5 个任务,一个任务一次 commit:

1. `.gitignore` + 后端 loader / 合并层
2. 后端 CRUD API + 校验
3. `problems.html` 跳链模板分岔(小改)+ `problem_detail.html` 同步
4. `problems.html` 顶部按钮 + Modal + 🗑 按钮
5. `static/app.js` 前端 JS 逻辑 + 端到端回归

---

## Task 1: 后端 loader — 私有文件 + 合并逻辑

**Files:**
- Modify: `.gitignore`(追加一行)
- Modify: `app.py:33`(常量区加 `PROBLEMS_CUSTOM_PATH` 等)
- Modify: `app.py:125-137`(改造 `load_problems` / `load_categories`)

**Interfaces:**
- Consumes: 现有 `load_json` / `save_json` / `DATA_DIR`(app.py:53/63/33)。
- Produces:
  - `PROBLEMS_CUSTOM_PATH: Path`、`CUSTOM_ID_START: int = 10001`、`CUSTOM_CATEGORY_NAME: str = "自定义"`
  - `load_custom_problems() -> dict`——返回 `{"categories":[{"name":"自定义","problems":[...]}], "next_id": int}`,文件不存在返回 fresh 空壳
  - `save_custom_problems(data: dict) -> None`
  - `_alive_custom_problems() -> list[dict]`——未删且已打 `custom=True` 的扁平题列表
  - `_official_ids() -> set[int]`——只从 `problems.json` 读的官方题 ID 集合(供删除接口校验)
  - `load_problems()` 返回 flat list,合并官方(带 `custom: False`)+ 存活自定义(带 `custom: True`)
  - `load_categories()` 返回 categories 列表,自定义分类拼在末尾;若无存活自定义题,**不追加**该分类

- [ ] **Step 1: 更新 .gitignore**

在 `.gitignore` 「私人数据 —— 不上传公开仓库」段落已有的两行下追加:

```
# 自定义题目(私人题库,不进公共 seed)
data/problems.custom.local.json
```

- [ ] **Step 2: `app.py` 常量区补三行**

在 `app.py:33` 附近(`PROBLEMS_PATH = DATA_DIR / "problems.json"` 下方,`load_config` 之前)追加:

```python
PROBLEMS_CUSTOM_PATH = DATA_DIR / "problems.custom.local.json"
CUSTOM_ID_START = 10001
CUSTOM_CATEGORY_NAME = "自定义"
```

- [ ] **Step 3: 新增 loader 函数**

在 `app.py` 的 `load_problems` 定义(约 125 行)**之前**插入以下函数:

```python
def load_custom_problems() -> dict:
    """读自定义题库文件;不存在则返回空壳(不落盘)。"""
    fresh = {
        "categories": [{"name": CUSTOM_CATEGORY_NAME, "problems": []}],
        "next_id": CUSTOM_ID_START,
    }
    data = load_json(PROBLEMS_CUSTOM_PATH, fresh)
    # 兼容旧文件缺 next_id / categories 的极端情况
    if "categories" not in data or not data["categories"]:
        data["categories"] = [{"name": CUSTOM_CATEGORY_NAME, "problems": []}]
    if "next_id" not in data:
        existing = [p["id"] for p in data["categories"][0]["problems"]]
        data["next_id"] = max([CUSTOM_ID_START - 1] + existing) + 1
    return data


def save_custom_problems(data: dict) -> None:
    save_json(PROBLEMS_CUSTOM_PATH, data)


def _alive_custom_problems() -> list[dict]:
    """未软删的 custom 题,已打上 custom=True,category=自定义。"""
    data = load_custom_problems()
    out = []
    for p in data["categories"][0]["problems"]:
        if p.get("deleted"):
            continue
        out.append({**p, "custom": True, "category": CUSTOM_CATEGORY_NAME})
    return out


def _official_ids() -> set[int]:
    """只从 problems.json 读的官方 ID 集合。"""
    raw = load_json(PROBLEMS_PATH, {"categories": []})
    return {p["id"] for cat in raw["categories"] for p in cat["problems"]}
```

- [ ] **Step 4: 改造 `load_problems`**

现有代码(`app.py:125-132`):

```python
def load_problems() -> list[dict]:
    """返回扁平列表,附上 category 字段。"""
    raw = load_json(PROBLEMS_PATH, {"categories": []})
    flat = []
    for cat in raw["categories"]:
        for p in cat["problems"]:
            flat.append({**p, "category": cat["name"]})
    return flat
```

改为:

```python
def load_problems() -> list[dict]:
    """返回扁平列表,附上 category / custom 字段。官方题 custom=False,自定义题 custom=True。"""
    raw = load_json(PROBLEMS_PATH, {"categories": []})
    flat = []
    for cat in raw["categories"]:
        for p in cat["problems"]:
            flat.append({**p, "category": cat["name"], "custom": False})
    flat.extend(_alive_custom_problems())
    return flat
```

- [ ] **Step 5: 改造 `load_categories`**

现有(`app.py:135-137`):

```python
def load_categories() -> list[dict]:
    """带上 category 名的原始分类结构。"""
    return load_json(PROBLEMS_PATH, {"categories": []})["categories"]
```

改为:

```python
def load_categories() -> list[dict]:
    """带上 category 名的原始分类结构;若有存活自定义题,把"自定义"分类拼在末尾。
    题字典里补 custom 字段(官方 False / 自定义 True),便于模板判断。"""
    raw = load_json(PROBLEMS_PATH, {"categories": []})["categories"]
    official = []
    for cat in raw:
        official.append({
            "name": cat["name"],
            "problems": [{**p, "custom": False} for p in cat["problems"]],
        })
    alive = _alive_custom_problems()
    if alive:
        official.append({
            "name": CUSTOM_CATEGORY_NAME,
            "problems": alive,  # 已带 custom=True
        })
    return official
```

- [ ] **Step 6: 手动验证 loader 不会破坏现有页面**

启动 dev server(端口 5001,host 现在是 `192.168.31.235`,如果本机 IP 不匹配先改回 `127.0.0.1`——但**不 commit** 这行):

```bash
python app.py
```

然后另开一个终端:

```bash
curl -s http://127.0.0.1:5001/api/dashboard | python3 -m json.tool | head -30
```

Expected:能看到 dashboard 数据,官方题数仍是 100,无报错。

停掉服务器:`lsof -iTCP:5001 -sTCP:LISTEN -Pn` 找 PID,`kill <pid>`。

- [ ] **Step 7: Commit**

```bash
git add .gitignore app.py
git commit -m "feat(custom-problems): 后端 loader 支持自定义题库合并

- 新增 data/problems.custom.local.json 存储层(gitignore)
- load_problems / load_categories 合并官方 + 未软删的自定义
- 官方题打 custom=False,自定义题打 custom=True
- 引入 _official_ids() 供后续删除接口做官方题保护

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Task 2: CRUD API — POST 新增 / DELETE 软删

**Files:**
- Modify: `app.py`(在 API 段末尾,约 `app.route("/api/settings")` 之后追加)

**Interfaces:**
- Consumes: `load_custom_problems / save_custom_problems / _official_ids / _today`(Task 1 产出)、`CUSTOM_CATEGORY_NAME`
- Produces:
  - `POST /api/custom-problem` — body: `{title: str, difficulty: str, url?: str, desc?: str}`,返回 `{"ok": true, "problem": {...}}`
  - `DELETE /api/custom-problem/<int:pid>` — 返回 `{"ok": true}`;官方题 400;不存在 / 已 deleted 404

- [ ] **Step 1: 定位插入位置**

在 `app.py` 尾部找到 `@app.post("/api/settings")` 之后、`# ---------- Entry ----------` 之前的空隙(约 1573 行附近)。新 API 全部加在这里。

- [ ] **Step 2: 添加 POST 新增 API**

```python
@app.post("/api/custom-problem")
def api_custom_problem_create():
    """新增自定义题。body: {title, difficulty, url?, desc?}"""
    body = request.get_json(force=True) or {}
    title = (body.get("title") or "").strip()
    difficulty = body.get("difficulty") or ""
    url = (body.get("url") or "").strip() or None
    desc = (body.get("desc") or "").strip() or None

    if not title:
        return jsonify({"error": "title required"}), 400
    if len(title) > 200:
        return jsonify({"error": "title too long"}), 400
    if difficulty not in {"简单", "中等", "困难"}:
        return jsonify({"error": "bad difficulty"}), 400
    if url and not (url.startswith("http://") or url.startswith("https://")):
        return jsonify({"error": "url must start with http:// or https://"}), 400
    if desc and len(desc) > 2000:
        return jsonify({"error": "desc too long"}), 400

    data = load_custom_problems()
    new_id = data["next_id"]
    problem = {
        "id": new_id,
        "title": title,
        "difficulty": difficulty,
        "url": url,
        "desc": desc,
        "custom": True,
        "deleted": False,
        "created_at": _today().isoformat(),
    }
    data["categories"][0]["problems"].append(problem)
    data["next_id"] = new_id + 1
    save_custom_problems(data)
    return jsonify({"ok": True, "problem": problem})
```

- [ ] **Step 3: 添加 DELETE 软删 API**

紧接 POST 之后:

```python
@app.delete("/api/custom-problem/<int:pid>")
def api_custom_problem_delete(pid: int):
    """软删自定义题。官方题拒绝;不存在或已删返 404。"""
    if pid in _official_ids():
        return jsonify({"error": "official problem cannot be deleted"}), 400
    data = load_custom_problems()
    for p in data["categories"][0]["problems"]:
        if p["id"] == pid:
            if p.get("deleted"):
                return jsonify({"error": "already deleted"}), 404
            p["deleted"] = True
            save_custom_problems(data)
            return jsonify({"ok": True})
    return jsonify({"error": "not found"}), 404
```

- [ ] **Step 4: 手动 curl 验证**

启动服务:

```bash
python app.py
```

另一个终端跑一串:

```bash
# 1. 新增一道
curl -s -X POST http://127.0.0.1:5001/api/custom-problem \
  -H "Content-Type: application/json" \
  -d '{"title":"测试题","difficulty":"中等","url":"https://example.com","desc":"just a test"}' | python3 -m json.tool

# 2. 校验:空标题 → 400
curl -s -o /dev/null -w "%{http_code}\n" -X POST http://127.0.0.1:5001/api/custom-problem \
  -H "Content-Type: application/json" \
  -d '{"title":"","difficulty":"中等"}'
# Expected: 400

# 3. 校验:错难度 → 400
curl -s -o /dev/null -w "%{http_code}\n" -X POST http://127.0.0.1:5001/api/custom-problem \
  -H "Content-Type: application/json" \
  -d '{"title":"t","difficulty":"easy"}'
# Expected: 400

# 4. 校验:错 url → 400
curl -s -o /dev/null -w "%{http_code}\n" -X POST http://127.0.0.1:5001/api/custom-problem \
  -H "Content-Type: application/json" \
  -d '{"title":"t","difficulty":"简单","url":"ftp://xxx"}'
# Expected: 400

# 5. 官方题不可删 → 400
curl -s -o /dev/null -w "%{http_code}\n" -X DELETE http://127.0.0.1:5001/api/custom-problem/1
# Expected: 400

# 6. 删刚才建的那道(假设 id=10001)
curl -s -X DELETE http://127.0.0.1:5001/api/custom-problem/10001 | python3 -m json.tool
# Expected: {"ok": true}

# 7. 重复删 → 404
curl -s -o /dev/null -w "%{http_code}\n" -X DELETE http://127.0.0.1:5001/api/custom-problem/10001
# Expected: 404

# 8. 检查文件
python3 -m json.tool < data/problems.custom.local.json
# Expected: 有一道 id=10001, deleted=true 的题, next_id=10002
```

停掉服务器。

- [ ] **Step 5: 清理测试数据(可选)**

如果不想留测试记录,可以手动 `rm data/problems.custom.local.json`,让 Task 3+ 从空开始验证。也可以留着,后续步骤照样能工作。

- [ ] **Step 6: Commit**

```bash
git add app.py
git commit -m "feat(custom-problems): POST/DELETE API 支持增删

- POST /api/custom-problem: 校验 title/difficulty/url/desc,分配 next_id,落盘
- DELETE /api/custom-problem/<pid>: 官方题返 400,不存在返 404,软删只标 deleted=true

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Task 3: 前端跳链模板分岔

**Files:**
- Modify: `templates/problems.html`(约 45-46 行的 `<a href=...leetcode.cn...>` 那段)
- Modify: `templates/problem_detail.html`(同类跳链逻辑)

**Interfaces:**
- Consumes: `p.custom`(Task 1 已让 `load_categories` 给每题打上此字段)、`p.url`(Task 2 起,自定义题会带此字段;官方题无此字段,Jinja `p.url` 求值为 `Undefined` → falsy,不会渲染)
- Produces:模板层对官方 / 自定义题的跳链分别处理

- [ ] **Step 1: 修改 `templates/problems.html:44-47`**

现有:

```jinja
<td>
  <a href="{{ url_for('problem_detail', pid=p.id) }}">{{ p.title }}</a>
  <a href="https://leetcode.cn/problems/{{ p.slug }}/" target="_blank" rel="noopener" class="lc-link" title="在力扣打开">↗</a>
</td>
```

改为:

```jinja
<td>
  <a href="{{ url_for('problem_detail', pid=p.id) }}">{{ p.title }}</a>
  {% if p.custom %}
    {% if p.url %}<a href="{{ p.url }}" target="_blank" rel="noopener" class="lc-link" title="题目链接">↗</a>{% endif %}
  {% else %}
    <a href="https://leetcode.cn/problems/{{ p.slug }}/" target="_blank" rel="noopener" class="lc-link" title="在力扣打开">↗</a>
  {% endif %}
</td>
```

- [ ] **Step 2: 检查 `templates/problem_detail.html` 是否也有力扣跳链**

```bash
grep -n "leetcode.cn/problems\|p.slug\|problem.slug" /Users/bytedance/leetcode-hot100/templates/problem_detail.html
```

如果有类似 `https://leetcode.cn/problems/{{ p.slug }}/`,用同样的 `{% if p.custom %}` 逻辑分岔。如果 grep 没结果,跳过。

**注意**:`api_load_problem_detail`(app.py 约 807-816)返回的题字典必须也带 `custom` 字段。检查 `problem_detail` 路由函数,若它直接从 `load_problems()` 里 filter 出题,`custom` 已自动带上,无需改。若走的是别的路径,需要补 `custom` 字段。查一下:

```bash
grep -A 8 "def problem_detail" /Users/bytedance/leetcode-hot100/app.py
```

如果 handler 是从 `load_problems()` 过滤,已 OK。

- [ ] **Step 3: 手动验证不破**

启动服务,访问 `http://127.0.0.1:5001/problems`,观察:
- 官方题的 `↗` 仍然存在,点开跳力扣
- 未有任何自定义题时,页面无「自定义」section

如果 Task 2 留了测试数据(已被软删),页面不应显示。

- [ ] **Step 4: Commit**

```bash
git add templates/problems.html templates/problem_detail.html
git commit -m "feat(custom-problems): 模板按 custom 分岔跳链

- 官方题走 leetcode.cn/problems/{slug}
- 自定义题走 p.url,未填则不显示 ↗

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Task 4: 顶部「+ 添加题目」按钮、Modal、🗑 按钮

**Files:**
- Modify: `templates/problems.html`(顶部 `.filters` 后加按钮 + 页尾加 modal;操作列末加 🗑)

**Interfaces:**
- Consumes: `.modal-backdrop / .modal / .modal-head / .modal-body / .modal-foot` CSS(已存在于 `static/style.css:1061+`)
- Produces:
  - HTML 元素 `#btn-add-problem`(顶部按钮)
  - HTML 元素 `#modal-add-problem`(整个 modal)
  - HTML 元素 `#cp-form`(表单)与其字段 `#cp-title / #cp-difficulty / #cp-url / #cp-desc`
  - 操作列内的 `<button class="btn ghost cp-del" data-pid=...>🗑</button>`(仅 `p.custom` 时渲染)

- [ ] **Step 1: 顶部加「+ 添加题目」按钮**

在 `templates/problems.html` 现有 `<div class="filters">...</div>`(约 13-28 行)之后立即插入:

```html
<div class="cp-toolbar">
  <button id="btn-add-problem" class="btn" type="button">+ 添加题目</button>
</div>
```

- [ ] **Step 2: 操作列加 🗑 按钮**

修改 `templates/problems.html` 里操作列(约 51-61 行)。现有:

```jinja
<td>
  <select data-status-select data-pid="{{ p.id }}">
    ...
  </select>
  <button class="btn ghost note-toggle" data-pid="{{ p.id }}" title="思路">💡</button>
  <button class="btn ghost cs-toggle" data-pid="{{ p.id }}" title="Cheatsheet">📝</button>
</td>
```

在 `📝` 按钮后追加(仍在 `<td>` 内):

```jinja
{% if p.custom %}
  <button class="btn ghost cp-del" data-pid="{{ p.id }}" title="删除自定义题">🗑</button>
{% endif %}
```

- [ ] **Step 3: 页尾加 Modal**

在 `templates/problems.html` 的 `{% endblock %}` 之前插入:

```html
<div id="modal-add-problem" class="modal-backdrop" hidden>
  <div class="modal" role="dialog" aria-labelledby="cp-modal-title">
    <div class="modal-head">
      <h3 id="cp-modal-title">添加自定义题</h3>
      <button class="modal-close" id="cp-close" type="button" aria-label="关闭">×</button>
    </div>
    <form id="cp-form" class="modal-body">
      <label>
        <span>题名 *</span>
        <input id="cp-title" type="text" required maxlength="200" placeholder="题目标题" />
      </label>
      <label>
        <span>难度 *</span>
        <select id="cp-difficulty" required>
          <option value="简单">简单</option>
          <option value="中等" selected>中等</option>
          <option value="困难">困难</option>
        </select>
      </label>
      <label>
        <span>题目链接</span>
        <input id="cp-url" type="url" placeholder="https://..." />
      </label>
      <label>
        <span>备注</span>
        <textarea id="cp-desc" rows="3" maxlength="2000" placeholder="选填"></textarea>
      </label>
      <p id="cp-form-error" class="cp-form-error" hidden></p>
    </form>
    <div class="modal-foot">
      <button class="btn ghost" id="cp-cancel" type="button">取消</button>
      <button class="btn" id="cp-save" type="button">保存</button>
    </div>
  </div>
</div>
```

- [ ] **Step 4: 手动验证 SSR 不破**

刷新 `/problems` 页面。观察:
- 「+ 添加题目」按钮出现在 filter 下方
- Modal HTML 存在但因 `hidden` 属性不可见(F12 devtools 看 DOM)
- 官方题行**没有** 🗑 按钮
- 无 JS 报错(F12 Console)

尚不需要点击响应——JS 在 Task 5 加。

- [ ] **Step 5: 页面若有 modal 布局挤压或 form label 样式很丑,加一小段 CSS**

先跳过这一步——`static/style.css` 里已有的 `.modal input[type="text"] / select / .modal-body label` 规则应该够用。若视觉真塌了,在 Task 5 结束前再补 CSS。

- [ ] **Step 6: Commit**

```bash
git add templates/problems.html
git commit -m "feat(custom-problems): 顶部按钮 + Modal + 自定义题删除按钮

- .filters 下方加 #btn-add-problem
- 模板末尾加 #modal-add-problem(标题/难度/链接/备注)
- 自定义题操作列末追加 .cp-del 🗑 按钮

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Task 5: 前端 JS 逻辑 + 端到端回归

**Files:**
- Modify: `static/app.js`(在文件末尾追加一段 IIFE / 直接绑定,取决于文件现有模式)

**Interfaces:**
- Consumes: `#btn-add-problem / #modal-add-problem / #cp-close / #cp-cancel / #cp-save / #cp-title / #cp-difficulty / #cp-url / #cp-desc / #cp-form-error / .cp-del`(Task 4 产出)
- Produces:交互行为——添加题、软删题、UI 局部更新

- [ ] **Step 1: 快速看下 `static/app.js` 现有代码风格**

```bash
head -40 /Users/bytedance/leetcode-hot100/static/app.js; echo "---"; tail -30 /Users/bytedance/leetcode-hot100/static/app.js
```

判断:是模块化 IIFE?顶层直接 addEventListener?还是有个统一 `bootstrap()`。**按照现有风格追加**,不要突兀塞。

- [ ] **Step 2: 追加"添加题目" modal 交互**

在 `static/app.js` 末尾追加(若文件是单一 IIFE,写在 IIFE 内;否则顶层直接写):

```javascript
// ---------- Custom problems: add ----------
(function initCustomProblemAdd() {
  const btnOpen = document.getElementById("btn-add-problem");
  const modal = document.getElementById("modal-add-problem");
  if (!btnOpen || !modal) return;
  const btnClose = document.getElementById("cp-close");
  const btnCancel = document.getElementById("cp-cancel");
  const btnSave = document.getElementById("cp-save");
  const inTitle = document.getElementById("cp-title");
  const inDiff = document.getElementById("cp-difficulty");
  const inUrl = document.getElementById("cp-url");
  const inDesc = document.getElementById("cp-desc");
  const errBox = document.getElementById("cp-form-error");

  function open() {
    errBox.hidden = true;
    errBox.textContent = "";
    inTitle.value = "";
    inDiff.value = "中等";
    inUrl.value = "";
    inDesc.value = "";
    modal.hidden = false;
    setTimeout(() => inTitle.focus(), 0);
  }
  function close() { modal.hidden = true; }
  function showErr(msg) { errBox.textContent = msg; errBox.hidden = false; }

  btnOpen.addEventListener("click", open);
  btnClose.addEventListener("click", close);
  btnCancel.addEventListener("click", close);
  modal.addEventListener("click", (e) => { if (e.target === modal) close(); });
  document.addEventListener("keydown", (e) => {
    if (!modal.hidden && e.key === "Escape") close();
  });

  btnSave.addEventListener("click", async () => {
    const title = inTitle.value.trim();
    const difficulty = inDiff.value;
    const url = inUrl.value.trim();
    const desc = inDesc.value.trim();

    if (!title) return showErr("题名不能为空");
    if (title.length > 200) return showErr("题名过长(≤200 字符)");
    if (url && !/^https?:\/\//i.test(url)) return showErr("链接需以 http:// 或 https:// 开头");
    if (desc.length > 2000) return showErr("备注过长(≤2000 字符)");

    btnSave.disabled = true;
    try {
      const resp = await fetch("/api/custom-problem", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ title, difficulty, url: url || undefined, desc: desc || undefined }),
      });
      const data = await resp.json();
      if (!resp.ok) { showErr(data.error || "保存失败"); return; }
      close();
      // 简单起见,新增后整页刷新——"自定义" section 会自动出现(SSR)
      location.reload();
    } catch (e) {
      showErr("网络异常:" + e.message);
    } finally {
      btnSave.disabled = false;
    }
  });
})();
```

- [ ] **Step 3: 追加"删除自定义题"交互(事件委托)**

紧接上一段追加:

```javascript
// ---------- Custom problems: delete ----------
document.addEventListener("click", async (e) => {
  const btn = e.target.closest(".cp-del");
  if (!btn) return;
  const pid = btn.dataset.pid;
  if (!pid) return;
  if (!confirm("删除这道自定义题?题的进度/笔记会保留但从题库中隐藏。")) return;
  btn.disabled = true;
  try {
    const resp = await fetch(`/api/custom-problem/${pid}`, { method: "DELETE" });
    const data = await resp.json();
    if (!resp.ok) {
      alert(data.error || "删除失败");
      btn.disabled = false;
      return;
    }
    // 移除该题的两行(数据行 + 展开的 cs-row)
    const dataRow = btn.closest("tr");
    const csRow = dataRow?.nextElementSibling;
    const section = dataRow?.closest(".cat-block");
    dataRow?.remove();
    if (csRow && csRow.classList.contains("cs-row")) csRow.remove();
    // 若 section 内已无题行,把整个 section 也移除
    if (section && !section.querySelector("tbody tr:not(.cs-row)")) {
      section.remove();
    }
  } catch (e) {
    alert("网络异常:" + e.message);
    btn.disabled = false;
  }
});
```

- [ ] **Step 4: 端到端回归**

启动服务:

```bash
python app.py
```

浏览器打开 `http://127.0.0.1:5001/problems`,依次:

1. 点「+ 添加题目」→ modal 弹出,title 聚焦
2. 只填 title「测试题 A」+ 难度默认「中等」→ 保存 → 页面刷新,底部出现「自定义」section 和「测试题 A」
3. 自定义题行:`↗` 图标**不显示**(未填 URL)、`🗑` 显示、`💡📝` 与官方题一致
4. 官方题(如 #1)行:**没有** 🗑
5. 再加一道,填 URL `https://leetcode.cn/problems/two-sum/`,`↗` 出现且能跳转
6. 给「测试题 A」标状态「磕绊」→ Dashboard 计数是否递增(打开 `/`,已刷分母 = 100 + 2 = 102)
7. 打开 `/calendar` → 「测试题 A」是否也进队列(可以不深究,肉眼看看有无自定义题出现)
8. 删除「测试题 A」→ confirm → 该行消失;`data/problems.custom.local.json` 里该题 `deleted: true`;`progress.local.json` 里 key `"10001"` 若之前 solidset 过应保留
9. 删除自定义 section 最后一道 → section 整个消失
10. 再刷 `/problems` → 「自定义」section 不再出现(SSR 也不渲染)
11. F12 Console 全程无 JS 报错

- [ ] **Step 5: 清理测试数据**

```bash
rm -f data/problems.custom.local.json
```

- [ ] **Step 6: 停掉 dev server 并 commit**

```bash
lsof -iTCP:5001 -sTCP:LISTEN -Pn  # 找 PID
kill <pid>
```

```bash
git add static/app.js
git commit -m "feat(custom-problems): 前端 JS 完成增删闭环

- initCustomProblemAdd IIFE: modal 开关、字段校验、POST 提交后 reload
- .cp-del 事件委托: confirm → DELETE → 局部移除 DOM,清空则移除整个 section

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Self-Review 结果

**Spec coverage check**:

| Spec 章节 | 覆盖任务 |
|---|---|
| §1.1 数据模型 | Task 1 Step 3(loader)、Task 2(API 落盘字段) |
| §1.2 分类归属 | Task 1 Step 5(load_categories 尾部追加) |
| §1.3 软删过滤 + section 空则不渲染 | Task 1 Step 5 + Task 5 Step 3(前端删完 section 也 remove) |
| §1.4 进度数据不动 | Task 2 Step 3(DELETE 仅改 problems.custom.local.json) |
| §2.1 一视同仁 | Task 1 Step 4/5(合并进 flat list & categories,自动被 dashboard / calendar / cheatsheet 消费) |
| §2.2 只读保护 | Task 2 Step 3(_official_ids 校验) |
| §2.3 ID 分配 | Task 1 Step 3(load_custom_problems 补 next_id)、Task 2 Step 2(读 next_id + 1) |
| §2.4 分类冲突 | Task 1 Step 5(自定义 section 独立追加,不合并) |
| §3.1 常量与函数 | Task 1 Step 2/3 |
| §3.2 CRUD + 校验 | Task 2 Step 2/3 |
| §3.3 官方题只读 | Task 2 Step 3 |
| §3.4 模板跳链分岔 | Task 3 Step 1/2 |
| §4.1 添加按钮 / Modal / 🗑 | Task 4 Step 1/2/3 |
| §4.2 JS 事件 | Task 5 Step 2/3 |
| §4.3 视觉细节 | 明确跳过(第一版不加装饰) |
| §5 影响面 | Task 1-5 已覆盖必改文件 |
| §6 测试计划 13 条 | Task 2 Step 4 + Task 5 Step 4 已覆盖(手工回归) |
| §7 非目标 | 无需实现 |

**Placeholder scan**:无 TBD / TODO / "similar to"。所有代码块都是可直接粘贴的完整片段。

**Type consistency**:

- 新增题字段名:Task 1 `_alive_custom_problems` 补 `custom=True`;Task 2 API 落盘也是 `custom: True`;Task 3 模板消费 `p.custom`;一致。
- API 路径:Task 2 定义 `POST /api/custom-problem` 和 `DELETE /api/custom-problem/<int:pid>`;Task 5 JS 完全一致。
- DOM ID:Task 4 定义 `#btn-add-problem / #modal-add-problem / #cp-title` 等;Task 5 JS 引用完全一致。
- `_official_ids()` 在 Task 1 定义,Task 2 消费,签名一致。

**特殊说明**:

- Task 1 Step 6 提到"host 现在是 192.168.31.235"——那是本 session 早先手动改的、未 commit 的本地状态。**若开发时本机 IP 不匹配,先临时把 host 改回 `127.0.0.1` 但不 commit**,不影响本计划任何一步。开发结束后,该行会作为工作区未 commit 状态保留,由用户自己决定要不要提交。
- 无自动化测试框架——本项目 `tests/` 目录不存在,`data/` 目录里也没测试文件。手工回归是唯一路径,不引入 pytest 以免拖节奏。
