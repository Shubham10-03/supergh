// Formatting utilities

export function relativeDate(dateStr) {
  if (!dateStr) return '';
  const date = new Date(dateStr);
  const now = new Date();
  const diff = Math.floor((now - date) / 1000);

  if (diff < 60) return 'just now';
  if (diff < 3600) return `${Math.floor(diff / 60)}m ago`;
  if (diff < 86400) return `${Math.floor(diff / 3600)}h ago`;
  if (diff < 604800) return `${Math.floor(diff / 86400)}d ago`;
  return dateStr.substring(0, 10);
}

export function truncate(str, len = 60) {
  if (!str) return '';
  return str.length > len ? str.substring(0, len) + '…' : str;
}

export function escapeHtml(str) {
  const d = document.createElement('div');
  d.textContent = str || '';
  return d.innerHTML;
}

export function pluralize(count, singular, plural) {
  return `${count} ${count === 1 ? singular : (plural || singular + 's')}`;
}
