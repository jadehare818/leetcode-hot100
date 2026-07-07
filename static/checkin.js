// 打卡卡片：拉 /api/checkin → 渲染成漂亮 HTML → 用 html2canvas 存图。

(function() {
  const openBtn = document.getElementById('open-checkin-card');
  const backdrop = document.getElementById('checkin-backdrop');
  const closeBtn = document.getElementById('close-checkin');
  const saveBtn = document.getElementById('save-checkin');
  const cardEl = document.getElementById('checkin-card');
  const hintEl = document.getElementById('checkin-hint');
  if (!openBtn || !backdrop) return;

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
    const filled = Math.round(done / total * 24);
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

  function render(d) {
    const doneToday = d.solved.length + d.reviewed.length;
    const finish = d.finish;
    const finishStr = finish.reachable && finish.days_left != null && finish.days_left > 0
      ? `${finish.days_left} 天 · ${finish.finish_date}`
      : (finish.days_left === 0 ? '已刷完 🎉' : '—');

    cardEl.innerHTML = `
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
          <span class="cc-chip cc-chip-streak">🔥 连续 ${d.streak} 天</span>
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

  async function open_() {
    hintEl.textContent = '加载中…';
    hintEl.style.color = '';
    backdrop.hidden = false;
    try {
      const r = await fetch('/api/checkin');
      const d = await r.json();
      render(d);
      hintEl.textContent = '';
    } catch (e) {
      hintEl.textContent = '加载失败：' + e.message;
      hintEl.style.color = 'var(--tomato)';
    }
  }
  function close_() { backdrop.hidden = true; }

  openBtn.addEventListener('click', open_);
  closeBtn.addEventListener('click', close_);
  backdrop.addEventListener('click', (e) => { if (e.target === backdrop) close_(); });
  document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape' && !backdrop.hidden) close_();
  });

  saveBtn.addEventListener('click', async () => {
    if (typeof html2canvas !== 'function') {
      hintEl.textContent = 'html2canvas 未加载';
      hintEl.style.color = 'var(--tomato)';
      return;
    }
    saveBtn.disabled = true;
    hintEl.textContent = '生成中…';
    hintEl.style.color = '';
    try {
      // 高清导出：pixelRatio 2x
      const canvas = await html2canvas(cardEl, {
        scale: 2,
        backgroundColor: null,
        useCORS: true,
        logging: false,
      });
      const dataUrl = canvas.toDataURL('image/png');
      const a = document.createElement('a');
      const today = document.querySelector('.cc-eyebrow')?.textContent?.split(' ')[0] || 'checkin';
      a.href = dataUrl;
      a.download = `hot100-${today}.png`;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      hintEl.textContent = '已保存 ✓';
      hintEl.style.color = 'var(--sage)';
    } catch (e) {
      hintEl.textContent = '保存失败：' + e.message;
      hintEl.style.color = 'var(--tomato)';
    } finally {
      saveBtn.disabled = false;
    }
  });
})();
