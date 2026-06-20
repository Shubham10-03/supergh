// Header component

import { store } from '../store.js';

const pageTitles = {
  repos: 'Repositories',
  detail: '',
  pipelines: 'Pipelines',
  teams: 'Teams',
  compliance: 'Compliance',
  search: 'Search Results',
};

export function renderHeader(container) {
  const s = store.getAll();
  const title = s.currentPage === 'detail' ? (s.selectedRepo?.name || '') : (pageTitles[s.currentPage] || '');

  container.innerHTML = `
    <h2 class="font-medium text-sm">${title}</h2>
    <div class="flex items-center gap-3">
      <input type="text" class="input" style="width:220px;padding:6px 12px;font-size:12px" placeholder="Search org..." id="header-search">
    </div>
  `;

  const searchInput = container.querySelector('#header-search');
  searchInput.onkeydown = (e) => {
    if (e.key === 'Enter' && searchInput.value.trim()) {
      window.dispatchEvent(new CustomEvent('sgh:search', { detail: searchInput.value.trim() }));
    }
  };
}
