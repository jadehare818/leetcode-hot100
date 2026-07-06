// 交互脚本：状态改动、复习、笔记保存、代码文件

async function post(url, body) {
  const r = await fetch(url, {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify(body || {}),
  });
  return r.json();
}

// ========== 语言切换器 ==========
const LANG_KEY = 'lc-hot100-lang';
function currentLang() {
  return localStorage.getItem(LANG_KEY) || 'python';
}
const langSelect = document.getElementById('lang-select');
if (langSelect) {
  langSelect.value = currentLang();
  langSelect.addEventListener('change', () => {
    localStorage.setItem(LANG_KEY, langSelect.value);
    // 无需 reload，"打开代码"按钮读 currentLang()
  });
}

// 复习打分
document.querySelectorAll('[data-review]').forEach(btn => {
  btn.addEventListener('click', async () => {
    const pid = btn.dataset.pid;
    const score = btn.dataset.review;
    btn.disabled = true;
    await post(`/api/problem/${pid}/review`, {score});
    location.reload();
  });
});

// 首刷 / 手动改状态（详情页 + dashboard 的新题按钮）
document.querySelectorAll('[data-solve]').forEach(btn => {
  btn.addEventListener('click', async () => {
    const pid = btn.dataset.pid;
    const status = btn.dataset.solve;
    btn.disabled = true;
    await post(`/api/problem/${pid}/status`, {status});
    location.reload();
  });
});

// 全表下拉
document.querySelectorAll('[data-status-select]').forEach(sel => {
  sel.addEventListener('change', async () => {
    const pid = sel.dataset.pid;
    const status = sel.value;
    await post(`/api/problem/${pid}/status`, {status});
    // 更新行 status，不 reload 避免滚回顶部
    const row = sel.closest('tr');
    row.dataset.status = status;
    row.querySelector('.st').textContent = status;
    row.querySelector('.st').className = `st st-${status}`;
    applyFilters();
  });
});

// 单张卡片的推迟
document.querySelectorAll('[data-postpone]').forEach(btn => {
  btn.addEventListener('click', async () => {
    const pid = btn.dataset.pid;
    btn.disabled = true;
    await post(`/api/problem/${pid}/postpone`);
    location.reload();
  });
});

// 推迟全部 / 仅推迟逾期
const postponeAll = document.querySelector('[data-postpone-all]');
if (postponeAll) {
  postponeAll.addEventListener('click', async () => {
    if (!confirm('把所有到期未做的题都推到明天？间隔档位不受影响。')) return;
    postponeAll.disabled = true;
    const r = await post('/api/postpone-overdue', {only_overdue_days: 0});
    alert(`已推迟 ${r.count} 题到明天`);
    location.reload();
  });
}
const postponeOverdue = document.querySelector('[data-postpone-overdue]');
if (postponeOverdue) {
  postponeOverdue.addEventListener('click', async () => {
    if (!confirm('把所有逾期超过 3 天的题推到明天？其他到期题保持原样。')) return;
    postponeOverdue.disabled = true;
    const r = await post('/api/postpone-overdue', {only_overdue_days: 4});
    alert(`已推迟 ${r.count} 题`);
    location.reload();
  });
}

// 打开代码文件（按当前选中语言）
document.querySelectorAll('.open-code').forEach(btn => {
  btn.addEventListener('click', async () => {
    const pid = btn.dataset.pid;
    const lang = currentLang();
    const res = await post(`/api/problem/${pid}/open-code`, {lang});
    const hint = document.querySelector('.filepath');
    if (hint) hint.textContent = res.path;
    btn.textContent = `📝 已打开: ${res.path.split('/').pop()}`;
    setTimeout(() => btn.textContent = '📝 打开代码', 2500);
  });
});

// 笔记保存
const noteBtn = document.getElementById('save-note');
if (noteBtn) {
  noteBtn.addEventListener('click', async () => {
    const ta = document.getElementById('note');
    const pid = ta.dataset.pid;
    await post(`/api/problem/${pid}/note`, {note: ta.value});
    document.getElementById('note-hint').textContent = '已保存';
    setTimeout(() => document.getElementById('note-hint').textContent = '', 2000);
  });
}

// 全表过滤
function applyFilters() {
  const active = new Set();
  document.querySelectorAll('[data-filter]').forEach(cb => {
    if (cb.checked) active.add(cb.dataset.filter);
  });
  document.querySelectorAll('tr[data-status]').forEach(row => {
    const st = row.dataset.status;
    row.classList.toggle('hidden', !active.has(st));
  });
}
document.querySelectorAll('[data-filter]').forEach(cb => cb.addEventListener('change', applyFilters));
applyFilters();
