// Search results page

import { api } from '../../utils/api.js';
import { tableLoader } from '../../components/loader.js';

let lastQuery = '';
let lastType = 'code';

export async function renderSearch(container, query) {
  if (query) lastQuery = query;
  container.innerHTML = `
    <div class="page">
      <div class="flex items-center gap-3 mb-4">
        <input type="text" class="input" style="width:320px" id="search-input" value="${lastQuery}" placeholder="Search...">
        <select class="select" style="width:120px" id="search-type">
          <option value="code" ${lastType === 'code' ? 'selected' : ''}>Code</option>
          <option value="repos" ${lastType === 'repos' ? 'selected' : ''}>Repos</option>
          <option value="issues" ${lastType === 'issues' ? 'selected' : ''}>Issues</option>
          <option value="prs" ${lastType === 'prs' ? 'selected' : ''}>PRs</option>
        </select>
        <button class="btn btn-primary" id="search-btn">Search</button>
      </div>
      <div class="card" id="search-results"></div>
    </div>
  `;

  const input = container.querySelector('#search-input');
  const typeSelect = container.querySelector('#search-type');
  const resultsEl = container.querySelector('#search-results');
  const btn = container.querySelector('#search-btn');

  const doSearch = () => {
    lastQuery = input.value.trim();
    lastType = typeSelect.value;
    if (lastQuery) runSearch(resultsEl);
  };

  btn.onclick = doSearch;
  input.onkeydown = (e) => { if (e.key === 'Enter') doSearch(); };

  if (lastQuery) await runSearch(resultsEl);
  else resultsEl.innerHTML = `<div class="empty-state"><div class="icon">⌕</div><div class="title">Search your organization</div><div class="desc">Search code, repositories, issues, and pull requests.</div></div>`;
}

async function runSearch(el) {
  el.innerHTML = tableLoader(5, 3);
  try {
    const data = await api.get('/api/search', { q: lastQuery, type: lastType });
    const items = data.items || [];

    if (!items.length) {
      el.innerHTML = `<div class="empty-state"><div class="title">No results</div><div class="desc">No matches found for "${lastQuery}"</div></div>`;
      return;
    }

    let html = `<table class="table"><thead><tr><th>Result</th><th>Details</th><th></th></tr></thead><tbody>`;
    for (const item of items.slice(0, 30)) {
      const name = item.full_name || item.name || item.title || item.path || '—';
      const desc = item.description || item.body?.substring(0, 80) || item.repository?.full_name || '';
      const url = item.html_url || '';
      html += `<tr><td class="font-medium">${esc(name)}</td><td class="text-xs text-muted truncate" style="max-width:400px">${esc(desc)}</td><td>${url ? `<a href="${url}" target="_blank" class="text-xs text-muted">↗</a>` : ''}</td></tr>`;
    }
    el.innerHTML = html + '</tbody></table>';
    if (items.length > 30) el.innerHTML += `<div class="text-xs text-muted" style="padding:12px 16px">Showing 30 of ${data.total_count || items.length} results</div>`;
  } catch (e) {
    el.innerHTML = `<div class="empty-state"><div class="icon">⚠</div><div class="title">Search failed</div><div class="desc">${e.message}</div></div>`;
  }
}

function esc(str) {
  const d = document.createElement('div');
  d.textContent = str || '';
  return d.innerHTML;
}
