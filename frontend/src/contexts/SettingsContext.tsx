import { createContext, useContext, useState, useEffect, useCallback, type ReactNode } from 'react';
import api from '@/services/api';

interface SettingsState {
  logo_url: string;
  company_name: string;
  reload: () => void;
}

const SettingsContext = createContext<SettingsState>({ logo_url: '', company_name: '', reload: () => {} });

export function SettingsProvider({ children }: { children: ReactNode }) {
  const [logo_url, setLogoUrl] = useState('');
  const [company_name, setCompanyName] = useState('');

  const reload = useCallback(() => {
    api.get('/settings').then((r) => {
      setLogoUrl(r.data.logo_url || '');
      setCompanyName(r.data.company_name || '');
    }).catch(() => {});
  }, []);

  useEffect(() => { reload(); }, [reload]);

  return (
    <SettingsContext.Provider value={{ logo_url, company_name, reload }}>
      {children}
    </SettingsContext.Provider>
  );
}

export function useSettings() {
  return useContext(SettingsContext);
}
