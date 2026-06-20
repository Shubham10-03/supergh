// Global state store — reactive state management

const listeners = new Set();
const state = {
  authenticated: false,
  authInfo: {},
  permissions: {},
  theme: localStorage.getItem('sgh-theme') || 'dark',
  currentPage: 'repos',
  selectedRepo: null,
  loading: {},
};

export const store = {
  get(key) { return state[key]; },

  set(key, value) {
    state[key] = value;
    this.notify();
  },

  update(partial) {
    Object.assign(state, partial);
    this.notify();
  },

  getAll() { return { ...state }; },

  setLoading(key, val) {
    state.loading = { ...state.loading, [key]: val };
    this.notify();
  },

  isLoading(key) { return !!state.loading[key]; },

  hasPermission(scope, level = 'read') {
    const perm = state.permissions[scope];
    return perm && perm[level];
  },

  getPermissionReason(scope) {
    const perm = state.permissions[scope];
    return perm?.reason || '';
  },

  subscribe(fn) {
    listeners.add(fn);
    return () => listeners.delete(fn);
  },

  notify() {
    listeners.forEach(fn => fn(state));
  },
};
