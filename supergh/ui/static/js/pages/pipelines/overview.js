// Pipelines overview page

import { api } from '../../utils/api.js';
import { tableLoader } from '../../components/loader.js';

export async function renderPipelines(container) {
  container.innerHTML = `<div class="page"><div class="card" id="pipeline-table">${tableLoader(10, 6)}</div></div>`;
  const tableEl = container.querySelector('#pipeline-table');

  try {
    const pipelines = await api.get('/api/pipelines', { limit: 30 });
    if (!pipelines.length) {
      tableEl.innerHTML = `<div class="empty-state"><div class="icon">▶</div><div class="title">No pipeline data</div><div class="desc">No recent workflow runs found across your repositories.</div></div>`;
      return;
    }

    let html = `<table class="table"><thead><tr><th>Repository</th><th>Workflow</th><th>Status</th><th>Result</th><th>Branch</th><th>Triggered by</th><th>Started</th></tr></thead><tbody>`;
    for (const p of pipelines) {
      const cls = p.conclusion === 'success' ? 'badge-green' : p.conclusion === 'failure' ? 'badge-red' : 'badge-orange';
      html += `<tr>
        <td class="font-medium text-blue">${p.repo}</td>
        <td>${p.workflow}</td>
        <td class="text-xs">${p.status}</td>
        <td><span class="badge ${cls}">${p.conclusion}</span></td>
        <td class="mono text-xs text-muted">${p.branch}</td>
        <td class="text-muted">${p.actor}</td>
        <td class="text-xs text-muted">${p.started}</td>
      </tr>`;
    }
    tableEl.innerHTML = html + '</tbody></table>';
  } catch (e) {
    tableEl.innerHTML = `<div class="empty-state"><div class="icon">⚠</div><div class="title">Failed to load pipelines</div><div class="desc">${e.message}</div></div>`;
  }
}
