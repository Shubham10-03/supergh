// Compliance page — scroll-triggered pagination + expandable rule details

import { api } from '../../utils/api.js';
import { tableLoader } from '../../components/loader.js';

let items = [];
let currentPage = 1;
let hasMore = true;
let loading = false;
let observer = null;
let expandedRepo = null;

export async function renderCompliance(container) {
  items = [];
  currentPage = 1;
  hasMore = true;
  expandedRepo = null;

  container.innerHTML = `
    <div class="page">
      <div class="flex items-center justify-between mb-4">
        <div>
          <span class="font-medium">Branch Protection Compliance</span>
          <p class="text-xs text-muted mt-2">Default branch protection rules across all repositories.</p>
        </div>
        <button class="btn btn-sm" id="refresh-compliance">Refresh</button>
      </div>
      <div class="card" id="compliance-table">${tableLoader(8, 6)}</div>
      <div id="compliance-sentinel" style="height:1px"></div>
      <div class="text-xs text-muted mt-2" id="compliance-count"></div>
    </div>
  `;

  const tableEl = container.querySelector('#compliance-table');
  const countEl = container.querySelector('#compliance-count');
  const sentinel = container.querySelector('#compliance-sentinel');

  container.querySelector('#refresh-compliance').onclick = () => {
    items = []; currentPage = 1; hasMore = true; expandedRepo = null;
    loadPage(tableEl, countEl);
  };

  await loadPage(tableEl, countEl);

  if (observer) observer.disconnect();
  observer = new IntersectionObserver((entries) => {
    if (entries[0].isIntersecting && hasMore && !loading) loadPage(tableEl, countEl);
  }, { root: container.closest('.content'), threshold: 0.1 });
  observer.observe(sentinel);
}

async function loadPage(tableEl, countEl) {
  if (loading || !hasMore) return;
  loading = true;
  if (currentPage === 1) tableEl.innerHTML = tableLoader(8, 6);

  try {
    const res = await api.get('/api/compliance', { page: currentPage, per_page: 20 });
    const pageItems = res.items || [];
    hasMore = res.has_more;
    items = items.concat(pageItems);
    currentPage++;
    renderTable(tableEl, countEl);
  } catch (e) {
    if (currentPage === 1) tableEl.innerHTML = `<div class="empty-state"><div class="icon">⚠</div><div class="title">Failed to load compliance data</div><div class="desc">${e.message}</div></div>`;
  } finally { loading = false; }
}

function renderTable(tableEl, countEl) {
  if (!items.length && !loading) {
    tableEl.innerHTML = `<div class="empty-state"><div class="icon">◈</div><div class="title">No compliance data</div><div class="desc">Could not retrieve branch protection information.</div></div>`;
    countEl.textContent = '';
    return;
  }

  const protectedCount = items.filter(r => r.protected).length;
  const unprotectedCount = items.filter(r => !r.protected).length;

  let html = `
    <div style="padding:12px 16px;border-bottom:1px solid var(--border);display:flex;gap:16px">
      <span class="badge badge-green">${protectedCount} protected</span>
      <span class="badge badge-red">${unprotectedCount} unprotected</span>
    </div>
    <table class="table"><thead><tr><th>Repository</th><th>Branch</th><th>Protected</th><th>Reviews</th><th>Status Checks</th><th>Admins Enforced</th><th></th></tr></thead><tbody>`;

  for (const r of items) {
    const protCls = r.protected ? 'badge-green' : 'badge-red';
    const isExpanded = expandedRepo === r.repo;
    html += `<tr class="compliance-row" data-repo="${r.repo}">
      <td class="font-medium">${r.repo}</td>
      <td class="mono text-xs text-muted">${r.branch}</td>
      <td><span class="badge ${protCls}">${r.protected ? 'Yes' : 'No'}</span></td>
      <td>${r.reviews_required != null ? r.reviews_required : '—'}</td>
      <td>${r.status_checks ? '<span class="text-green">✓</span>' : '<span class="text-muted">✕</span>'}</td>
      <td>${r.enforce_admins ? '<span class="text-green">✓</span>' : '<span class="text-muted">✕</span>'}</td>
      <td>${r.protected ? `<button class="btn btn-ghost btn-sm expand-btn" data-repo="${r.repo}">${isExpanded ? '▾ Hide' : '▸ Rules'}</button>` : ''}</td>
    </tr>`;

    if (isExpanded && r.protected) {
      html += `<tr><td colspan="7" style="padding:0;background:var(--s1)">
        <div style="padding:16px 24px;font-size:12px">
          ${renderRules(r)}
        </div>
      </td></tr>`;
    }
  }

  html += '</tbody></table>';
  if (loading) html += `<div style="padding:12px 16px">${tableLoader(3, 6)}</div>`;
  tableEl.innerHTML = html;
  countEl.textContent = `${items.length} repositories${hasMore ? ' (scroll for more)' : ''}`;

  tableEl.querySelectorAll('.expand-btn').forEach(btn => {
    btn.onclick = (e) => {
      e.stopPropagation();
      expandedRepo = expandedRepo === btn.dataset.repo ? null : btn.dataset.repo;
      renderTable(tableEl, countEl);
    };
  });
}

function renderRules(r) {
  const rules = [
    { label: 'Require pull request reviews', value: r.reviews_required != null, detail: r.reviews_required ? `${r.reviews_required} approving review(s)` : '' },
    { label: 'Dismiss stale reviews', value: r.dismiss_stale_reviews },
    { label: 'Require code owner reviews', value: r.require_code_owners },
    { label: 'Require status checks', value: r.status_checks, detail: r.status_contexts?.length ? `Contexts: ${r.status_contexts.join(', ')}` : '' },
    { label: 'Require branches to be up to date', value: r.status_strict },
    { label: 'Enforce rules for admins', value: r.enforce_admins },
    { label: 'Require linear history', value: r.linear_history },
    { label: 'Allow force pushes', value: r.allow_force_push, inverted: true },
    { label: 'Allow deletions', value: r.allow_deletions, inverted: true },
  ];

  let html = '<div style="display:grid;grid-template-columns:1fr 1fr;gap:8px">';
  for (const rule of rules) {
    const enabled = rule.value;
    const isGood = rule.inverted ? !enabled : enabled;
    const icon = isGood ? '<span class="text-green">✓</span>' : '<span class="text-red">✕</span>';
    const detail = rule.detail ? `<span class="text-muted" style="margin-left:6px">(${rule.detail})</span>` : '';
    html += `<div style="display:flex;align-items:center;gap:8px">${icon} <span>${rule.label}</span>${detail}</div>`;
  }
  html += '</div>';
  return html;
}
