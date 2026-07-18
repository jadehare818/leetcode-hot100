// 分享卡片：两种视图（checkin 打卡 / calendar 节奏），共享保存 + 发飞书。
// - checkin：直接 DOM 渲染（拉 /api/checkin），html2canvas 前端截图
// - calendar：iframe 嵌 /calendar-card 独立页，前端 html2canvas 抓 iframe 内部
//   （或者点 send 时让服务端 render_checkin.py 直接跑 playwright；这里前端简化：
//    Save 前端截，Send 服务端后端专门端点跑 playwright）

(function() {
  const openBtn = document.getElementById('open-checkin-card');
  const backdrop = document.getElementById('checkin-backdrop');
  const closeBtn = document.getElementById('close-checkin');
  const saveBtn = document.getElementById('save-checkin');
  const sendBtn = document.getElementById('send-checkin-feishu');
  const hintEl = document.getElementById('checkin-hint');
  const checkinCard = document.getElementById('checkin-card');
  const calFrame = document.getElementById('calendar-card-frame');
  const tabs = document.querySelectorAll('.checkin-tab');
  if (!openBtn || !backdrop) return;

  let currentView = 'checkin';
  let checkinLoaded = false;
  let calendarLoaded = false;

  const DIFF_ICON = { '简单': '🟢', '中等': '🟡', '困难': '🔴' };

  function esc(s) {
    return String(s).replace(/[&<>"']/g, c => ({
      '&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'
    }[c]));
  }
  function fmtProblems(list, kind) {
    if (!list.length) return `<div class="cc-empty">${kind === 'solve' ? '今日暂无首刷' : '今日暂无复习'}</div>`;
    return `<ul class="cc-list">` + list.map(p => `
      <li>
        <span class="cc-pid">#${p.id}</span>
        <span class="cc-title">${esc(p.title)}</span>
        <span class="cc-diff">${DIFF_ICON[p.difficulty] || ''} ${esc(p.difficulty)}</span>
      </li>
    `).join('') + `</ul>`;
  }
  function progressBar(done, total) {
    const pct = Math.floor(done / total * 100);
    return `
      <div class="cc-progress">
        <div class="cc-progress-bar">
          <div class="cc-progress-fill" style="width: ${pct}%;"></div>
        </div>
        <div class="cc-progress-nums">
          <span class="cc-progress-done">${done}</span>
          <span class="cc-progress-total">/ ${total}</span>
          <span class="cc-progress-pct">${pct}%</span>
        </div>
      </div>
    `;
  }
  function renderCheckin(d) {
    const doneToday = d.solved.length + d.reviewed.length;
    const finish = d.finish;
    const finishStr = finish.reachable && finish.days_left != null && finish.days_left > 0
      ? `${finish.days_left} 天 · ${finish.finish_date}`
      : (finish.days_left === 0 ? '已刷完 🎉' : '—');

    checkinCard.innerHTML = `
      <div class="cc-corner-mark">HOT 100</div>
      <header class="cc-head">
        <div class="cc-eyebrow">${d.date} · 周${d.weekday} · ${d.is_weekend ? 'Weekend' : 'Weekday'} Session</div>
        <h2 class="cc-brand">刷题手账 · <em>Journal</em></h2>
      </header>
      <section class="cc-hero">
        <div class="cc-blurb">${esc(d.blurb)}</div>
        <div class="cc-today-count">
          <span class="cc-big">${doneToday}</span>
          <span class="cc-big-unit">道 · 今日</span>
        </div>
        <div class="cc-today-break">
          <span class="cc-chip cc-chip-solve">首刷 · ${d.solved.length}</span>
          <span class="cc-chip cc-chip-review">复习 · ${d.reviewed.length}</span>
          <span class="cc-chip cc-chip-streak">🔥 连续 ${d.streak} 天${d.streak_used ? ` 🛡️${d.streak_used}` : ''}</span>
        </div>
      </section>
      <section class="cc-block">
        <div class="cc-block-title">今日首刷</div>
        ${fmtProblems(d.solved, 'solve')}
      </section>
      <section class="cc-block">
        <div class="cc-block-title">今日复习</div>
        ${fmtProblems(d.reviewed, 'review')}
      </section>
      <section class="cc-progress-block">
        <div class="cc-block-title">总体进度</div>
        ${progressBar(d.done_count, d.total)}
        <div class="cc-legend">
          <span class="cc-legend-item"><span class="cc-legend-dot dot-solid"></span><span>${d.counts.solid} 很稳</span></span>
          <span class="cc-legend-item"><span class="cc-legend-dot dot-shaky"></span><span>${d.counts.shaky} 磕绊</span></span>
          <span class="cc-legend-item"><span class="cc-legend-dot dot-forgot"></span><span>${d.counts.forgot} 卡住</span></span>
          <span class="cc-legend-item"><span class="cc-legend-dot dot-todo"></span><span>${d.counts.todo} 未刷</span></span>
        </div>
      </section>
      <section class="cc-stats-grid">
        <div class="cc-stat">
          <div class="cc-stat-k">Finish by</div>
          <div class="cc-stat-v">${finishStr}</div>
        </div>
        <div class="cc-stat">
          <div class="cc-stat-k">已完成难度</div>
          <div class="cc-stat-v cc-diff-line">
            <span>🟢 ${d.overall_diff['简单']}</span>
            <span>🟡 ${d.overall_diff['中等']}</span>
            <span>🔴 ${d.overall_diff['困难']}</span>
          </div>
        </div>
      </section>
      <footer class="cc-foot">
        <div class="cc-foot-l">— #hot100 · 每日一题 —</div>
        <div class="cc-foot-repo">github.com/jadehare818/leetcode-hot100</div>
      </footer>
    `;
  }

  async function loadCheckin() {
    if (checkinLoaded) return;
    const r = await fetch('/api/checkin');
    const d = await r.json();
    renderCheckin(d);
    checkinLoaded = true;
  }
  function loadCalendar() {
    if (calendarLoaded) return;
    // 加时间戳防缓存
    calFrame.src = `/calendar-card?_=${Date.now()}`;
    calendarLoaded = true;
  }

  function switchView(view) {
    currentView = view;
    tabs.forEach(t => t.classList.toggle('active', t.dataset.card === view));
    checkinCard.hidden = view !== 'checkin';
    calFrame.hidden = view !== 'calendar';
    if (view === 'checkin') loadCheckin();
    else loadCalendar();
  }

  async function open_() {
    hintEl.textContent = '';
    hintEl.style.color = '';
    backdrop.hidden = false;
    switchView(currentView);
  }
  function close_() { backdrop.hidden = true; }

  openBtn.addEventListener('click', open_);
  closeBtn.addEventListener('click', close_);
  backdrop.addEventListener('click', (e) => { if (e.target === backdrop) close_(); });
  document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape' && !backdrop.hidden) close_();
  });
  tabs.forEach(t => t.addEventListener('click', () => switchView(t.dataset.card)));

  // 截当前 tab 对应的元素成 blob。
  //   checkin：直接对 DOM 截图（html2canvas 前端）
  //   calendar：拿 iframe 里的 body（也用 html2canvas，跨 same-origin 可以）
  async function currentCardToBlob() {
    if (typeof html2canvas !== 'function') throw new Error('html2canvas 未加载');
    let target;
    if (currentView === 'checkin') {
      target = checkinCard;
    } else {
      const doc = calFrame.contentDocument;
      if (!doc) throw new Error('iframe 还没就绪');
      target = doc.querySelector('.calendar-card');
      if (!target) throw new Error('.calendar-card 在 iframe 里没找到');
    }
    const canvas = await html2canvas(target, {
      scale: 2,
      backgroundColor: null,
      useCORS: true,
      logging: false,
    });
    return new Promise((res, rej) => {
      canvas.toBlob(b => b ? res(b) : rej(new Error('canvas.toBlob 空')), 'image/png');
    });
  }

  saveBtn.addEventListener('click', async () => {
    saveBtn.disabled = true;
    hintEl.textContent = '生成中…';
    hintEl.style.color = '';
    try {
      const blob = await currentCardToBlob();
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      const today = new Date().toISOString().slice(0, 10);
      a.href = url;
      a.download = `hot100-${currentView}-${today}.png`;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      URL.revokeObjectURL(url);
      hintEl.textContent = '已保存 ✓';
      hintEl.style.color = 'var(--sage)';
    } catch (e) {
      hintEl.textContent = '保存失败：' + e.message;
      hintEl.style.color = 'var(--tomato)';
    } finally {
      saveBtn.disabled = false;
    }
  });

  sendBtn.addEventListener('click', async () => {
    sendBtn.disabled = true;
    hintEl.textContent = '生成 & 上传中…';
    hintEl.style.color = '';
    try {
      const blob = await currentCardToBlob();
      const form = new FormData();
      form.append('image', blob, `${currentView}.png`);
      form.append('kind', currentView);
      const r = await fetch('/api/checkin/send-to-feishu', { method: 'POST', body: form });
      const data = await r.json();
      if (!r.ok || !data.ok) throw new Error(data.error || `HTTP ${r.status}`);
      hintEl.textContent = '已发送到飞书 ✓';
      hintEl.style.color = 'var(--sage)';
    } catch (e) {
      hintEl.textContent = '发送失败：' + e.message;
      hintEl.style.color = 'var(--tomato)';
    } finally {
      sendBtn.disabled = false;
    }
  });
})();
