import { useEffect, useState, useCallback } from 'react';
import api from '@/services/api';
import type { User, RoleInfo } from '@/types';
import { PageHeader } from '@/components/PageHeader';
import { DataTable } from '@/components/DataTable';
import { StatusBadge } from '@/components/StatusBadge';
import { LoadingState, EmptyState } from '@/components/LoadingState';
import { useConfirmDialog } from '@/components/ConfirmDialog';
import { useAuth } from '@/contexts/AuthContext';

export default function UsersPage() {
  const { user: currentUser } = useAuth();
  const [users, setUsers] = useState<User[]>([]);
  const [roles, setRoles] = useState<RoleInfo[]>([]);
  const [loading, setLoading] = useState(true);
  const [showForm, setShowForm] = useState(false);
  const [editing, setEditing] = useState<User | null>(null);
  const [showPasswordForm, setShowPasswordForm] = useState<User | null>(null);
  const [form, setForm] = useState({ username: '', full_name: '', password: '', role: 'viewer' });
  const [newPassword, setNewPassword] = useState('');
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');
  const { confirm, dialog } = useConfirmDialog();

  const load = useCallback(() => {
    setLoading(true);
    Promise.all([
      api.get('/auth/users').then((r) => setUsers(r.data.items)),
      api.get('/auth/roles').then((r) => setRoles(r.data)),
    ]).catch((e) => setError(e.response?.data?.detail || 'Failed to load'))
      .finally(() => setLoading(false));
  }, []);

  useEffect(() => { load(); }, [load]);

  const openNew = () => {
    setEditing(null);
    setForm({ username: '', full_name: '', password: '', role: 'viewer' });
    setShowForm(true);
    setError('');
  };

  const openEdit = (u: User) => {
    setEditing(u);
    setForm({ username: u.username, full_name: u.full_name, password: '', role: u.role });
    setShowForm(true);
    setError('');
  };

  const save = async (e: React.FormEvent) => {
    e.preventDefault();
    setSaving(true); setError(''); setSuccess('');
    try {
      if (editing) {
        await api.put(`/auth/users/${editing.user_id}`, { full_name: form.full_name, role: form.role });
        setSuccess('User updated.');
      } else {
        await api.post('/auth/users', form);
        setSuccess('User created.');
      }
      setShowForm(false); load();
    } catch (err: unknown) {
      setError((err as { response?: { data?: { detail?: string } } })?.response?.data?.detail || 'Save failed');
    } finally { setSaving(false); }
  };

  const toggleActive = async (u: User) => {
    const action = u.is_active ? 'deactivate' : 'activate';
    if (!(await confirm(`${action.charAt(0).toUpperCase() + action.slice(1)} User`, `${action} ${u.username}?`, u.is_active))) return;
    try {
      await api.put(`/auth/users/${u.user_id}`, { is_active: !u.is_active });
      setSuccess(`User ${action}d.`); load();
    } catch (err: unknown) { setError((err as { response?: { data?: { detail?: string } } })?.response?.data?.detail || 'Failed'); }
  };

  const resetPassword = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!showPasswordForm) return;
    setSaving(true); setError(''); setSuccess('');
    try {
      await api.post(`/auth/users/${showPasswordForm.user_id}/reset-password`, { new_password: newPassword });
      setSuccess(`Password reset for ${showPasswordForm.username}.`);
      setShowPasswordForm(null); setNewPassword('');
    } catch (err: unknown) {
      setError((err as { response?: { data?: { detail?: string } } })?.response?.data?.detail || 'Failed');
    } finally { setSaving(false); }
  };

  if (currentUser?.role !== 'admin') {
    return <div className="text-center py-12 text-gray-500">Admin access required.</div>;
  }

  const roleColors: Record<string, string> = {
    admin: 'bg-purple-100 text-purple-800',
    manager: 'bg-blue-100 text-blue-800',
    operator: 'bg-green-100 text-green-800',
    viewer: 'bg-gray-100 text-gray-800',
  };

  return (
    <div>
      {dialog}
      <PageHeader title="User Management" subtitle="Create users, assign roles and control access" actions={
        <button className="btn-primary text-sm" onClick={openNew}>+ Add User</button>
      } />
      {success && <div className="bg-green-50 text-green-700 text-sm px-4 py-2 rounded-lg mb-4">{success}</div>}
      {error && <div className="bg-red-50 text-red-700 text-sm px-4 py-2 rounded-lg mb-4">{error}</div>}

      {/* Role reference */}
      {roles.length > 0 && (
        <div className="card p-4 mb-6">
          <h3 className="text-sm font-semibold mb-3">Role Permissions</h3>
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3">
            {roles.map((r) => (
              <div key={r.role} className="border border-gray-200 rounded-lg p-3">
                <span className={`inline-flex items-center px-2 py-0.5 rounded-full text-xs font-semibold mb-2 ${roleColors[r.role] || 'bg-gray-100 text-gray-800'}`}>
                  {r.role}
                </span>
                <div className="flex flex-wrap gap-1 mt-1">
                  {r.permissions.map((p) => (
                    <span key={p} className="text-xs bg-gray-50 text-gray-600 px-1.5 py-0.5 rounded">{p}</span>
                  ))}
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Create/Edit form */}
      {showForm && (
        <div className="card p-4 sm:p-6 mb-6">
          <h3 className="font-semibold mb-4">{editing ? 'Edit User' : 'New User'}</h3>
          <form onSubmit={save} className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <div>
              <label className="label">Username *</label>
              <input className="input" value={form.username} onChange={(e) => setForm({ ...form, username: e.target.value })}
                required disabled={!!editing} />
            </div>
            <div>
              <label className="label">Full Name *</label>
              <input className="input" value={form.full_name} onChange={(e) => setForm({ ...form, full_name: e.target.value })} required />
            </div>
            {!editing && (
              <div>
                <label className="label">Password *</label>
                <input className="input" type="password" value={form.password}
                  onChange={(e) => setForm({ ...form, password: e.target.value })} required minLength={6} />
              </div>
            )}
            <div>
              <label className="label">Role *</label>
              <select className="input" value={form.role} onChange={(e) => setForm({ ...form, role: e.target.value })}>
                {roles.map((r) => <option key={r.role} value={r.role}>{r.role}</option>)}
              </select>
            </div>
            <div className="sm:col-span-2 flex gap-2">
              <button type="submit" className="btn-primary text-sm" disabled={saving}>{saving ? 'Saving...' : 'Save'}</button>
              <button type="button" className="btn-secondary text-sm" onClick={() => setShowForm(false)}>Cancel</button>
            </div>
          </form>
        </div>
      )}

      {/* Password reset form */}
      {showPasswordForm && (
        <div className="card p-4 sm:p-6 mb-6">
          <h3 className="font-semibold mb-4">Reset Password for {showPasswordForm.username}</h3>
          <form onSubmit={resetPassword} className="flex gap-3 items-end">
            <div className="flex-1">
              <label className="label">New Password *</label>
              <input className="input" type="password" value={newPassword}
                onChange={(e) => setNewPassword(e.target.value)} required minLength={6} />
            </div>
            <button type="submit" className="btn-primary text-sm" disabled={saving}>{saving ? 'Resetting...' : 'Reset'}</button>
            <button type="button" className="btn-secondary text-sm" onClick={() => setShowPasswordForm(null)}>Cancel</button>
          </form>
        </div>
      )}

      {/* Users table */}
      <div className="card">
        {loading ? <LoadingState /> : users.length === 0 ? <EmptyState /> : (
          <DataTable keyField="user_id" data={users} columns={[
            { header: 'Username', accessor: 'username' },
            { header: 'Full Name', accessor: 'full_name' },
            { header: 'Role', accessor: (u) => (
              <span className={`inline-flex items-center px-2 py-0.5 rounded-full text-xs font-semibold ${roleColors[u.role] || 'bg-gray-100'}`}>
                {u.role}
              </span>
            )},
            { header: 'Status', accessor: (u) => <StatusBadge status={u.is_active ? 'ACTIVE' : 'INACTIVE'} /> },
            { header: 'Actions', accessor: (u) => (
              <div className="flex gap-2">
                <button className="text-primary-600 text-xs hover:underline" onClick={(e) => { e.stopPropagation(); openEdit(u); }}>Edit</button>
                <button className="text-primary-600 text-xs hover:underline" onClick={(e) => { e.stopPropagation(); setShowPasswordForm(u); setNewPassword(''); }}>Password</button>
                {u.user_id !== currentUser?.user_id && (
                  <button className={`text-xs hover:underline ${u.is_active ? 'text-red-600' : 'text-green-600'}`}
                    onClick={(e) => { e.stopPropagation(); toggleActive(u); }}>
                    {u.is_active ? 'Deactivate' : 'Activate'}
                  </button>
                )}
              </div>
            )},
          ]} />
        )}
      </div>
    </div>
  );
}
