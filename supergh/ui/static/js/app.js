// sgh Web UI — Main app shell

import { store } from './store.js';
import { api } from './utils/api.js';
import { renderSidebar } from './components/sidebar.js';
import { renderHeader } from './components/header.js';
import { renderLogin } from './pages/login.js';
import { renderReposList } from './pages/repos/list.js';
import { renderRepoDetail } from './pages/repos/detail.js';
import { renderPipelines } from './pages/pipelines/overview.js';
import { renderTeams } from './pages/teams/list.js';
import { renderCompliance } from './pages/compliance/check.js';
import { renderSearch } from './pages/search/results.js';

const app = document.getElementById('app');
let sidebarEl, headerEl, contentEl;
let currentRenderedPage = null;
let rendering = false;

// Apply saved theme
const savedTheme = store.get('theme');
if (savedTheme === 'light') document.documentElement.setAttribute('data-theme', 'light');

async function init() {
  try {
    const authInfo = await api.get('/api/auth');
    store.update({ authenticated: authInfo.authenticated, authInfo });
  } catch (e) {
    store.update({ authenticated: false, authInfo: {} });
  }

  if (!store.get('authenticated')) {
    renderLogin(app);
    return;
  }

  try {
    const perms = await api.get('/api/permissions');
    store.set('permissions', perms);
  } catch (e) {
    store.set('permissions', {});
  }

  renderShell();
  await renderCurrentPage();
}

function renderShell() {
  app.innerHTML = `
    <div class="shell">
      <aside class="sidebar" id="sidebar"></aside>
      <div class="main">
        <header class="header" id="header"></header>
        <main class="content" id="content"></main>
      </div>
    </div>
  `;
  sidebarEl = document.getElementById('sidebar');
  headerEl = document.getElementById('header');
  contentEl = document.getElementById('content');

  renderSidebar(sidebarEl);
  renderHeader(headerEl);
}

async function renderCurrentPage() {
  if (!contentEl || rendering) return;
  const page = store.get('currentPage');

  // Avoid re-rendering same page unless it's detail (repo might change)
  if (page === currentRenderedPage && page !== 'detail') return;

  rendering = true;
  currentRenderedPage = page;

  try {
    switch (page) {
      case 'repos':
        await renderReposList(contentEl);
        break;
      case 'detail':
        await renderRepoDetail(contentEl);
        break;
      case 'pipelines':
        await renderPipelines(contentEl);
        break;
      case 'teams':
        await renderTeams(contentEl);
        break;
      case 'compliance':
        await renderCompliance(contentEl);
        break;
      case 'search':
        await renderSearch(contentEl);
        break;
      default:
        await renderReposList(contentEl);
    }
  } finally {
    rendering = false;
  }
}

// React to state changes — only re-render what's needed
let prevPage = store.get('currentPage');
let prevRepo = store.get('selectedRepo');

store.subscribe((state) => {
  const pageChanged = state.currentPage !== prevPage;
  const repoChanged = state.selectedRepo !== prevRepo;

  if (sidebarEl) renderSidebar(sidebarEl);
  if (headerEl) renderHeader(headerEl);

  if (pageChanged || (state.currentPage === 'detail' && repoChanged)) {
    prevPage = state.currentPage;
    prevRepo = state.selectedRepo;
    currentRenderedPage = null; // force re-render
    renderCurrentPage();
  }
});

// Global events
window.addEventListener('sgh:authenticated', () => {
  currentRenderedPage = null;
  init();
});

window.addEventListener('sgh:logout', () => {
  store.update({ authenticated: false, authInfo: {} });
  currentRenderedPage = null;
  renderLogin(app);
});

window.addEventListener('sgh:search', (e) => {
  store.set('currentPage', 'search');
  currentRenderedPage = null;
  setTimeout(() => renderSearch(contentEl, e.detail), 50);
});

// Boot
init();
