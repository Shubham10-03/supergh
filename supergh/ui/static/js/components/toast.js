// Toast notification system

let container = null;

function ensureContainer() {
  if (container) return container;
  container = document.createElement('div');
  container.className = 'toast-container';
  document.body.appendChild(container);
  return container;
}

function show(type, message, duration = 4000) {
  const c = ensureContainer();
  const el = document.createElement('div');
  el.className = `toast toast-${type}`;

  const icons = { success: '✓', error: '✕', warning: '⚠', info: 'ℹ' };
  el.innerHTML = `
    <span class="icon">${icons[type] || 'ℹ'}</span>
    <span class="msg">${escapeHtml(message)}</span>
    <span class="close-btn" onclick="this.parentElement.remove()">×</span>
  `;

  c.appendChild(el);

  if (duration > 0) {
    setTimeout(() => {
      el.classList.add('leaving');
      setTimeout(() => el.remove(), 200);
    }, duration);
  }
}

function escapeHtml(str) {
  const div = document.createElement('div');
  div.textContent = str;
  return div.innerHTML;
}

export const toast = {
  success: (msg) => show('success', msg),
  error: (msg) => show('error', msg, 6000),
  warning: (msg) => show('warning', msg, 5000),
  info: (msg) => show('info', msg),
};
