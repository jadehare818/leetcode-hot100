// Cheatsheet 视图 / 编辑 切换

const view = document.getElementById('cheat-view');
const edit = document.getElementById('cheat-edit');
const toggle = document.getElementById('toggle-mode');
const hint = document.getElementById('cheat-hint');

function render() {
  view.innerHTML = marked.parse(edit.value);
}
render();

toggle.addEventListener('click', async () => {
  if (edit.style.display === 'none') {
    // → 编辑模式
    edit.style.display = 'block';
    view.style.display = 'none';
    toggle.textContent = '💾 保存 & 预览';
  } else {
    // → 预览 & 保存
    const r = await fetch('/api/cheatsheet', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({markdown: edit.value}),
    });
    if (r.ok) {
      hint.textContent = '已保存';
      setTimeout(() => hint.textContent = '', 2000);
    }
    render();
    edit.style.display = 'none';
    view.style.display = 'block';
    toggle.textContent = '✏️ 编辑';
  }
});
