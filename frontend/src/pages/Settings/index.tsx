import { useState } from 'react';
import api from '@/services/api';
import { useSettings } from '@/contexts/SettingsContext';
import { useAuth } from '@/contexts/AuthContext';
import { PageHeader } from '@/components/PageHeader';
import { Trash2, Building2, Image as ImageIcon } from 'lucide-react';

export default function SettingsPage() {
  const { can } = useAuth();
  const { logo_url, company_name, reload } = useSettings();
  const [name, setName] = useState(company_name);
  const [logo, setLogo] = useState(logo_url);
  const [savingLogo, setSavingLogo] = useState(false);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');

  if (!can('settings')) {
    return <div className="text-center py-12 text-gray-500">You do not have access to settings.</div>;
  }

  const saveLogo = async (value: string) => {
    setSavingLogo(true); setError(''); setSuccess('');
    try {
      await api.put('/settings', { logo_url: value });
      setSuccess(value ? 'Logo updated.' : 'Logo removed.');
      reload();
    } catch (err: unknown) {
      setError((err as { response?: { data?: { detail?: string } } })?.response?.data?.detail || 'Failed');
    } finally { setSavingLogo(false); }
  };

  const removeLogo = async () => {
    setLogo('');
    await saveLogo('');
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
          <h3 className="text-sm font-semibold mb-4 flex items-center gap-2"><ImageIcon className="h-4 w-4" /> Company Logo</h3>
          <div className="flex items-start gap-6">
            <div className="w-24 h-24 rounded-xl border-2 border-dashed border-gray-300 flex items-center justify-center bg-gray-50 overflow-hidden flex-shrink-0">
              {logo_url ? (
                <img src={logo_url} alt="Logo" className="w-full h-full object-contain" />
              ) : (
                <Building2 className="h-10 w-10 text-gray-300" />
              )}
            </div>
            <div className="flex-1 space-y-2">
              <input className="input" value={logo} onChange={(e) => setLogo(e.target.value)}
                placeholder="https://cdn.example.com/logo.png" />
              <div className="flex gap-2">
                <button className="btn-primary text-sm" onClick={() => saveLogo(logo)} disabled={savingLogo}>
                  {savingLogo ? 'Saving...' : 'Save Logo'}
                </button>
                {logo_url && (
                  <button className="btn-danger text-sm flex items-center gap-1" onClick={removeLogo} disabled={savingLogo}>
                    <Trash2 className="h-4 w-4" /> Remove
                  </button>
                )}
              </div>
              <p className="text-xs text-gray-400">Paste a public image URL. Container storage is ephemeral, so files are not hosted here.</p>
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
