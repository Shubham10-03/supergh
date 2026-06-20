// Repo detail page — tabbed view using sub-page modules

import { api } from '../../utils/api.js';
import { store } from '../../store.js';
import { toast } from '../../components/toast.js';
import { tableLoader } from '../../components/loader.js';
import { confirmDialog } from '../../components/modal.js';
import { renderPRList } from '../pr/list.js';
import { renderIssuesList } from '../issues/list.js';
import { renderWorkflows } from '../workflows/list.js';

let activeTab = 'prs';

export async function renderRepoDetail(container) {
  const repo = store.get('selectedRepo');
  if (!repo) {
    store.set('currentPage', 'repos');
    return;
  }

  const perms = store.get('permissions');
  const tabs = [
    { id: 'prs', label: 'Pull Requests', perm: 'pulls' },
    { id: 'issues', label: 'Issues', perm: 'issues' },
    { id: 'workflows', label: 'Workflows', perm: 'actions' },
    { id: 'secrets', label: 'Secrets', perm: 'secrets' },
    { id: 'variables', label: 'Variables', perm: 'secrets' },
  ];

  container.innerHTML = `
    <div class="page">
      <div class="flex items-center gap-3 mb-4">
        <button class="btn btn-ghost btn-sm" id="back-btn">← Back</button>
        <span class="font-medium">${repo.name}</span>
        <span class="badge badge-neutral">${repo.visibility}</span>
        <span class="text-xs text-muted">${repo.language || ''}</span>
        <div class="ml-auto flex items-center gap-2">
          <button class="btn btn-danger btn-sm" id="delete-repo-btn" ${!store.hasPermission('repos', 'write') ? 'disabled' : ''}>Delete</button>
          <a href="${repo.url}" target="_blank" class="btn btn-ghost btn-sm">GitHub ↗</a>
        </div>
      </div>
      <div class="tabs" id="detail-tabs">
        ${tabs.map(t => {
          const disabled = !perms[t.perm]?.read;
          return `<div class="tab ${activeTab === t.id ? 'active' : ''} ${disabled ? 'disabled' : ''}" data-tab="${t.id}" ${disabled ? `title="${perms[t.perm]?.reason || 'No permission'}"` : ''}>${t.label}</div>`;
        }).join('')}
      </div>
      <div id="detail-content"></div>
    </div>
  `;

  container.querySelector('#back-btn').onclick = () => store.set('currentPage', 'repos');

  container.querySelector('#delete-repo-btn').onclick = async () => {
    const yes = await confirmDialog(
      `<strong>This will permanently delete ${repo.name}.</strong><br><br>This action cannot be undone. All issues, pull requests, wikis, and releases will be lost.`,
      { title: 'Delete repository', confirmLabel: 'Delete this repository', danger: true }
    );
    if (!yes) return;
    try {
      await api.delete(`/api/repos/${repo.name}`);
      toast.success(`Repository "${repo.name}" deleted.`);
      store.update({ selectedRepo: null, currentPage: 'repos' });
    } catch (e) { /* toasted */ }
  };

  container.querySelectorAll('[data-tab]').forEach(el => {
    el.onclick = () => {
      if (el.classList.contains('disabled')) {
        const tab = tabs.find(t => t.id === el.dataset.tab);
        toast.error(perms[tab?.perm]?.reason || 'You do not have permission for this.');
        return;
      }
      activeTab = el.dataset.tab;
      renderRepoDetail(container);
    };
  });

  const contentEl = container.querySelector('#detail-content');
  await renderTabContent(contentEl, repo.name);
}

async function renderTabContent(contentEl, repoName) {
  switch (activeTab) {
    case 'prs':
      await renderPRList(contentEl, repoName);
      break;
    case 'issues':
      await renderIssuesList(contentEl, repoName);
      break;
    case 'workflows':
      await renderWorkflows(contentEl, repoName);
      break;
    case 'secrets':
      await renderSecrets(contentEl, repoName);
      break;
    case 'variables':
      await renderVariables(contentEl, repoName);
      break;
  }
}

async function renderSecrets(el, repoName) {
  el.innerHTML = `<div class="card">${tableLoader(4, 2)}</div>`;
  try {
    const secrets = await api.get(`/api/repos/${repoName}/secrets`);
    const card = el.querySelector('.card') || el;
    if (!secrets.length) {
      card.innerHTML = `<div class="empty-state"><div class="title">No secrets</div><div class="desc">No secrets configured for this repository.</div></div>`;
      return;
    }
    let html = `<table class="table"><thead><tr><th>Secret Name</th><th>Last Updated</th></tr></thead><tbody>`;
    for (const s of secrets) {
      html += `<tr><td class="mono text-xs font-medium">${esc(s.name)}</td><td class="text-muted">${s.updated}</td></tr>`;
    }
    card.innerHTML = html + '</tbody></table>';
  } catch (e) {
    el.innerHTML = `<div class="card"><div class="empty-state"><div class="icon">⚠</div><div class="title">Failed to load secrets</div><div class="desc">${e.message}</div></div></div>`;
  }
}

async function renderVariables(el, repoName) {
  el.innerHTML = `<div class="card">${tableLoader(4, 3)}</div>`;
  try {
    const variables = await api.get(`/api/repos/${repoName}/variables`);
    const card = el.querySelector('.card') || el;
    if (!variables.length) {
      card.innerHTML = `<div class="empty-state"><div class="title">No variables</div><div class="desc">No variables configured for this repository.</div></div>`;
      return;
    }
    let html = `<table class="table"><thead><tr><th>Variable</th><th>Value</th><th>Updated</th></tr></thead><tbody>`;
    for (const v of variables) {
      html += `<tr><td class="mono text-xs font-medium">${esc(v.name)}</td><td class="mono text-xs text-green">${esc(v.value.substring(0, 80))}</td><td class="text-muted">${v.updated}</td></tr>`;
    }
    card.innerHTML = html + '</tbody></table>';
  } catch (e) {
    el.innerHTML = `<div class="card"><div class="empty-state"><div class="icon">⚠</div><div class="title">Failed to load variables</div><div class="desc">${e.message}</div></div></div>`;
  }
}

function esc(str) {
  const d = document.createElement('div');
  d.textContent = str || '';
  return d.innerHTML;
}
