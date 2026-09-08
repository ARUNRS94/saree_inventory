import { useEffect, useState } from 'react';
import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, LineChart, Line } from 'recharts';
import { Package, IndianRupee, ShoppingCart, Wrench, Layers, Factory, Users } from 'lucide-react';
import api from '@/services/api';
import type { DashboardData } from '@/types';
import { StatsCard } from '@/components/StatsCard';
import { LoadingState, ErrorState } from '@/components/LoadingState';
import { formatCurrency, formatNumber } from '@/utils/format';

export default function DashboardPage() {
  const [data, setData] = useState<DashboardData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  useEffect(() => {
    api.get('/dashboard').then((r) => setData(r.data)).catch((e) => setError(e.response?.data?.detail || 'Failed to load dashboard')).finally(() => setLoading(false));
  }, []);

  if (loading) return <LoadingState />;
  if (error || !data) return <ErrorState message={error} />;

  const { cards } = data;

  return (
    <div>
      <h1 className="text-xl sm:text-2xl font-bold mb-6">Dashboard</h1>

      <div className="grid grid-cols-2 lg:grid-cols-4 gap-3 sm:gap-4 mb-6">
        <StatsCard title="Total Stock" value={`${formatNumber(cards.total_stock_qty)} pcs`} icon={<Package className="h-8 w-8" />} />
        <StatsCard title="Stock Value" value={formatCurrency(cards.stock_value)} icon={<IndianRupee className="h-8 w-8" />} />
        <StatsCard title="Pending PO Qty" value={`${formatNumber(cards.pending_po_qty)} pcs`} icon={<ShoppingCart className="h-8 w-8" />} />
        <StatsCard title="Vendor WIP" value={`${formatNumber(cards.vendor_wip_qty)} pcs`} icon={<Wrench className="h-8 w-8" />} />
        <StatsCard title="Open PO Value" value={formatCurrency(cards.open_po_value)} icon={<ShoppingCart className="h-8 w-8" />} />
        <StatsCard title="Active Items" value={formatNumber(cards.active_items)} icon={<Layers className="h-8 w-8" />} />
        <StatsCard title="Active Vendors" value={formatNumber(cards.active_vendors)} icon={<Factory className="h-8 w-8" />} />
        <StatsCard title="Active Contacts" value={formatNumber(cards.active_contacts)} icon={<Users className="h-8 w-8" />} />
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4 mb-6">
        {data.purchase_trend.length > 0 && (
          <div className="card p-4">
            <h3 className="text-sm font-semibold mb-4">Purchase Trend</h3>
            <ResponsiveContainer width="100%" height={250}>
              <LineChart data={data.purchase_trend}>
                <CartesianGrid strokeDasharray="3 3" />
                <XAxis dataKey="month" fontSize={12} />
                <YAxis fontSize={12} />
                <Tooltip />
                <Line type="monotone" dataKey="value" stroke="#2563eb" strokeWidth={2} />
              </LineChart>
            </ResponsiveContainer>
          </div>
        )}
        {data.stock_movement.length > 0 && (
          <div className="card p-4">
            <h3 className="text-sm font-semibold mb-4">Stock Movement</h3>
            <ResponsiveContainer width="100%" height={250}>
              <BarChart data={data.stock_movement}>
                <CartesianGrid strokeDasharray="3 3" />
                <XAxis dataKey="month" fontSize={12} />
                <YAxis fontSize={12} />
                <Tooltip />
                <Bar dataKey="qty_in" fill="#22c55e" name="In" />
                <Bar dataKey="qty_out" fill="#ef4444" name="Out" />
              </BarChart>
            </ResponsiveContainer>
          </div>
        )}
      </div>

      {data.top_categories.length > 0 && (
        <div className="card p-4">
          <h3 className="text-sm font-semibold mb-4">Stock by Category</h3>
          <ResponsiveContainer width="100%" height={200}>
            <BarChart data={data.top_categories} layout="vertical">
              <CartesianGrid strokeDasharray="3 3" />
              <XAxis type="number" fontSize={12} />
              <YAxis dataKey="category" type="category" fontSize={12} width={100} />
              <Tooltip />
              <Bar dataKey="qty" fill="#3b82f6" />
            </BarChart>
          </ResponsiveContainer>
        </div>
      )}
    </div>
  );
}
