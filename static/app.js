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
const STATUS_ZH = {todo: '未刷', forgot: '卡住', shaky: '磕绊', solid: '很稳', archived: '归档'};
document.querySelectorAll('[data-status-select]').forEach(sel => {
  sel.addEventListener('change', async () => {
    const pid = sel.dataset.pid;
    const status = sel.value;
    await post(`/api/problem/${pid}/status`, {status});
    // 更新行 status，不 reload 避免滚回顶部
    const row = sel.closest('tr');
    row.dataset.status = status;
    row.querySelector('.st').textContent = STATUS_ZH[status] || status;
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

// ========== 设置弹窗 ==========
const settingsBtn = document.getElementById('open-settings');
const settingsBackdrop = document.getElementById('settings-backdrop');
const closeSettings = document.getElementById('close-settings');
const saveSettings = document.getElementById('save-settings');

if (settingsBtn && settingsBackdrop) {
  const $wd = document.getElementById('quota-weekday');
  const $we = document.getElementById('quota-weekend');
  const $iv = document.getElementById('intervals');
  const $od = document.getElementById('overdue');
  const $db = document.getElementById('day-boundary');
  const $hint = document.getElementById('settings-hint');

  async function openSettings() {
    const r = await fetch('/api/settings');
    const d = await r.json();
    $wd.value = d.daily_quota.weekday;
    $we.value = d.daily_quota.weekend;
    $iv.value = d.review_intervals_days.join(', ');
    $od.value = d.overdue_alert_days;
    $db.value = String(d.day_boundary_hour ?? 0);
    $hint.textContent = '';
    settingsBackdrop.hidden = false;
    setTimeout(() => $wd.focus(), 50);
  }

  function hideSettings() { settingsBackdrop.hidden = true; }

  settingsBtn.addEventListener('click', openSettings);
  closeSettings.addEventListener('click', hideSettings);
  settingsBackdrop.addEventListener('click', (e) => {
    if (e.target === settingsBackdrop) hideSettings();
  });
  document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape' && !settingsBackdrop.hidden) hideSettings();
  });

  saveSettings.addEventListener('click', async () => {
    // 解析 intervals: 允许逗号或空格分隔
    const intervals = $iv.value
      .split(/[,\s]+/)
      .map(s => s.trim())
      .filter(Boolean)
      .map(s => parseInt(s, 10));

    if (intervals.some(n => isNaN(n) || n <= 0)) {
      $hint.textContent = '间隔天数只能是正整数';
      $hint.style.color = 'var(--tomato)';
      return;
    }

    const body = {
      daily_quota: {
        weekday: parseInt($wd.value, 10) || 0,
        weekend: parseInt($we.value, 10) || 0,
      },
      review_intervals_days: intervals,
      overdue_alert_days: parseInt($od.value, 10) || 0,
      day_boundary_hour: parseFloat($db.value) || 0,
    };

    saveSettings.disabled = true;
    const r = await post('/api/settings', body);
    saveSettings.disabled = false;

    if (r.ok) {
      $hint.textContent = '已保存 · 刷新页面…';
      $hint.style.color = 'var(--sage)';
      setTimeout(() => location.reload(), 700);
    } else {
      $hint.textContent = r.error || '保存失败';
      $hint.style.color = 'var(--tomato)';
    }
  });
}
