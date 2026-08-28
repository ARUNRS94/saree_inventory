import { useState } from 'react';
import { useAuth } from '@/contexts/AuthContext';
import { useSettings } from '@/contexts/SettingsContext';
import { Building2 } from 'lucide-react';

export default function LoginPage() {
  const { login } = useAuth();
  const { logo_url, company_name } = useSettings();
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');
    setLoading(true);
    try {
      await login(username, password);
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Login failed';
      setError((err as { response?: { data?: { detail?: string } } })?.response?.data?.detail || msg);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen flex items-center justify-center bg-gradient-to-br from-primary-50 to-primary-100 p-4">
      <div className="w-full max-w-sm">
        <div className="card p-8">
          <div className="flex justify-center mb-3">
            {logo_url ? (
              <img src={logo_url} alt="Logo" className="h-16 w-16 object-contain rounded-xl" />
            ) : (
              <div className="h-16 w-16 rounded-xl bg-primary-100 flex items-center justify-center">
                <Building2 className="h-8 w-8 text-primary-600" />
              </div>
            )}
          </div>
          <h1 className="text-2xl font-bold text-center text-primary-700 mb-2">{company_name || 'TextiLedger'}</h1>
          <p className="text-sm text-gray-500 text-center mb-6">Sign in to your account</p>
          {error && <div className="bg-red-50 text-red-700 text-sm px-4 py-2 rounded-lg mb-4">{error}</div>}
          <form onSubmit={handleSubmit} className="space-y-4">
            <div>
              <label className="label">Username</label>
              <input className="input" value={username} onChange={(e) => setUsername(e.target.value)} required autoFocus />
            </div>
            <div>
              <label className="label">Password</label>
              <input className="input" type="password" value={password} onChange={(e) => setPassword(e.target.value)} required />
            </div>
            <button type="submit" className="btn-primary w-full" disabled={loading}>
              {loading ? 'Signing in...' : 'Sign In'}
            </button>
          </form>
          <p className="text-xs text-gray-400 text-center mt-4">Default: admin / admin123</p>
        </div>
      </div>
    </div>
  );
}
