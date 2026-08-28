import { useState } from 'react';
import api from '@/services/api';
import { useSettings } from '@/contexts/SettingsContext';
import { useAuth } from '@/contexts/AuthContext';
import { PageHeader } from '@/components/PageHeader';
import { Upload, Trash2, Building2 } from 'lucide-react';

export default function SettingsPage() {
  const { user } = useAuth();
  const { logo_url, company_name, reload } = useSettings();
  const [name, setName] = useState(company_name);
  const [uploading, setUploading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');

  if (user?.role !== 'admin') {
    return <div className="text-center py-12 text-gray-500">Admin access required.</div>;
  }

  const handleUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    setUploading(true); setError(''); setSuccess('');
    try {
      const form = new FormData();
      form.append('file', file);
      await api.post('/settings/logo', form, { headers: { 'Content-Type': 'multipart/form-data' } });
      setSuccess('Logo uploaded.');
      reload();
    } catch (err: unknown) {
      setError((err as { response?: { data?: { detail?: string } } })?.response?.data?.detail || 'Upload failed');
    } finally { setUploading(false); e.target.value = ''; }
  };

  const removeLogo = async () => {
    setError(''); setSuccess('');
    try {
      await api.delete('/settings/logo');
      setSuccess('Logo removed.');
      reload();
    } catch (err: unknown) {
      setError((err as { response?: { data?: { detail?: string } } })?.response?.data?.detail || 'Failed');
    }
  };

  const saveName = async () => {
    setSaving(true); setError(''); setSuccess('');
    try {
      await api.put('/settings', { company_name: name });
      setSuccess('Company name saved.');
      reload();
    } catch (err: unknown) {
      setError((err as { response?: { data?: { detail?: string } } })?.response?.data?.detail || 'Failed');
    } finally { setSaving(false); }
  };

  return (
    <div>
      <PageHeader title="Settings" subtitle="Company branding and configuration" />
      {success && <div className="bg-green-50 text-green-700 text-sm px-4 py-2 rounded-lg mb-4">{success}</div>}
      {error && <div className="bg-red-50 text-red-700 text-sm px-4 py-2 rounded-lg mb-4">{error}</div>}

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Logo */}
        <div className="card p-6">
          <h3 className="text-sm font-semibold mb-4 flex items-center gap-2"><Upload className="h-4 w-4" /> Company Logo</h3>
          <div className="flex items-center gap-6">
            <div className="w-24 h-24 rounded-xl border-2 border-dashed border-gray-300 flex items-center justify-center bg-gray-50 overflow-hidden flex-shrink-0">
              {logo_url ? (
                <img src={logo_url} alt="Logo" className="w-full h-full object-contain" />
              ) : (
                <Building2 className="h-10 w-10 text-gray-300" />
              )}
            </div>
            <div className="space-y-2">
              <label className="btn-primary text-sm cursor-pointer inline-flex items-center gap-1">
                <Upload className="h-4 w-4" />
                {uploading ? 'Uploading...' : 'Upload Logo'}
                <input type="file" accept=".png,.jpg,.jpeg,.svg,.webp" onChange={handleUpload} className="hidden" disabled={uploading} />
              </label>
              {logo_url && (
                <button className="btn-danger text-sm flex items-center gap-1" onClick={removeLogo}>
                  <Trash2 className="h-4 w-4" /> Remove
                </button>
              )}
              <p className="text-xs text-gray-400">PNG, JPG, SVG or WebP. Max 2MB.</p>
            </div>
          </div>
        </div>

        {/* Company Name */}
        <div className="card p-6">
          <h3 className="text-sm font-semibold mb-4 flex items-center gap-2"><Building2 className="h-4 w-4" /> Company Name</h3>
          <div className="space-y-3">
            <input className="input" value={name} onChange={(e) => setName(e.target.value)} placeholder="Enter company name" />
            <button className="btn-primary text-sm" onClick={saveName} disabled={saving}>
              {saving ? 'Saving...' : 'Save'}
            </button>
            <p className="text-xs text-gray-400">Displayed in sidebar, login page, and reports.</p>
          </div>
        </div>
      </div>
    </div>
  );
}
