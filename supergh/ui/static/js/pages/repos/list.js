// Repos list page — scroll-triggered pagination + search

import { api } from '../../utils/api.js';
import { store } from '../../store.js';
import { toast } from '../../components/toast.js';
import { tableLoader } from '../../components/loader.js';
import { openModal, closeModal } from '../../components/modal.js';

let repos = [];
let filter = '';
let currentPage = 1;
let hasMore = true;
let loading = false;
let observer = null;

export async function renderReposList(container) {
  if (observer) { observer.disconnect(); observer = null; }
  repos = [];
  currentPage = 1;
  hasMore = true;

  container.innerHTML = `
    <div class="page">
      <div class="flex items-center justify-between mb-4">
        <input type="text" class="input" style="width:280px" placeholder="Search repositories..." id="repo-filter" value="${filter}">
        <button class="btn btn-primary" id="btn-create-repo" ${!store.hasPermission('repos', 'write') ? 'disabled title="You do not have permission to create repositories"' : ''}>+ New repository</button>
      </div>
      <div class="card" id="repos-table">${tableLoader(8, 5)}</div>
      <div id="scroll-sentinel" style="height:1px"></div>
      <div class="text-xs text-muted mt-2" id="repo-count"></div>
    </div>
  `;

  const filterInput = container.querySelector('#repo-filter');
  const tableEl = container.querySelector('#repos-table');
  const countEl = container.querySelector('#repo-count');
  const sentinel = container.querySelector('#scroll-sentinel');

  let searchTimeout = null;
  filterInput.oninput = () => {
    filter = filterInput.value;
    // Always show client-side results immediately
    renderTable(tableEl, countEl);
    // Clear any pending server search
    if (searchTimeout) clearTimeout(searchTimeout);
    // Schedule server search after 2s of no typing
    if (filter.length >= 2) {
      searchTimeout = setTimeout(async () => {
        const clientFiltered = getClientFiltered();
        if (clientFiltered.length === 0) {
          await serverSearch(tableEl, countEl);
        }
      }, 2000);
    }
  };

  container.querySelector('#btn-create-repo').onclick = () => showCreateModal(tableEl, countEl);

  // Load first page
  await loadPage(tableEl, countEl);

  // Observe scroll — load more when sentinel is visible
  if (observer) observer.disconnect();
  observer = new IntersectionObserver((entries) => {
    if (entries[0].isIntersecting && hasMore && !loading) {
      loadPage(tableEl, countEl);
    }
  }, { root: container.closest('.content'), threshold: 0.1 });
  observer.observe(sentinel);
}

async function loadPage(tableEl, countEl) {
  if (loading || !hasMore) return;
  loading = true;

  if (currentPage === 1) tableEl.innerHTML = tableLoader(8, 5);

  try {
    const res = await api.get('/api/repos', { page: currentPage, per_page: 30 });
    const items = res.items || [];
    hasMore = res.has_more;
    repos = repos.concat(items);
    currentPage++;
    renderTable(tableEl, countEl);
  } catch (e) {
    if (currentPage === 1) {
      tableEl.innerHTML = `<div class="empty-state"><div class="icon">⚠</div><div class="title">Failed to load repositories</div><div class="desc">${e.message}</div></div>`;
    }
  } finally {
    loading = false;
  }
}

function getClientFiltered() {
  const f = filter.toLowerCase();
  if (!f) return repos;
  return repos.filter(r =>
    r.name.toLowerCase().includes(f) ||
    (r.language || '').toLowerCase().includes(f) ||
    (r.description || '').toLowerCase().includes(f)
  );
}

async function serverSearch(tableEl, countEl) {
  const searchTerm = filter; // capture current value
  tableEl.innerHTML = tableLoader(4, 5);
  try {
    const res = await api.get('/api/repos-search', { q: searchTerm, per_page: 30 });
    // If user typed more while we were fetching, discard stale results
    if (filter !== searchTerm) return;
    const items = res.items || [];
    if (!items.length) {
      tableEl.innerHTML = `<div class="empty-state"><div class="icon">⌕</div><div class="title">No repositories found</div><div class="desc">No repos matching "${esc(filter)}" in this organization.</div></div>`;
      countEl.textContent = '';
      return;
    }
    // Render search results
    let html = `<table class="table"><thead><tr><th>Repository</th><th>Visibility</th><th>Language</th><th>Issues</th><th>Updated</th><th></th></tr></thead><tbody>`;
    for (const r of items) {
      const visCls = r.visibility === 'private' ? 'badge-orange' : r.visibility === 'internal' ? 'badge-purple' : 'badge-green';
      html += `<tr>
        <td><span class="link repo-link" data-name="${r.name}">${esc(r.name)}</span><div class="text-xs text-muted mt-2" style="max-width:300px">${esc((r.description || '').substring(0, 80))}</div></td>
        <td><span class="badge ${visCls}">${r.visibility}</span></td>
        <td class="text-muted">${r.language || '\u2014'}</td>
        <td>${r.issues}</td>
        <td class="text-xs text-muted">${r.updated}</td>
        <td><a href="${r.url}" target="_blank" class="text-xs text-muted" style="text-decoration:none">\u2197</a></td>
      </tr>`;
    }
    html += '</tbody></table>';
    tableEl.innerHTML = html;
    countEl.textContent = `${items.length} results (searched org)`;

    tableEl.querySelectorAll('.repo-link').forEach(el => {
      el.onclick = () => {
        const repo = items.find(r => r.name === el.dataset.name);
        if (repo) store.update({ selectedRepo: repo, currentPage: 'detail' });
      };
    });
  } catch (e) {
    tableEl.innerHTML = `<div class="empty-state"><div class="icon">\u26A0</div><div class="title">Search failed</div><div class="desc">${e.message}</div></div>`;
  }
}

function renderTable(tableEl, countEl) {
  const filtered = getClientFiltered();

  if (!filtered.length && !loading) {
    tableEl.innerHTML = `<div class="empty-state"><div class="icon">◫</div><div class="title">${filter ? 'No matching repositories' : 'No repositories found'}</div><div class="desc">${filter ? 'Try a different search term' : 'This organization has no repositories yet'}</div></div>`;
    countEl.textContent = '';
    return;
  }

  let html = `<table class="table"><thead><tr><th>Repository</th><th>Visibility</th><th>Language</th><th>Issues</th><th>Updated</th><th></th></tr></thead><tbody>`;
  for (const r of filtered) {
    const visCls = r.visibility === 'private' ? 'badge-orange' : r.visibility === 'internal' ? 'badge-purple' : 'badge-green';
    html += `<tr>
      <td><span class="link repo-link" data-name="${r.name}">${esc(r.name)}</span><div class="text-xs text-muted mt-2" style="max-width:300px">${esc((r.description || '').substring(0, 80))}</div></td>
      <td><span class="badge ${visCls}">${r.visibility}</span></td>
      <td class="text-muted">${r.language || '—'}</td>
      <td>${r.issues}</td>
      <td class="text-xs text-muted">${r.updated}</td>
      <td><a href="${r.url}" target="_blank" class="text-xs text-muted" style="text-decoration:none">↗</a></td>
    </tr>`;
  }
  html += '</tbody></table>';

  if (loading && hasMore && currentPage > 2) html += `<div style="padding:12px 16px">${tableLoader(2, 5)}</div>`;

  tableEl.innerHTML = html;
  countEl.textContent = `${filtered.length} repositories${hasMore ? ' (scroll for more)' : ''}`;

  tableEl.querySelectorAll('.repo-link').forEach(el => {
    el.onclick = () => {
      const repo = repos.find(r => r.name === el.dataset.name);
      if (repo) store.update({ selectedRepo: repo, currentPage: 'detail' });
    };
  });
}

function showCreateModal(tableEl, countEl) {
  openModal('New Repository', `
    <div class="form-group"><label class="form-label">Name</label><input type="text" class="input" id="new-repo-name" placeholder="my-new-repo"></div>
    <div class="form-group"><label class="form-label">Description</label><input type="text" class="input" id="new-repo-desc" placeholder="Optional description"></div>
    <div class="form-group"><label class="form-label">Visibility</label><select class="select" id="new-repo-vis"><option value="private">Private</option><option value="internal">Internal</option><option value="public">Public</option></select></div>
  `, [
    { label: 'Cancel', cls: 'btn-ghost', onClick: () => closeModal() },
    { label: 'Create repository', cls: 'btn-primary', onClick: () => handleCreate(tableEl, countEl) },
  ]);
  setTimeout(() => document.getElementById('new-repo-name')?.focus(), 100);
}

async function handleCreate(tableEl, countEl) {
  const name = document.getElementById('new-repo-name')?.value.trim();
  const desc = document.getElementById('new-repo-desc')?.value.trim();
  const vis = document.getElementById('new-repo-vis')?.value;
  if (!name) { toast.warning('Repository name is required.'); return; }
  if (!/^[a-zA-Z0-9._-]+$/.test(name)) { toast.warning('Invalid repository name.'); return; }
  try {
    await api.post('/api/repos', { name, description: desc, private: vis === 'private', visibility: vis });
    toast.success(`Repository "${name}" created.`);
    closeModal();
    repos = []; currentPage = 1; hasMore = true;
    await loadPage(tableEl, countEl);
  } catch (e) { /* toasted */ }
}

function debounce(fn, ms) {
  let timer;
  return (...args) => { clearTimeout(timer); timer = setTimeout(() => fn(...args), ms); };
}

function esc(str) { const d = document.createElement('div'); d.textContent = str || ''; return d.innerHTML; }
