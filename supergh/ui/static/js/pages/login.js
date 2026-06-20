// Login page — supports PAT, OAuth device flow, GitHub App

import { api } from '../utils/api.js';
import { toast } from '../components/toast.js';
import { store } from '../store.js';

let activeMethod = 'pat';

export function renderLogin(container) {
  container.innerHTML = `
    <div class="login-container">
      <div class="login-card">
        <img src="/static/img/logo.png" alt="sgh" style="width:64px;height:64px;border-radius:12px;margin:0 auto 16px;display:block">
        <h1>supergh <span style="font-size:14px;font-weight:400"><span style="color:var(--green)">[›_</span> <span style="color:var(--tx3)">:</span> <span style="color:var(--tx1)">sgh</span></span></h1>
        <p class="subtitle">Sign in to your GitHub organization</p>

        <div class="auth-tabs" id="auth-tabs">
          <div class="auth-tab ${activeMethod === 'pat' ? 'active' : ''}" data-method="pat">Token</div>
          <div class="auth-tab ${activeMethod === 'oauth' ? 'active' : ''}" data-method="oauth">OAuth</div>
          <div class="auth-tab ${activeMethod === 'app' ? 'active' : ''}" data-method="app">GitHub App</div>
        </div>

        <form id="login-form">
          <div id="auth-fields"></div>
          <button type="submit" class="btn btn-primary" id="login-btn" style="width:100%;justify-content:center;padding:10px;margin-top:8px">Sign in</button>
        </form>
        <div id="login-error" class="form-error mt-2" style="display:none"></div>
        <div id="login-info" class="form-hint mt-2" style="display:none"></div>
      </div>
    </div>
  `;

  const fieldsEl = container.querySelector('#auth-fields');
  renderFields(fieldsEl);

  // Tab switching
  container.querySelectorAll('.auth-tab').forEach(tab => {
    tab.onclick = () => {
      activeMethod = tab.dataset.method;
      container.querySelectorAll('.auth-tab').forEach(t => t.classList.remove('active'));
      tab.classList.add('active');
      renderFields(fieldsEl);
      container.querySelector('#login-error').style.display = 'none';
      container.querySelector('#login-info').style.display = 'none';
    };
  });

  // Form submit
  container.querySelector('#login-form').onsubmit = (e) => {
    e.preventDefault();
    handleSubmit(container);
  };
}

function renderFields(fieldsEl) {
  switch (activeMethod) {
    case 'pat':
      fieldsEl.innerHTML = `
        <div class="form-group" style="text-align:left">
          <label class="form-label">Personal Access Token</label>
          <input type="password" class="input" id="field-token" placeholder="ghp_xxxxxxxxxxxx" autocomplete="off">
          <p class="form-hint">GitHub → Settings → Developer settings → Personal access tokens → Generate new token</p>
        </div>
      `;
      setTimeout(() => document.getElementById('field-token')?.focus(), 50);
      break;

    case 'oauth':
      fieldsEl.innerHTML = `
        <div class="form-group" style="text-align:left">
          <label class="form-label">OAuth Client ID</label>
          <input type="text" class="input" id="field-client-id" placeholder="Ov23li...">
          <p class="form-hint">Register an OAuth App in your org's settings to get a Client ID.</p>
        </div>
      `;
      setTimeout(() => document.getElementById('field-client-id')?.focus(), 50);
      break;

    case 'app':
      fieldsEl.innerHTML = `
        <div class="form-group" style="text-align:left">
          <label class="form-label">App ID</label>
          <input type="text" class="input" id="field-app-id" placeholder="123456">
        </div>
        <div class="form-group" style="text-align:left">
          <label class="form-label">Private Key (PEM content)</label>
          <textarea class="input" id="field-pem" rows="4" placeholder="-----BEGIN RSA PRIVATE KEY-----&#10;..." style="resize:vertical;font-family:monospace;font-size:11px"></textarea>
          <p class="form-hint">Paste the contents of the .pem file downloaded when you created the GitHub App.</p>
        </div>
        <div class="form-group" style="text-align:left">
          <label class="form-label">Installation Org</label>
          <input type="text" class="input" id="field-app-org" placeholder="my-org">
          <p class="form-hint">The organization where this App is installed.</p>
        </div>
      `;
      setTimeout(() => document.getElementById('field-app-id')?.focus(), 50);
      break;
  }
}

async function handleSubmit(container) {
  const btn = container.querySelector('#login-btn');
  const errorEl = container.querySelector('#login-error');
  const infoEl = container.querySelector('#login-info');
  errorEl.style.display = 'none';
  infoEl.style.display = 'none';

  btn.disabled = true;
  btn.textContent = 'Signing in...';

  try {
    switch (activeMethod) {
      case 'pat':
        await handlePAT(container, errorEl);
        break;
      case 'oauth':
        await handleOAuth(container, errorEl, infoEl);
        break;
      case 'app':
        await handleApp(container, errorEl);
        break;
    }
  } finally {
    btn.disabled = false;
    btn.textContent = 'Sign in';
  }
}

async function handlePAT(container, errorEl) {
  const token = document.getElementById('field-token')?.value.trim();
  if (!token) {
    showError(errorEl, 'Token is required.');
    document.getElementById('field-token')?.classList.add('input-error');
    return;
  }

  try {
    const res = await api.post('/api/auth/pat', { token });
    if (res.ok) {
      toast.success(`Signed in as ${res.username}`);
      store.set('authenticated', true);
      window.dispatchEvent(new CustomEvent('sgh:authenticated'));
    } else {
      showError(errorEl, res.error || 'Invalid token.');
      document.getElementById('field-token')?.classList.add('input-error');
    }
  } catch (err) {
    showError(errorEl, 'Authentication failed. Check your token and try again.');
  }
}

async function handleOAuth(container, errorEl, infoEl) {
  const clientId = document.getElementById('field-client-id')?.value.trim();
  if (!clientId) {
    showError(errorEl, 'Client ID is required.');
    document.getElementById('field-client-id')?.classList.add('input-error');
    return;
  }

  try {
    const res = await api.post('/api/auth/oauth/start', { client_id: clientId });
    if (res.device_code) {
      infoEl.innerHTML = `
        <div style="text-align:left;padding:12px;background:var(--s3);border-radius:var(--radius);margin-top:12px">
          <p style="margin-bottom:8px"><strong>Step 1:</strong> Go to <a href="${res.verification_uri}" target="_blank" style="color:var(--blue)">${res.verification_uri}</a></p>
          <p style="margin-bottom:8px"><strong>Step 2:</strong> Enter code: <code style="background:var(--s1);padding:2px 8px;border-radius:4px;font-size:16px;font-weight:bold">${res.user_code}</code></p>
          <p class="text-xs text-muted">Waiting for authorization...</p>
        </div>
      `;
      infoEl.style.display = 'block';

      // Poll for token
      const pollRes = await api.post('/api/auth/oauth/poll', { device_code: res.device_code, client_id: clientId, interval: res.interval });
      if (pollRes.ok) {
        toast.success(`Signed in as ${pollRes.username}`);
        store.set('authenticated', true);
        window.dispatchEvent(new CustomEvent('sgh:authenticated'));
      } else {
        showError(errorEl, pollRes.error || 'OAuth flow failed or timed out.');
      }
    } else {
      showError(errorEl, res.error || 'Failed to start OAuth device flow.');
    }
  } catch (err) {
    showError(errorEl, 'OAuth flow failed. Ensure your Client ID is correct.');
  }
}

async function handleApp(container, errorEl) {
  const appId = document.getElementById('field-app-id')?.value.trim();
  const pem = document.getElementById('field-pem')?.value.trim();
  const org = document.getElementById('field-app-org')?.value.trim();

  if (!appId) { showError(errorEl, 'App ID is required.'); return; }
  if (!pem) { showError(errorEl, 'Private key is required.'); return; }
  if (!org) { showError(errorEl, 'Installation org is required.'); return; }

  if (!pem.includes('-----BEGIN') || !pem.includes('-----END')) {
    showError(errorEl, 'Invalid PEM format. Paste the full private key including BEGIN/END markers.');
    return;
  }

  try {
    const res = await api.post('/api/auth/app', { app_id: appId, pem, org });
    if (res.ok) {
      toast.success(`Authenticated as GitHub App (${res.app_name || appId})`);
      store.set('authenticated', true);
      window.dispatchEvent(new CustomEvent('sgh:authenticated'));
    } else {
      showError(errorEl, res.error || 'App authentication failed.');
    }
  } catch (err) {
    showError(errorEl, 'App authentication failed. Verify App ID, PEM key, and installation org.');
  }
}

function showError(el, msg) {
  el.textContent = msg;
  el.style.display = 'block';
}
