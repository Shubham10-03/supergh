// Permissions utility

import { store } from '../store.js';
import { toast } from '../components/toast.js';

export function requirePermission(scope, level = 'read') {
  if (!store.hasPermission(scope, level)) {
    const reason = store.getPermissionReason(scope);
    toast.error(reason || `You do not have ${level} permission for ${scope}.`);
    return false;
  }
  return true;
}

export function permissionBadge(scope) {
  const perms = store.get('permissions');
  const p = perms[scope];
  if (!p) return '<span class="badge badge-neutral">Unknown</span>';
  if (p.write) return '<span class="badge badge-green">Read & Write</span>';
  if (p.read) return '<span class="badge badge-blue">Read Only</span>';
  return '<span class="badge badge-red">No Access</span>';
}
