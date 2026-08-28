import clsx from 'clsx';
import type { ReactNode } from 'react';

interface Props {
  title: string;
  value: string | number;
  icon?: ReactNode;
  className?: string;
}

export function StatsCard({ title, value, icon, className }: Props) {
  return (
    <div className={clsx('card p-4 sm:p-6', className)}>
      <div className="flex items-center justify-between">
        <div>
          <p className="text-xs sm:text-sm font-medium text-gray-500">{title}</p>
          <p className="text-lg sm:text-2xl font-bold mt-1">{value}</p>
        </div>
        {icon && <div className="text-primary-500 hidden sm:block">{icon}</div>}
      </div>
    </div>
  );
}
