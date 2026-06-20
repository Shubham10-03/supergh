// PR list page — scroll-triggered pagination

import { api } from '../../utils/api.js';
import { store } from '../../store.js';
import { toast } from '../../components/toast.js';
import { tableLoader } from '../../components/loader.js';
import { openModal, closeModal } from '../../components/modal.js';

let prs = [];
let stateFilter = 'open';
let searchTerm = '';
let currentPage = 1;
let hasMore = true;
let loading = false;
let observer = null;

export async function renderPRList(container, repoName) {
  if (observer) { observer.disconnect(); observer = null; }
  prs = [];
  currentPage = 1;
  hasMore = true;

  container.innerHTML = `
    <div class="page">
      <div class="flex items-center justify-between mb-4">
        <div class="flex items-center gap-3">
          <select class="select" style="width:120px" id="pr-state-filter">
            <option value="open" ${stateFilter === 'open' ? 'selected' : ''}>Open</option>
            <option value="closed" ${stateFilter === 'closed' ? 'selected' : ''}>Closed</option>
            <option value="all" ${stateFilter === 'all' ? 'selected' : ''}>All</option>
          </select>
          <input type="text" class="input" style="width:220px" placeholder="Search pull requests..." id="pr-search" value="${searchTerm}">
        </div>
        <button class="btn btn-primary" id="btn-create-pr" ${!store.hasPermission('pulls', 'write') ? 'disabled' : ''}>+ New pull request</button>
      </div>
      <div class="card" id="pr-table">${tableLoader(6, 5)}</div>
      <div id="pr-sentinel" style="height:1px"></div>
      <div class="text-xs text-muted mt-2" id="pr-count"></div>
    </div>
  `;

  const tableEl = container.querySelector('#pr-table');
  const countEl = container.querySelector('#pr-count');
  const sentinel = container.querySelector('#pr-sentinel');

  container.querySelector('#pr-state-filter').onchange = (e) => {
    stateFilter = e.target.value;
    prs = []; currentPage = 1; hasMore = true;
    loadPage(tableEl, countEl, repoName);
  };

  let prSearchTimeout = null;
  const searchInput = container.querySelector('#pr-search');
  searchInput.oninput = () => {
    searchTerm = searchInput.value;
    renderTable(tableEl, countEl, repoName);
    if (prSearchTimeout) clearTimeout(prSearchTimeout);
    if (searchTerm.length >= 2) {
      prSearchTimeout = setTimeout(() => {
        const filtered = getFilteredPRs();
        if (filtered.length === 0) renderTable(tableEl, countEl, repoName);
      }, 2000);
    }
  };

  container.querySelector('#btn-create-pr').onclick = () => showCreateModal(repoName, tableEl, countEl);

  await loadPage(tableEl, countEl, repoName);

  if (observer) observer.disconnect();
  observer = new IntersectionObserver((entries) => {
    if (entries[0].isIntersecting && hasMore && !loading) loadPage(tableEl, countEl, repoName);
  }, { root: container.closest('.content'), threshold: 0.1 });
  observer.observe(sentinel);
}

async function loadPage(tableEl, countEl, repoName) {
  if (loading || !hasMore) return;
  loading = true;
  if (currentPage === 1) tableEl.innerHTML = tableLoader(6, 5);

  try {
    const res = await api.get(`/api/repos/${repoName}/pulls`, { state: stateFilter, page: currentPage, per_page: 30 });
    const items = res.items || [];
    hasMore = res.has_more;
    prs = prs.concat(items);
    currentPage++;
    renderTable(tableEl, countEl, repoName);
  } catch (e) {
    if (currentPage === 1) tableEl.innerHTML = `<div class="empty-state"><div class="icon">⚠</div><div class="title">Failed to load</div><div class="desc">${e.message}</div></div>`;
  } finally { loading = false; }
}

function getFilteredPRs() {
  if (!searchTerm) return prs;
  const s = searchTerm.toLowerCase();
  return prs.filter(p =>
    p.title.toLowerCase().includes(s) ||
    p.author.toLowerCase().includes(s) ||
    p.branch.toLowerCase().includes(s) ||
    String(p.number).includes(s)
  );
}

function renderTable(tableEl, countEl, repoName) {
  const filtered = getFilteredPRs();
  if (!filtered.length && !loading) {
    tableEl.innerHTML = `<div class="empty-state"><div class="title">${searchTerm ? 'No matching pull requests' : 'No pull requests'}</div><div class="desc">${searchTerm ? 'Try a different search term' : `No ${stateFilter} pull requests.`}</div></div>`;
    countEl.textContent = ''; return;
  }

  let html = `<table class="table"><thead><tr><th>#</th><th>Title</th><th>Author</th><th>Branch</th><th>Updated</th><th></th></tr></thead><tbody>`;
  for (const p of filtered) {
    const draft = p.draft ? '<span class="badge badge-neutral" style="margin-left:6px">Draft</span>' : '';
    html += `<tr>
      <td class="text-blue font-medium">#${p.number}</td>
      <td class="truncate" style="max-width:280px">${esc(p.title)}${draft}</td>
      <td class="text-orange">${p.author}</td>
      <td class="mono text-xs text-muted">${p.branch} → ${p.base}</td>
      <td class="text-xs text-muted">${p.updated}</td>
      <td class="flex gap-2">
        ${p.state === 'open' ? `<button class="btn btn-primary btn-sm merge-btn" data-number="${p.number}">Merge</button>` : ''}
        <a href="${p.url}" target="_blank" class="btn btn-ghost btn-sm">↗</a>
      </td>
    </tr>`;
  }
  html += '</tbody></table>';
  if (loading && hasMore && currentPage > 2) html += `<div style="padding:12px 16px">${tableLoader(2, 5)}</div>`;
  tableEl.innerHTML = html;
  countEl.textContent = `${filtered.length} pull requests${hasMore && !searchTerm ? ' (scroll for more)' : ''}`;

  tableEl.querySelectorAll('.merge-btn').forEach(btn => {
    btn.onclick = () => showMergeModal(repoName, parseInt(btn.dataset.number), tableEl, countEl);
  });
}

function showCreateModal(repoName, tableEl, countEl) {
  openModal('New Pull Request', `
    <div class="form-group"><label class="form-label">Title</label><input type="text" class="input" id="pr-title" placeholder="What does this PR do?"></div>
    <div class="form-group"><label class="form-label">Head branch</label><input type="text" class="input" id="pr-head" placeholder="feature-branch"></div>
    <div class="form-group"><label class="form-label">Base branch</label><input type="text" class="input" id="pr-base" value="main" placeholder="main"></div>
    <div class="form-group"><label class="form-label">Description</label><textarea class="input" id="pr-body" rows="3" style="resize:vertical" placeholder="Optional..."></textarea></div>
    <div class="form-group"><label style="display:flex;align-items:center;gap:8px;cursor:pointer"><input type="checkbox" id="pr-draft"><span class="text-sm">Draft</span></label></div>
  `, [
    { label: 'Cancel', cls: 'btn-ghost', onClick: () => closeModal() },
    { label: 'Create', cls: 'btn-primary', onClick: async () => {
      const title = document.getElementById('pr-title')?.value.trim();
      const head = document.getElementById('pr-head')?.value.trim();
      const base = document.getElementById('pr-base')?.value.trim() || 'main';
      const body = document.getElementById('pr-body')?.value.trim();
      const draft = document.getElementById('pr-draft')?.checked;
      if (!title) { toast.warning('Title is required.'); return; }
      if (!head) { toast.warning('Head branch is required.'); return; }
      try {
        const r = await api.post(`/api/repos/${repoName}/pulls`, { title, head, base, body, draft });
        toast.success(`PR #${r.number} created.`); closeModal();
        prs = []; currentPage = 1; hasMore = true;
        await loadPage(tableEl, countEl, repoName);
      } catch (e) {}
    }},
  ]);
  setTimeout(() => document.getElementById('pr-title')?.focus(), 100);
}

function showMergeModal(repoName, number, tableEl, countEl) {
  openModal(`Merge PR #${number}`, `
    <div class="form-group"><label class="form-label">Method</label><select class="select" id="merge-method"><option value="squash">Squash and merge</option><option value="merge">Merge commit</option><option value="rebase">Rebase</option></select></div>
  `, [
    { label: 'Cancel', cls: 'btn-ghost', onClick: () => closeModal() },
    { label: 'Merge', cls: 'btn-primary', onClick: async () => {
      const method = document.getElementById('merge-method')?.value || 'squash';
      try {
        await api.put(`/api/repos/${repoName}/pulls/${number}/merge`, { merge_method: method });
        toast.success(`PR #${number} merged.`); closeModal();
        prs = prs.filter(p => p.number !== number);
        renderTable(tableEl, countEl, repoName);
      } catch (e) {}
    }},
  ]);
}

function esc(str) { const d = document.createElement('div'); d.textContent = str || ''; return d.innerHTML; }
