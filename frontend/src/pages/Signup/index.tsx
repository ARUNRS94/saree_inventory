import { useCallback, useState } from 'react';
import { Link, Navigate } from 'react-router-dom';
import { useAuth } from '@/contexts/AuthContext';
import { useSettings } from '@/contexts/SettingsContext';
import { GoogleSignInButton } from '@/components/GoogleSignInButton';
import { Building2 } from 'lucide-react';

function errorMessage(err: unknown, fallback: string) {
  const detail = (err as { response?: { data?: { detail?: unknown } } })?.response?.data?.detail;
  if (typeof detail === 'string') return detail;
  if (Array.isArray(detail)) return detail.map((d: { msg?: string }) => d.msg).filter(Boolean).join(', ') || fallback;
  return err instanceof Error ? err.message : fallback;
}

export default function SignupPage() {
  const { signup, loginWithGoogle, providers } = useAuth();
  const { logo_url, company_name } = useSettings();
  const [form, setForm] = useState({ full_name: '', username: '', email: '', password: '' });
  const [confirm, setConfirm] = useState('');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (form.password !== confirm) {
      setError('Passwords do not match.');
      return;
    }
    setError('');
    setLoading(true);
    try {
      await signup(form);
    } catch (err: unknown) {
      setError(errorMessage(err, 'Sign up failed'));
    } finally {
      setLoading(false);
    }
  };

  const handleGoogle = useCallback(async (credential: string) => {
    setError('');
    setLoading(true);
    try {
      await loginWithGoogle(credential);
    } catch (err: unknown) {
      setError(errorMessage(err, 'Google sign-up failed'));
    } finally {
      setLoading(false);
    }
  }, [loginWithGoogle]);

  if (!providers.signup_enabled && !providers.google_enabled) {
    return <Navigate to="/login" replace />;
  }

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
          <h1 className="text-2xl font-bold text-center text-primary-700 mb-2">{company_name || 'Inventory Management'}</h1>
          <p className="text-sm text-gray-500 text-center mb-6">Create your account</p>
          {error && <div className="bg-red-50 text-red-700 text-sm px-4 py-2 rounded-lg mb-4">{error}</div>}

          {providers.signup_enabled && (
            <form onSubmit={handleSubmit} className="space-y-4">
              <div>
                <label className="label">Full Name</label>
                <input className="input" value={form.full_name}
                  onChange={(e) => setForm({ ...form, full_name: e.target.value })} required autoFocus />
              </div>
              <div>
                <label className="label">Username</label>
                <input className="input" value={form.username}
                  onChange={(e) => setForm({ ...form, username: e.target.value })} required minLength={3} />
              </div>
              <div>
                <label className="label">Email</label>
                <input className="input" type="email" value={form.email}
                  onChange={(e) => setForm({ ...form, email: e.target.value })} required />
              </div>
              <div>
                <label className="label">Password</label>
                <input className="input" type="password" value={form.password}
                  onChange={(e) => setForm({ ...form, password: e.target.value })} required minLength={8} />
              </div>
              <div>
                <label className="label">Confirm Password</label>
                <input className="input" type="password" value={confirm}
                  onChange={(e) => setConfirm(e.target.value)} required minLength={8} />
              </div>
              <button type="submit" className="btn-primary w-full" disabled={loading}>
                {loading ? 'Creating account...' : 'Sign Up'}
              </button>
            </form>
          )}

          {providers.google_enabled && providers.google_client_id && (
            <>
              <div className="flex items-center gap-3 my-5">
                <div className="h-px flex-1 bg-gray-200" />
                <span className="text-xs text-gray-400 uppercase">or</span>
                <div className="h-px flex-1 bg-gray-200" />
              </div>
              <GoogleSignInButton
                clientId={providers.google_client_id}
                text="signup_with"
                onCredential={handleGoogle}
                onError={setError}
              />
            </>
          )}

          <p className="text-sm text-gray-500 text-center mt-5">
            Already have an account?{' '}
            <Link to="/login" className="text-primary-600 font-medium hover:underline">Sign in</Link>
          </p>
        </div>
      </div>
    </div>
  );
}
