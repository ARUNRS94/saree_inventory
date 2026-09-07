import { useCallback, useEffect, useState } from 'react';
import api from '@/services/api';
import type { Permission, Role } from '@/types';
import { PageHeader } from '@/components/PageHeader';
import { DataTable } from '@/components/DataTable';
import { StatusBadge } from '@/components/StatusBadge';
import { LoadingState, EmptyState } from '@/components/LoadingState';
import { useConfirmDialog } from '@/components/ConfirmDialog';
import { useAuth } from '@/contexts/AuthContext';

const EMPTY_FORM = { role_name: '', description: '', permissions: [] as string[] };

function detail(err: unknown, fallback: string) {
  return (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail || fallback;
}

export default function AccessManagementPage() {
  const { can } = useAuth();
  const [roles, setRoles] = useState<Role[]>([]);
  const [permissions, setPermissions] = useState<Permission[]>([]);
  const [loading, setLoading] = useState(true);
  const [showForm, setShowForm] = useState(false);
  const [editing, setEditing] = useState<Role | null>(null);
  const [form, setForm] = useState(EMPTY_FORM);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');
  const { confirm, dialog } = useConfirmDialog();

  const load = useCallback(() => {
    setLoading(true);
    Promise.all([
      api.get('/access/roles').then((r) => setRoles(r.data)),
      api.get('/access/permissions').then((r) => setPermissions(r.data)),
    ]).catch((e) => setError(detail(e, 'Failed to load')))
      .finally(() => setLoading(false));
  }, []);

  useEffect(() => { load(); }, [load]);

  const openNew = () => {
    setEditing(null);
    setForm(EMPTY_FORM);
    setShowForm(true);
    setError('');
  };

  const openEdit = (role: Role) => {
    setEditing(role);
    setForm({ role_name: role.role_name, description: role.description || '', permissions: [...role.permissions] });
    setShowForm(true);
    setError('');
  };

  const togglePermission = (code: string) => {
    setForm((f) => ({
      ...f,
      permissions: f.permissions.includes(code)
        ? f.permissions.filter((p) => p !== code)
        : [...f.permissions, code],
    }));
  };

  const save = async (e: React.FormEvent) => {
    e.preventDefault();
    setSaving(true); setError(''); setSuccess('');
    try {
      if (editing) {
        const payload: Record<string, unknown> = { description: form.description, permissions: form.permissions };
        if (!editing.is_system) payload.role_name = form.role_name;
        if (editing.role_name === 'admin') delete payload.permissions;
        await api.put(`/access/roles/${editing.role_id}`, payload);
        setSuccess('Role updated.');
      } else {
        await api.post('/access/roles', form);
        setSuccess('Role created.');
      }
      setShowForm(false); load();
    } catch (err: unknown) {
      setError(detail(err, 'Save failed'));
    } finally { setSaving(false); }
  };

  const toggleActive = async (role: Role) => {
    try {
      await api.put(`/access/roles/${role.role_id}`, { is_active: !role.is_active });
      setSuccess(`Role ${role.is_active ? 'deactivated' : 'activated'}.`); load();
    } catch (err: unknown) { setError(detail(err, 'Failed')); }
  };

  const remove = async (role: Role) => {
    if (!(await confirm('Delete Role', `Delete role "${role.role_name}"?`, true))) return;
    try {
      await api.delete(`/access/roles/${role.role_id}`);
      setSuccess('Role deleted.'); load();
    } catch (err: unknown) { setError(detail(err, 'Failed')); }
  };

  if (!can('roles')) {
    return <div className="text-center py-12 text-gray-500">You do not have access to role management.</div>;
  }

  return (
    <div>
      {dialog}
      <PageHeader title="Access Management" subtitle="Define roles and the permissions granted to each" actions={
        <button className="btn-primary text-sm" onClick={openNew}>+ Add Role</button>
      } />
      {success && <div className="bg-green-50 text-green-700 text-sm px-4 py-2 rounded-lg mb-4">{success}</div>}
      {error && <div className="bg-red-50 text-red-700 text-sm px-4 py-2 rounded-lg mb-4">{error}</div>}

      {showForm && (
        <div className="card p-4 sm:p-6 mb-6">
          <h3 className="font-semibold mb-4">{editing ? `Edit Role: ${editing.role_name}` : 'New Role'}</h3>
          <form onSubmit={save} className="space-y-4">
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
              <div>
                <label className="label">Role Name *</label>
                <input className="input" value={form.role_name}
                  onChange={(e) => setForm({ ...form, role_name: e.target.value })}
                  required minLength={2} disabled={!!editing?.is_system} />
              </div>
              <div>
                <label className="label">Description</label>
                <input className="input" value={form.description}
                  onChange={(e) => setForm({ ...form, description: e.target.value })} />
              </div>
            </div>
            <div>
              <label className="label">Permissions</label>
              {editing?.role_name === 'admin' ? (
                <p className="text-sm text-gray-500">The admin role always keeps every permission.</p>
              ) : (
                <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-2">
                  {permissions.map((p) => (
                    <label key={p.code} className="flex items-start gap-2 border border-gray-200 rounded-lg p-2 cursor-pointer hover:bg-gray-50">
                      <input type="checkbox" className="mt-1" checked={form.permissions.includes(p.code)}
                        onChange={() => togglePermission(p.code)} />
                      <span>
                        <span className="block text-sm font-medium">{p.name}</span>
                        <span className="block text-xs text-gray-500">{p.description}</span>
                      </span>
                    </label>
                  ))}
                </div>
              )}
            </div>
            <div className="flex gap-2">
              <button type="submit" className="btn-primary text-sm" disabled={saving}>{saving ? 'Saving...' : 'Save'}</button>
              <button type="button" className="btn-secondary text-sm" onClick={() => setShowForm(false)}>Cancel</button>
            </div>
          </form>
        </div>
      )}

      <div className="card">
        {loading ? <LoadingState /> : roles.length === 0 ? <EmptyState /> : (
          <DataTable keyField="role_id" data={roles} columns={[
            { header: 'Role', accessor: (r) => (
              <span className="font-medium">{r.role_name}{r.is_system && <span className="ml-2 text-xs text-gray-400">built-in</span>}</span>
            )},
            { header: 'Description', accessor: (r) => r.description || '—' },
            { header: 'Permissions', accessor: (r) => (
              <div className="flex flex-wrap gap-1 max-w-md">
                {r.permissions.map((p) => (
                  <span key={p} className="text-xs bg-gray-50 text-gray-600 px-1.5 py-0.5 rounded">{p}</span>
                ))}
              </div>
            )},
            { header: 'Status', accessor: (r) => <StatusBadge status={r.is_active ? 'ACTIVE' : 'INACTIVE'} /> },
            { header: 'Actions', accessor: (r) => (
              <div className="flex gap-2">
                <button className="text-primary-600 text-xs hover:underline"
                  onClick={(e) => { e.stopPropagation(); openEdit(r); }}>Edit</button>
                {!r.is_system && (
                  <>
                    <button className={`text-xs hover:underline ${r.is_active ? 'text-amber-600' : 'text-green-600'}`}
                      onClick={(e) => { e.stopPropagation(); toggleActive(r); }}>
                      {r.is_active ? 'Deactivate' : 'Activate'}
                    </button>
                    <button className="text-red-600 text-xs hover:underline"
                      onClick={(e) => { e.stopPropagation(); remove(r); }}>Delete</button>
                  </>
                )}
              </div>
            )},
          ]} />
        )}
      </div>
    </div>
  );
}
