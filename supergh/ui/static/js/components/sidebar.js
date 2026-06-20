// Sidebar component

import { store } from '../store.js';

export function renderSidebar(container) {
  const s = store.getAll();
  const page = s.currentPage;
  const perms = s.permissions;
  const auth = s.authInfo;

  container.innerHTML = `
    <div class="sidebar-brand">
      <div>
        <img src="/static/img/logo.png" alt="sgh" id="sidebar-logo" style="width:120px;height:120px;border-radius:8px;cursor:pointer">
        <div class="org">${auth.org || 'Not connected'}</div>
      </div>
      <button class="btn btn-ghost btn-sm" id="theme-toggle">${s.theme === 'light' ? '🌙' : '☀'}</button>
    </div>
    <nav class="sidebar-nav">
      <div class="sidebar-section">Navigation</div>
      <div class="sidebar-item ${page === 'repos' ? 'active' : ''}" data-page="repos">
        <span class="icon">◫</span> Repositories
      </div>
      <div class="sidebar-item ${page === 'pipelines' ? 'active' : ''} ${!perms.actions?.read ? 'disabled' : ''}" data-page="pipelines" ${!perms.actions?.read ? `title="${perms.actions?.reason || 'No permission'}"` : ''}>
        <span class="icon">▶</span> Pipelines
      </div>
      <div class="sidebar-item ${page === 'teams' ? 'active' : ''} ${!perms.teams?.read ? 'disabled' : ''}" data-page="teams" ${!perms.teams?.read ? `title="${perms.teams?.reason || 'No permission'}"` : ''}>
        <span class="icon">⊞</span> Teams
      </div>
      <div class="sidebar-item ${page === 'compliance' ? 'active' : ''}" data-page="compliance">
        <span class="icon">◈</span> Compliance
      </div>
      <div class="sidebar-section">Repo Detail</div>
      <div class="sidebar-item ${page === 'detail' ? 'active' : ''} ${!s.selectedRepo ? 'disabled' : ''}" data-page="detail">
        <span class="icon">◉</span> <span class="truncate" style="max-width:140px">${s.selectedRepo?.name || 'Select a repo'}</span>
      </div>
    </nav>
    <div class="sidebar-footer">
      <div class="status-row">
        <span class="dot ${auth.authenticated ? 'dot-green' : 'dot-red'}"></span>
        <span>${auth.authenticated ? 'Connected' : 'Disconnected'}</span>
      </div>
      ${auth.authenticated ? `
        <div class="meta">
          ${auth.auth_type === 'app' ? (auth.app_name || auth.username || '').replace(/\\\[/g, '[') : auth.username}<br>
          ${auth.org ? `${auth.org}` : ''}${auth.expires_in ? ` · ${Math.floor(auth.expires_in / 60)}m left` : ''}
        </div>
      ` : ''}
    </div>
  `;

  // Event listeners
  container.querySelector('#sidebar-logo').onclick = () => {
    store.set('currentPage', 'repos');
  };

  container.querySelector('#theme-toggle').onclick = () => {
    const next = store.get('theme') === 'light' ? 'dark' : 'light';
    store.set('theme', next);
    localStorage.setItem('sgh-theme', next);
    document.documentElement.setAttribute('data-theme', next === 'dark' ? '' : 'light');
    renderSidebar(container);
  };

  container.querySelectorAll('[data-page]').forEach(el => {
    el.onclick = () => {
      if (el.classList.contains('disabled')) return;
      const target = el.dataset.page;
      store.set('currentPage', target);
    };
  });
}
