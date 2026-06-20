// Issues list page — scroll-triggered pagination

import { api } from '../../utils/api.js';
import { store } from '../../store.js';
import { toast } from '../../components/toast.js';
import { tableLoader } from '../../components/loader.js';
import { openModal, closeModal, confirmDialog } from '../../components/modal.js';

let issues = [];
let stateFilter = 'open';
let searchTerm = '';
let currentPage = 1;
let hasMore = true;
let loading = false;
let observer = null;

export async function renderIssuesList(container, repoName) {
  if (observer) { observer.disconnect(); observer = null; }
  issues = [];
  currentPage = 1;
  hasMore = true;

  container.innerHTML = `
    <div class="page">
      <div class="flex items-center justify-between mb-4">
        <div class="flex items-center gap-3">
          <select class="select" style="width:120px" id="issue-state-filter">
            <option value="open" ${stateFilter === 'open' ? 'selected' : ''}>Open</option>
            <option value="closed" ${stateFilter === 'closed' ? 'selected' : ''}>Closed</option>
            <option value="all" ${stateFilter === 'all' ? 'selected' : ''}>All</option>
          </select>
          <input type="text" class="input" style="width:220px" placeholder="Search issues..." id="issue-search" value="${searchTerm}">
        </div>
        <button class="btn btn-primary" id="btn-create-issue" ${!store.hasPermission('issues', 'write') ? 'disabled' : ''}>+ New issue</button>
      </div>
      <div class="card" id="issues-table">${tableLoader(6, 5)}</div>
      <div id="issue-sentinel" style="height:1px"></div>
      <div class="text-xs text-muted mt-2" id="issue-count"></div>
    </div>
  `;

  const tableEl = container.querySelector('#issues-table');
  const countEl = container.querySelector('#issue-count');
  const sentinel = container.querySelector('#issue-sentinel');

  container.querySelector('#issue-state-filter').onchange = (e) => {
    stateFilter = e.target.value;
    issues = []; currentPage = 1; hasMore = true;
    loadPage(tableEl, countEl, repoName);
  };

  let issueSearchTimeout = null;
  const searchInput = container.querySelector('#issue-search');
  searchInput.oninput = () => {
    searchTerm = searchInput.value;
    renderTable(tableEl, countEl, repoName);
    if (issueSearchTimeout) clearTimeout(issueSearchTimeout);
    if (searchTerm.length >= 2) {
      issueSearchTimeout = setTimeout(() => {
        const filtered = getFilteredIssues();
        if (filtered.length === 0) renderTable(tableEl, countEl, repoName);
      }, 2000);
    }
  };

  container.querySelector('#btn-create-issue').onclick = () => showCreateModal(repoName, tableEl, countEl);

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
    const res = await api.get(`/api/repos/${repoName}/issues`, { state: stateFilter, page: currentPage, per_page: 30 });
    const items = res.items || [];
    hasMore = res.has_more;
    issues = issues.concat(items);
    currentPage++;
    renderTable(tableEl, countEl, repoName);
  } catch (e) {
    if (currentPage === 1) tableEl.innerHTML = `<div class="empty-state"><div class="icon">⚠</div><div class="title">Failed to load</div><div class="desc">${e.message}</div></div>`;
  } finally { loading = false; }
}

function getFilteredIssues() {
  if (!searchTerm) return issues;
  const s = searchTerm.toLowerCase();
  return issues.filter(i =>
    i.title.toLowerCase().includes(s) ||
    i.author.toLowerCase().includes(s) ||
    i.labels.some(l => l.toLowerCase().includes(s)) ||
    String(i.number).includes(s)
  );
}

function renderTable(tableEl, countEl, repoName) {
  const filtered = getFilteredIssues();
  if (!filtered.length && !loading) {
    tableEl.innerHTML = `<div class="empty-state"><div class="title">${searchTerm ? 'No matching issues' : 'No issues'}</div><div class="desc">${searchTerm ? 'Try a different search term' : `No ${stateFilter} issues.`}</div></div>`;
    countEl.textContent = ''; return;
  }

  let html = `<table class="table"><thead><tr><th>#</th><th>Title</th><th>Author</th><th>Labels</th><th>Comments</th><th>Updated</th><th></th></tr></thead><tbody>`;
  for (const i of filtered) {
    const labels = i.labels.map(l => `<span class="badge badge-blue">${esc(l)}</span>`).join(' ');
    html += `<tr>
      <td class="text-blue font-medium">#${i.number}</td>
      <td class="truncate" style="max-width:280px">${esc(i.title)}</td>
      <td class="text-orange">${i.author}</td>
      <td>${labels || '—'}</td>
      <td>${i.comments || '0'}</td>
      <td class="text-xs text-muted">${i.updated}</td>
      <td class="flex gap-2">
        ${i.state === 'open' ? `<button class="btn btn-ghost btn-sm close-btn" data-n="${i.number}">Close</button>` : `<button class="btn btn-ghost btn-sm reopen-btn" data-n="${i.number}">Reopen</button>`}
        <a href="${i.url}" target="_blank" class="btn btn-ghost btn-sm">↗</a>
      </td>
    </tr>`;
  }
  html += '</tbody></table>';
  if (loading && hasMore && currentPage > 2) html += `<div style="padding:12px 16px">${tableLoader(2, 5)}</div>`;
  tableEl.innerHTML = html;
  countEl.textContent = `${filtered.length} issues${hasMore && !searchTerm ? ' (scroll for more)' : ''}`;

  tableEl.querySelectorAll('.close-btn').forEach(btn => {
    btn.onclick = async () => {
      const yes = await confirmDialog(`Close issue #${btn.dataset.n}?`, { title: 'Close Issue', confirmLabel: 'Close' });
      if (!yes) return;
      try {
        await api.patch(`/api/repos/${repoName}/issues/${btn.dataset.n}`, { state: 'closed' });
        toast.success(`Issue #${btn.dataset.n} closed.`);
        const idx = issues.findIndex(x => x.number === parseInt(btn.dataset.n));
        if (idx >= 0) issues[idx].state = 'closed';
        renderTable(tableEl, countEl, repoName);
      } catch (e) {}
    };
  });

  tableEl.querySelectorAll('.reopen-btn').forEach(btn => {
    btn.onclick = async () => {
      try {
        await api.patch(`/api/repos/${repoName}/issues/${btn.dataset.n}`, { state: 'open' });
        toast.success(`Issue #${btn.dataset.n} reopened.`);
        const idx = issues.findIndex(x => x.number === parseInt(btn.dataset.n));
        if (idx >= 0) issues[idx].state = 'open';
        renderTable(tableEl, countEl, repoName);
      } catch (e) {}
    };
  });
}

function showCreateModal(repoName, tableEl, countEl) {
  openModal('New Issue', `
    <div class="form-group"><label class="form-label">Title</label><input type="text" class="input" id="issue-title" placeholder="Brief description"></div>
    <div class="form-group"><label class="form-label">Body</label><textarea class="input" id="issue-body" rows="4" style="resize:vertical" placeholder="Details..."></textarea></div>
    <div class="form-group"><label class="form-label">Labels (comma-separated)</label><input type="text" class="input" id="issue-labels" placeholder="bug, enhancement"></div>
    <div class="form-group"><label class="form-label">Assignees (comma-separated)</label><input type="text" class="input" id="issue-assignees" placeholder="user1, user2"></div>
  `, [
    { label: 'Cancel', cls: 'btn-ghost', onClick: () => closeModal() },
    { label: 'Create issue', cls: 'btn-primary', onClick: async () => {
      const title = document.getElementById('issue-title')?.value.trim();
      const body = document.getElementById('issue-body')?.value.trim();
      const labelsRaw = document.getElementById('issue-labels')?.value.trim();
      const assigneesRaw = document.getElementById('issue-assignees')?.value.trim();
      if (!title) { toast.warning('Title is required.'); return; }
      const payload = { title, body };
      if (labelsRaw) payload.labels = labelsRaw.split(',').map(s => s.trim()).filter(Boolean);
      if (assigneesRaw) payload.assignees = assigneesRaw.split(',').map(s => s.trim()).filter(Boolean);
      try {
        const r = await api.post(`/api/repos/${repoName}/issues`, payload);
        toast.success(`Issue #${r.number} created.`); closeModal();
        issues = []; currentPage = 1; hasMore = true;
        await loadPage(tableEl, countEl, repoName);
      } catch (e) {}
    }},
  ]);
  setTimeout(() => document.getElementById('issue-title')?.focus(), 100);
}

function esc(str) { const d = document.createElement('div'); d.textContent = str || ''; return d.innerHTML; }
