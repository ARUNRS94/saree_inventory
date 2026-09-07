import { NavLink } from 'react-router-dom';
import { LayoutDashboard, Package, Users, Factory, ShoppingCart, ClipboardCheck, Wrench, BarChart3, Settings, X, Layers, Shield, KeyRound } from 'lucide-react';
import clsx from 'clsx';
import { useAuth } from '@/contexts/AuthContext';
import { useSettings } from '@/contexts/SettingsContext';

const links = [
  { to: '/', label: 'Dashboard', icon: LayoutDashboard },
  { to: '/inventory', label: 'Inventory', icon: Package },
  { to: '/purchase-orders', label: 'Purchase Orders', icon: ShoppingCart },
  { to: '/grn', label: 'GRN', icon: ClipboardCheck },
  { to: '/job-work', label: 'Job Work', icon: Wrench },
  { to: '/sarees', label: 'Sarees', icon: Layers },
  { to: '/suppliers', label: 'Suppliers', icon: Users },
  { to: '/vendors', label: 'Vendors', icon: Factory },
  { to: '/reports', label: 'Reports', icon: BarChart3 },
];

const adminLinks = [
  { to: '/users', label: 'User Management', icon: Shield, permission: 'users' },
  { to: '/access', label: 'Access Management', icon: KeyRound, permission: 'roles' },
  { to: '/settings', label: 'Settings', icon: Settings, permission: 'settings' },
];

export function Sidebar({ onClose }: { onClose?: () => void }) {
  const { can } = useAuth();
  const { logo_url, company_name } = useSettings();
  const allLinks = [
    ...links,
    ...adminLinks.filter((l) => can(l.permission)),
  ];
  return (
    <div className="flex flex-col h-full bg-white border-r border-gray-200">
      <div className="flex items-center justify-between px-5 py-4 border-b border-gray-100">
        <div className="flex items-center gap-2.5 min-w-0">
          {logo_url ? (
            <img src={logo_url} alt="Logo" className="h-8 w-8 object-contain rounded flex-shrink-0" />
          ) : null}
          <h1 className="text-lg font-bold text-primary-700 truncate">{company_name || 'Inventory Management'}</h1>
        </div>
        {onClose && (
          <button onClick={onClose} className="lg:hidden p-1 rounded hover:bg-gray-100">
            <X className="h-5 w-5" />
          </button>
        )}
      </div>
      <nav className="flex-1 px-3 py-4 space-y-1 overflow-y-auto">
        {allLinks.map(({ to, label, icon: Icon }) => (
          <NavLink
            key={to}
            to={to}
            end={to === '/'}
            onClick={onClose}
            className={({ isActive }) =>
              clsx('flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-medium transition-colors',
                isActive ? 'bg-primary-50 text-primary-700' : 'text-gray-600 hover:bg-gray-100 hover:text-gray-900')
            }
          >
            <Icon className="h-5 w-5" />
            {label}
          </NavLink>
        ))}
      </nav>
    </div>
  );
}
