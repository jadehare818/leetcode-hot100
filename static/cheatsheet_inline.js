// 每题 cheatsheet 内联编辑器：一个通用组件。
//
// 使用方式（模板里）：
//   <button class="btn cs-toggle" data-pid="{{ p.id }}">📝 Cheatsheet</button>
//   <div class="cs-panel" data-pid="{{ p.id }}"></div>   ← 空容器，第一次展开时注入 UI
//
// 组件行为：
//   - 点按钮切换 panel 显示 / 隐藏
//   - 首次展开时 GET /api/problem/{pid}/cheatsheet 拉内容
//   - 默认预览模式（marked 渲染）；点"编辑"切到 textarea；点"保存 & 预览"发 POST 存回

const CS_LOADED = new Set();

function _renderPanel(panel, md) {
  const escapedInitial = md || '';
  panel.innerHTML = `
    <div class="cs-toolbar">
      <button class="btn cs-mode-btn">✏️ 编辑</button>
      <span class="hint cs-hint"></span>
    </div>
    <div class="markdown-body cs-view"></div>
    <textarea class="cs-edit" style="display:none" placeholder="随手写下这题的思路 / 代码 / 常错点。支持 markdown。"></textarea>
  `;
  const view = panel.querySelector('.cs-view');
  const edit = panel.querySelector('.cs-edit');
  const btn = panel.querySelector('.cs-mode-btn');
  const hint = panel.querySelector('.cs-hint');
  edit.value = escapedInitial;
  view.innerHTML = escapedInitial ? marked.parse(escapedInitial) : '<p class="empty">还没写笔记，点右上"编辑"开始。</p>';

  btn.addEventListener('click', async () => {
    if (edit.style.display === 'none') {
      // → 编辑
      edit.style.display = 'block';
      view.style.display = 'none';
      btn.textContent = '💾 保存 & 预览';
      edit.focus();
    } else {
      // → 保存 & 预览
      const pid = panel.dataset.pid;
      const r = await fetch(`/api/problem/${pid}/cheatsheet`, {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({cheatsheet: edit.value}),
      });
      if (r.ok) {
        hint.textContent = '已保存';
        setTimeout(() => hint.textContent = '', 1500);
      }
      view.innerHTML = edit.value ? marked.parse(edit.value) : '<p class="empty">还没写笔记。</p>';
      edit.style.display = 'none';
      view.style.display = 'block';
      btn.textContent = '✏️ 编辑';
    }
  });
}

async function _openPanel(pid, panel) {
  if (!CS_LOADED.has(pid)) {
    const r = await fetch(`/api/problem/${pid}/cheatsheet`);
    const data = await r.json();
    _renderPanel(panel, data.cheatsheet || '');
    CS_LOADED.add(pid);
  }
  panel.classList.add('open');
}

function _closePanel(panel) {
  panel.classList.remove('open');
}

document.querySelectorAll('.cs-toggle').forEach(btn => {
  btn.addEventListener('click', async () => {
    const pid = btn.dataset.pid;
    const panel = document.querySelector(`.cs-panel[data-pid="${pid}"]`);
    if (!panel) return;
    if (panel.classList.contains('open')) {
      _closePanel(panel);
    } else {
      await _openPanel(pid, panel);
    }
  });
});
