// Workflows & Runs page

import { api } from '../../utils/api.js';
import { store } from '../../store.js';
import { toast } from '../../components/toast.js';
import { tableLoader } from '../../components/loader.js';
import { openModal, closeModal, confirmDialog } from '../../components/modal.js';

let workflows = [];
let runs = [];
let activeTab = 'workflows';

export async function renderWorkflows(container, repoName) {
  container.innerHTML = `
    <div class="page">
      <div class="tabs" id="wf-tabs">
        <div class="tab ${activeTab === 'workflows' ? 'active' : ''}" data-tab="workflows">Workflows</div>
        <div class="tab ${activeTab === 'runs' ? 'active' : ''}" data-tab="runs">Runs</div>
      </div>
      <div class="card" id="wf-content">${tableLoader(6, 4)}</div>
    </div>
  `;

  const contentEl = container.querySelector('#wf-content');
  container.querySelectorAll('[data-tab]').forEach(el => {
    el.onclick = () => {
      activeTab = el.dataset.tab;
      renderWorkflows(container, repoName);
    };
  });

  if (activeTab === 'workflows') await loadWorkflows(contentEl, repoName);
  else await loadRuns(contentEl, repoName);
}

async function loadWorkflows(el, repoName) {
  el.innerHTML = tableLoader(5, 4);
  try {
    workflows = await api.get(`/api/repos/${repoName}/workflows`);
    if (!workflows.length) {
      el.innerHTML = `<div class="empty-state"><div class="icon">▶</div><div class="title">No workflows</div><div class="desc">This repository has no GitHub Actions workflows configured.</div></div>`;
      return;
    }

    let html = `<table class="table"><thead><tr><th>Workflow</th><th>State</th><th>File</th><th></th></tr></thead><tbody>`;
    for (const w of workflows) {
      const stateClass = w.state === 'active' ? 'badge-green' : 'badge-red';
      html += `<tr>
        <td class="font-medium">${esc(w.name)}</td>
        <td><span class="badge ${stateClass}">${w.state}</span></td>
        <td class="mono text-xs text-muted">${w.path}</td>
        <td><button class="btn btn-sm btn-primary trigger-btn" data-id="${w.id}" data-name="${esc(w.name)}" ${!store.hasPermission('actions', 'write') ? 'disabled' : ''}>▶ Trigger</button></td>
      </tr>`;
    }
    el.innerHTML = html + '</tbody></table>';

    el.querySelectorAll('.trigger-btn').forEach(btn => {
      btn.onclick = () => showTriggerModal(repoName, btn.dataset.id, btn.dataset.name);
    });
  } catch (e) {
    el.innerHTML = `<div class="empty-state"><div class="icon">⚠</div><div class="title">Failed to load workflows</div><div class="desc">${e.message}</div></div>`;
  }
}

function showTriggerModal(repoName, workflowId, workflowName) {
  const repo = store.get('selectedRepo');
  const defaultBranch = repo?.default_branch || 'main';

  openModal(`Trigger: ${workflowName}`, `
    <div class="form-group">
      <label class="form-label">Branch or tag</label>
      <input type="text" class="input" id="trigger-ref" value="${defaultBranch}">
    </div>
    <div class="form-group">
      <label class="form-label">Inputs (JSON, optional)</label>
      <textarea class="input" id="trigger-inputs" rows="3" placeholder='{"key": "value"}' style="resize:vertical;font-family:monospace;font-size:12px"></textarea>
      <p class="form-hint">Only needed if the workflow defines workflow_dispatch inputs.</p>
    </div>
  `, [
    { label: 'Cancel', cls: 'btn-ghost', onClick: () => closeModal() },
    { label: 'Trigger workflow', cls: 'btn-primary', onClick: () => handleTrigger(repoName, workflowId) },
  ]);
}

async function handleTrigger(repoName, workflowId) {
  const ref = document.getElementById('trigger-ref')?.value.trim() || 'main';
  const inputsRaw = document.getElementById('trigger-inputs')?.value.trim();

  const payload = { ref };
  if (inputsRaw) {
    try {
      payload.inputs = JSON.parse(inputsRaw);
    } catch (e) {
      toast.warning('Invalid JSON in inputs field.');
      return;
    }
  }

  try {
    await api.post(`/api/repos/${repoName}/workflows/${workflowId}/dispatch`, payload);
    toast.success('Workflow triggered successfully.');
    closeModal();
  } catch (e) { /* toasted */ }
}

async function loadRuns(el, repoName) {
  el.innerHTML = tableLoader(8, 6);
  try {
    runs = await api.get(`/api/repos/${repoName}/runs`, { limit: 30 });
    if (!runs.length) {
      el.innerHTML = `<div class="empty-state"><div class="icon">▶</div><div class="title">No runs</div><div class="desc">No workflow runs found for this repository.</div></div>`;
      return;
    }

    let html = `<table class="table"><thead><tr><th>Workflow</th><th>Status</th><th>Result</th><th>Branch</th><th>Triggered by</th><th>Started</th><th></th></tr></thead><tbody>`;
    for (const r of runs) {
      const cls = r.conclusion === 'success' ? 'badge-green' : r.conclusion === 'failure' ? 'badge-red' : r.conclusion === 'cancelled' ? 'badge-neutral' : 'badge-orange';
      html += `<tr>
        <td>${esc(r.name)}</td>
        <td class="text-xs">${r.status}</td>
        <td><span class="badge ${cls}">${r.conclusion || 'pending'}</span></td>
        <td class="mono text-xs text-muted">${r.branch}</td>
        <td class="text-muted">${r.actor}</td>
        <td class="text-xs text-muted">${r.started}</td>
        <td class="flex gap-2">
          <button class="btn btn-ghost btn-sm rerun-btn" data-id="${r.id}">Rerun</button>
          ${r.status === 'in_progress' || r.status === 'queued' ? `<button class="btn btn-danger btn-sm cancel-btn" data-id="${r.id}">Cancel</button>` : ''}
          <a href="${r.url}" target="_blank" class="btn btn-ghost btn-sm">↗</a>
        </td>
      </tr>`;
    }
    el.innerHTML = html + '</tbody></table>';

    el.querySelectorAll('.rerun-btn').forEach(btn => {
      btn.onclick = async () => {
        try {
          await api.post(`/api/repos/${repoName}/runs/${btn.dataset.id}/rerun`);
          toast.success('Run restarted.');
          await loadRuns(el, repoName);
        } catch (e) { /* toasted */ }
      };
    });

    el.querySelectorAll('.cancel-btn').forEach(btn => {
      btn.onclick = async () => {
        const yes = await confirmDialog('Cancel this workflow run?', { title: 'Cancel Run', confirmLabel: 'Cancel run', danger: true });
        if (!yes) return;
        try {
          await api.post(`/api/repos/${repoName}/runs/${btn.dataset.id}/cancel`);
          toast.success('Run cancelled.');
          await loadRuns(el, repoName);
        } catch (e) { /* toasted */ }
      };
    });
  } catch (e) {
    el.innerHTML = `<div class="empty-state"><div class="icon">⚠</div><div class="title">Failed to load runs</div><div class="desc">${e.message}</div></div>`;
  }
}

function esc(str) {
  const d = document.createElement('div');
  d.textContent = str || '';
  return d.innerHTML;
}
