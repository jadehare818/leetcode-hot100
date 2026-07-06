// 每题"思路"内联编辑器：单行 textarea + 保存。跟 cheatsheet_inline.js 用同样的展开/收起模式，
// 但更轻量 —— 无 markdown 预览。
//
// 模板里的用法：
//   <button class="btn note-toggle" data-pid="{{ p.id }}">💡 思路</button>
//   <div class="note-panel" data-pid="{{ p.id }}"></div>

const NOTE_LOADED = new Set();

function _renderNotePanel(panel, note) {
  panel.innerHTML = `
    <textarea class="note-edit" placeholder="一句话思路（关键 idea）">${note.replace(/</g, '&lt;')}</textarea>
    <div class="note-toolbar">
      <button class="btn primary note-save-btn">💾 保存</button>
      <span class="hint note-hint"></span>
    </div>
  `;
  const edit = panel.querySelector('.note-edit');
  const btn = panel.querySelector('.note-save-btn');
  const hint = panel.querySelector('.note-hint');

  btn.addEventListener('click', async () => {
    const pid = panel.dataset.pid;
    const r = await fetch(`/api/problem/${pid}/note`, {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({note: edit.value}),
    });
    if (r.ok) {
      hint.textContent = '已保存';
      // 若卡片有 preview 摘要，同步更新
      const preview = document.querySelector(`.note-preview[data-pid="${pid}"]`);
      if (preview) {
        const short = edit.value.length > 60 ? edit.value.slice(0, 60) + '…' : edit.value;
        preview.textContent = short ? `💡 ${short}` : '';
      }
      setTimeout(() => hint.textContent = '', 1500);
    }
  });
}

async function _openNotePanel(pid, panel) {
  if (!NOTE_LOADED.has(pid)) {
    const r = await fetch(`/api/problem/${pid}/note`);
    const data = await r.json();
    _renderNotePanel(panel, data.note || '');
    NOTE_LOADED.add(pid);
  }
  panel.classList.add('open');
}

document.querySelectorAll('.note-toggle').forEach(btn => {
  btn.addEventListener('click', async () => {
    const pid = btn.dataset.pid;
    const panel = document.querySelector(`.note-panel[data-pid="${pid}"]`);
    if (!panel) return;
    if (panel.classList.contains('open')) {
      panel.classList.remove('open');
    } else {
      await _openNotePanel(pid, panel);
    }
  });
});
