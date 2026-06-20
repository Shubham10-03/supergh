// API utility — centralized fetch with error handling

import { toast } from '../components/toast.js';

const BASE = '';

class ApiError extends Error {
  constructor(status, message, detail) {
    super(message);
    this.status = status;
    this.detail = detail;
  }
}

async function request(method, path, { body, params } = {}) {
  let url = `${BASE}${path}`;
  if (params) {
    const qs = new URLSearchParams(params).toString();
    if (qs) url += `?${qs}`;
  }

  const opts = { method, headers: {} };
  if (body) {
    opts.headers['Content-Type'] = 'application/json';
    opts.body = JSON.stringify(body);
  }

  let res;
  try {
    res = await fetch(url, opts);
  } catch (e) {
    toast.error('Network error — could not reach the server.');
    throw new ApiError(0, 'Network error', e.message);
  }

  if (res.status === 401) {
    toast.error('Authentication expired. Please log in again.');
    window.dispatchEvent(new CustomEvent('sgh:logout'));
    throw new ApiError(401, 'Unauthorized');
  }

  if (res.status === 403) {
    const data = await res.json().catch(() => ({}));
    const msg = data.detail || data.message || 'You do not have permission to perform this action.';
    toast.error(msg);
    throw new ApiError(403, msg);
  }

  if (res.status === 404) {
    throw new ApiError(404, 'Not found');
  }

  if (res.status === 422) {
    const data = await res.json().catch(() => ({}));
    const msg = data.detail || data.message || 'Validation error';
    toast.warning(msg);
    throw new ApiError(422, msg, data);
  }

  if (!res.ok) {
    const data = await res.json().catch(() => ({}));
    const msg = data.detail || data.message || `Request failed (${res.status})`;
    toast.error(msg);
    throw new ApiError(res.status, msg);
  }

  if (res.status === 204) return null;
  return res.json();
}

export const api = {
  get: (path, params) => request('GET', path, { params }),
  post: (path, body) => request('POST', path, { body }),
  patch: (path, body) => request('PATCH', path, { body }),
  put: (path, body) => request('PUT', path, { body }),
  delete: (path) => request('DELETE', path),
};
