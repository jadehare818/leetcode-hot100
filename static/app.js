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

// 复习打分 / 首刷 —— 卡片内的按钮走 2s 延迟 + 可撤销；卡片外（如详情页）保持即时
//
// 交互约定（简版）：
//   - 点某个状态按钮 → 卡片开始淡出（2s），2s 后发请求 + reload
//   - 2s 内再点同一按钮 → 撤销，卡片恢复原样，请求不发
//   - 2s 内点了不同按钮 → 换选择，倒计时重置（新的 2s 起算）
//   - 每卡独立，互不影响；页面刷新时 pending 视为放弃
const PENDING_DELAY_MS = 2000;
const cardTimers = new WeakMap();  // card element → { timerId, pendingKey, pendingBtn }

function commitCardStatus(card, url, payload, btn) {
  // 请求发出前把所有相关按钮 disable，防止 reload 抢跑
  card.querySelectorAll('[data-review], [data-solve]').forEach(b => b.disabled = true);
  post(url, payload).then(() => location.reload());
}

function cancelCardPending(card) {
  const state = cardTimers.get(card);
  if (!state) return;
  clearTimeout(state.timerId);
  cardTimers.delete(card);
  card.classList.remove('is-pending');
  card.querySelectorAll('[data-review], [data-solve]').forEach(b => b.classList.remove('is-armed'));
}

function armCardStatus(btn, kind /* 'review' | 'solve' */) {
  const card = btn.closest('.card');
  if (!card) {
    // 详情页等：没有卡片容器，走即时逻辑
    return null;
  }
  const pid = btn.dataset.pid;
  const value = btn.dataset[kind];  // dataset.review 或 dataset.solve
  const key = `${kind}:${value}`;
  const state = cardTimers.get(card);

  // 情况 1：再次点击同一个按钮 → 撤销
  if (state && state.pendingKey === key) {
    cancelCardPending(card);
    return;
  }

  // 情况 2：切换到别的按钮 → 清掉旧的，重新计时（下面统一处理）
  if (state) {
    clearTimeout(state.timerId);
    card.querySelectorAll('[data-review], [data-solve]').forEach(b => b.classList.remove('is-armed'));
    // 立刻跳回不透明，再重新开始 2s 淡出（否则会从当前中间透明度接着补完剩余 transition）
    card.classList.add('no-transition');
    card.classList.remove('is-pending');
    void card.offsetWidth;  // 强制 reflow，让浏览器认可"opacity 已经回到 1"
    card.classList.remove('no-transition');
  }

  // 情况 3：新的 pending 状态
  card.classList.add('is-pending');
  btn.classList.add('is-armed');
  const url = kind === 'review'
    ? `/api/problem/${pid}/review`
    : `/api/problem/${pid}/status`;
  const payload = kind === 'review' ? { score: value } : { status: value };
  const timerId = setTimeout(() => {
    cardTimers.delete(card);
    commitCardStatus(card, url, payload, btn);
  }, PENDING_DELAY_MS);
  cardTimers.set(card, { timerId, pendingKey: key, pendingBtn: btn });
}

// 复习打分
document.querySelectorAll('[data-review]').forEach(btn => {
  btn.addEventListener('click', async () => {
    if (btn.disabled) return;
    if (btn.closest('.card')) {
      armCardStatus(btn, 'review');
      return;
    }
    // 详情页等：即时提交
    const pid = btn.dataset.pid;
    const score = btn.dataset.review;
    btn.disabled = true;
    await post(`/api/problem/${pid}/review`, { score });
    location.reload();
  });
});

// 首刷 / 手动改状态（详情页 + dashboard 的新题按钮）
document.querySelectorAll('[data-solve]').forEach(btn => {
  btn.addEventListener('click', async () => {
    if (btn.disabled) return;
    if (btn.closest('.card')) {
      armCardStatus(btn, 'solve');
      return;
    }
    // 详情页等：即时提交
    const pid = btn.dataset.pid;
    const status = btn.dataset.solve;
    btn.disabled = true;
    await post(`/api/problem/${pid}/status`, { status });
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

// 空档横幅:整日空档时提示"整体后移一天"或"忽略"。
const skippedBanner = document.querySelector('.skipped-banner');
if (skippedBanner) {
  const skippedDate = skippedBanner.dataset.skippedDate;
  const dismissKey = `skipped-yesterday-dismissed-${skippedDate}`;
  if (!localStorage.getItem(dismissKey)) {
    skippedBanner.hidden = false;
  }
  const shiftBtn = skippedBanner.querySelector('[data-shift-forward]');
  const dismissBtn = skippedBanner.querySelector('[data-skipped-dismiss]');
  if (shiftBtn) {
    shiftBtn.addEventListener('click', async () => {
      if (!confirm(`把 ${skippedDate} 起所有 next_review 各 +1 天?等价于那天不存在。`)) return;
      shiftBtn.disabled = true;
      const r = await post('/api/shift-forward', {from_date: skippedDate, days: 1});
      alert(`已平移 ${r.count} 题 (+${r.days} 天)`);
      location.reload();
    });
  }
  if (dismissBtn) {
    dismissBtn.addEventListener('click', () => {
      localStorage.setItem(dismissKey, '1');
      skippedBanner.hidden = true;
    });
  }
}

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
