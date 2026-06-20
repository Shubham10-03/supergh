// Teams list page

import { api } from '../../utils/api.js';
import { tableLoader } from '../../components/loader.js';

export async function renderTeams(container) {
  container.innerHTML = `<div class="page"><div class="card" id="teams-table">${tableLoader(6, 4)}</div></div>`;
  const tableEl = container.querySelector('#teams-table');

  try {
    const teams = await api.get('/api/teams');
    if (!teams.length) {
      tableEl.innerHTML = `<div class="empty-state"><div class="icon">⊞</div><div class="title">No teams</div><div class="desc">No teams found in this organization.</div></div>`;
      return;
    }

    let html = `<table class="table"><thead><tr><th>Team</th><th>Slug</th><th>Privacy</th><th>Members</th></tr></thead><tbody>`;
    for (const t of teams) {
      const privCls = t.privacy === 'secret' ? 'badge-orange' : 'badge-neutral';
      html += `<tr><td class="font-medium">${t.name}</td><td class="text-muted mono text-xs">${t.slug}</td><td><span class="badge ${privCls}">${t.privacy}</span></td><td>${t.members}</td></tr>`;
    }
    tableEl.innerHTML = html + '</tbody></table>';
  } catch (e) {
    tableEl.innerHTML = `<div class="empty-state"><div class="icon">⚠</div><div class="title">Failed to load teams</div><div class="desc">${e.message}</div></div>`;
  }
}
