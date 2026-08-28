import { NavLink } from 'react-router-dom';
import { LayoutDashboard, Package, ShoppingCart, Wrench, MoreHorizontal } from 'lucide-react';
import clsx from 'clsx';
import { useState } from 'react';

const mainLinks = [
  { to: '/', label: 'Dashboard', icon: LayoutDashboard },
  { to: '/inventory', label: 'Inventory', icon: Package },
  { to: '/purchase-orders', label: 'Purchase', icon: ShoppingCart },
  { to: '/job-work', label: 'Job Work', icon: Wrench },
];

const moreLinks = [
  { to: '/grn', label: 'GRN' },
  { to: '/sarees', label: 'Sarees' },
  { to: '/suppliers', label: 'Suppliers' },
  { to: '/vendors', label: 'Vendors' },
  { to: '/reports', label: 'Reports' },
];

export function MobileNav() {
  const [showMore, setShowMore] = useState(false);

  return (
    <>
      {showMore && (
        <div className="fixed inset-0 z-40 lg:hidden">
          <div className="fixed inset-0 bg-black/30" onClick={() => setShowMore(false)} />
          <div className="fixed bottom-16 left-4 right-4 bg-white rounded-xl shadow-xl border border-gray-200 p-3 z-50 grid grid-cols-3 gap-2">
            {moreLinks.map(({ to, label }) => (
              <NavLink key={to} to={to} onClick={() => setShowMore(false)}
                className={({ isActive }) => clsx('text-center px-3 py-2.5 rounded-lg text-sm font-medium', isActive ? 'bg-primary-50 text-primary-700' : 'text-gray-600 hover:bg-gray-100')}>
                {label}
              </NavLink>
            ))}
          </div>
        </div>
      )}
      <nav className="fixed bottom-0 left-0 right-0 bg-white border-t border-gray-200 z-30 lg:hidden">
        <div className="flex justify-around items-center h-16">
          {mainLinks.map(({ to, label, icon: Icon }) => (
            <NavLink key={to} to={to} end={to === '/'}
              className={({ isActive }) => clsx('flex flex-col items-center gap-0.5 px-2 py-1 text-xs font-medium', isActive ? 'text-primary-600' : 'text-gray-500')}>
              <Icon className="h-5 w-5" />
              {label}
            </NavLink>
          ))}
          <button onClick={() => setShowMore(!showMore)} className="flex flex-col items-center gap-0.5 px-2 py-1 text-xs font-medium text-gray-500">
            <MoreHorizontal className="h-5 w-5" />
            More
          </button>
        </div>
      </nav>
    </>
  );
}
