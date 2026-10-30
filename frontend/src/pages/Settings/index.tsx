import { useEffect, useState } from 'react';
import api from '@/services/api';
import { useSettings } from '@/contexts/SettingsContext';
import { useAuth } from '@/contexts/AuthContext';
import { PageHeader } from '@/components/PageHeader';
import { Trash2, Building2, Image as ImageIcon, MapPin } from 'lucide-react';

export default function SettingsPage() {
  const { can } = useAuth();
  const { logo_url, company_name, company_tagline, company_address, company_phone, reload } = useSettings();
  const [name, setName] = useState(company_name);
  const [tagline, setTagline] = useState(company_tagline);
  const [logo, setLogo] = useState(logo_url);
  const [address, setAddress] = useState(company_address);
  const [phone, setPhone] = useState(company_phone);
  const [savingLogo, setSavingLogo] = useState(false);
  const [savingContact, setSavingContact] = useState(false);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');

  // Settings arrive after the first render, so the inputs adopt them when they land.
  useEffect(() => {
    setName(company_name); setLogo(logo_url); setTagline(company_tagline);
    setAddress(company_address); setPhone(company_phone);
  }, [company_name, logo_url, company_tagline, company_address, company_phone]);

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
      await api.put('/settings', { company_name: name, company_tagline: tagline });
      setSuccess('Company name and tag line saved.');
      reload();
    } catch (err: unknown) {
      setError((err as { response?: { data?: { detail?: string } } })?.response?.data?.detail || 'Failed');
    } finally { setSaving(false); }
  };

  const saveContact = async () => {
    setSavingContact(true); setError(''); setSuccess('');
    try {
      await api.put('/settings', { company_address: address, company_phone: phone });
      setSuccess('Address and phone saved.');
      reload();
    } catch (err: unknown) {
      setError((err as { response?: { data?: { detail?: string } } })?.response?.data?.detail || 'Failed');
    } finally { setSavingContact(false); }
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
            <div>
              <label className="label">Tag Line</label>
              <input className="input" maxLength={120} value={tagline} onChange={(e) => setTagline(e.target.value)}
                placeholder="Weaving tradition since 1980" />
            </div>
            <button className="btn-primary text-sm" onClick={saveName} disabled={saving}>
              {saving ? 'Saving...' : 'Save'}
            </button>
            <p className="text-xs text-gray-400">Displayed in sidebar, login page, and reports. The tag line prints under the company name on exports.</p>
          </div>
        </div>

        {/* Address and phone */}
        <div className="card p-6 lg:col-span-2">
          <h3 className="text-sm font-semibold mb-4 flex items-center gap-2"><MapPin className="h-4 w-4" /> Address &amp; Phone</h3>
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <div>
              <label className="label">Address</label>
              <textarea className="input" rows={3} value={address} onChange={(e) => setAddress(e.target.value)}
                placeholder={'12 Market Street\nSalem, Tamil Nadu 636001'} />
            </div>
            <div>
              <label className="label">Phone Number</label>
              <input className="input" maxLength={50} value={phone} onChange={(e) => setPhone(e.target.value)}
                placeholder="+91 98765 43210" />
            </div>
          </div>
          <button className="btn-primary text-sm mt-3" onClick={saveContact} disabled={savingContact}>
            {savingContact ? 'Saving...' : 'Save'}
          </button>
          <p className="text-xs text-gray-400 mt-2">Printed in the header of every exported PDF and CSV.</p>
        </div>
      </div>
    </div>
  );
}
