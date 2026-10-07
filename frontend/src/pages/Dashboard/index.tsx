import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, LineChart, Line, PieChart, Pie, Cell, Legend } from 'recharts';
import { Package, IndianRupee, ShoppingCart, Wrench, Layers, TriangleAlert, PackageX } from 'lucide-react';
import api from '@/services/api';
import type { DashboardData } from '@/types';
import { StatsCard } from '@/components/StatsCard';
import { LoadingState, ErrorState } from '@/components/LoadingState';
import { formatCurrency, formatDate, formatNumber } from '@/utils/format';

const SPLIT_COLOURS = ['#3b82f6', '#f59e0b', '#8b5cf6', '#14b8a6'];

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
  const lossQty = cards.damaged_qty + cards.short_qty;

  return (
    <div>
      <h1 className="text-xl sm:text-2xl font-bold mb-6">Dashboard</h1>

      <div className="grid grid-cols-2 lg:grid-cols-4 gap-3 sm:gap-4 mb-6">
        <StatsCard title="Total Stock" value={`${formatNumber(cards.total_stock_qty)} pcs`} icon={<Package className="h-8 w-8" />} />
        <StatsCard title="Stock Value" value={formatCurrency(cards.stock_value)} icon={<IndianRupee className="h-8 w-8" />} />
        <StatsCard title="Pending Voucher Qty" value={`${formatNumber(cards.pending_po_qty)} pcs`} icon={<ShoppingCart className="h-8 w-8" />} />
        <StatsCard title="Vendor WIP" value={`${formatNumber(cards.vendor_wip_qty)} pcs`} icon={<Wrench className="h-8 w-8" />} />
        <StatsCard title="Open Voucher Value" value={formatCurrency(cards.open_po_value)} icon={<IndianRupee className="h-8 w-8" />} />
        <StatsCard
          title="Damaged / NC"
          value={`${formatNumber(cards.damaged_qty)} pcs`}
          icon={<TriangleAlert className="h-8 w-8" />}
          className={cards.damaged_qty > 0 ? 'border-l-4 border-amber-400' : undefined}
        />
        <StatsCard
          title="Short Of"
          value={`${formatNumber(cards.short_qty)} pcs`}
          icon={<PackageX className="h-8 w-8" />}
          className={cards.short_qty > 0 ? 'border-l-4 border-red-400' : undefined}
        />
        <StatsCard title="Active Items" value={formatNumber(cards.active_items)} icon={<Layers className="h-8 w-8" />} />
      </div>

      {lossQty > 0 && (
        <div className="card p-4 mb-6 flex flex-wrap items-center justify-between gap-3">
          <p className="text-sm text-gray-600">
            <span className="font-semibold text-gray-900">{formatNumber(lossQty)} pcs</span> never reached stock
            — {formatNumber(cards.damaged_qty)} damaged/NC and {formatNumber(cards.short_qty)} short of.
          </p>
          <Link to="/grn" className="text-primary-600 text-sm hover:underline">Review GRNs</Link>
        </div>
      )}

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4 mb-6">
        {data.vendor_pending.length > 0 && (
          <div className="card p-4">
            <div className="flex items-center justify-between mb-4">
              <h3 className="text-sm font-semibold">Pending with Sub Vendors</h3>
              <Link to="/vouchers" className="text-primary-600 text-xs hover:underline">All vouchers</Link>
            </div>
            <table className="w-full text-sm">
              <thead className="text-gray-500">
                <tr>
                  <th className="text-left font-medium pb-2">Sub Vendor</th>
                  <th className="text-right font-medium pb-2">Open</th>
                  <th className="text-right font-medium pb-2">Pending</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-100">
                {data.vendor_pending.map((v) => (
                  <tr key={v.vendor_name}>
                    <td className="py-2">{v.vendor_name}</td>
                    <td className="py-2 text-right text-gray-500">{v.open_vouchers}</td>
                    <td className="py-2 text-right font-semibold">{formatNumber(v.pending_qty)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}

        {data.recent_grns.length > 0 && (
          <div className="card p-4">
            <div className="flex items-center justify-between mb-4">
              <h3 className="text-sm font-semibold">Recent Inwards</h3>
              <Link to="/grn" className="text-primary-600 text-xs hover:underline">All GRNs</Link>
            </div>
            <table className="w-full text-sm">
              <thead className="text-gray-500">
                <tr>
                  <th className="text-left font-medium pb-2">GRN</th>
                  <th className="text-left font-medium pb-2">Vendor</th>
                  <th className="text-right font-medium pb-2">Received</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-100">
                {data.recent_grns.map((g) => (
                  <tr key={g.grn_number}>
                    <td className="py-2">
                      <span className="block">{g.grn_number}</span>
                      <span className="text-xs text-gray-500">
                        {g.grn_type === 'RM' ? 'Raw Material' : 'Sub Vendor'} &middot; {formatDate(g.grn_date)}
                      </span>
                    </td>
                    <td className="py-2">{g.vendor_name || '-'}</td>
                    <td className="py-2 text-right">
                      <span className="font-semibold">{formatNumber(g.received_qty)}</span>
                      {(g.damaged_qty > 0 || g.short_qty > 0) && (
                        <span className="block text-xs text-amber-600">
                          {g.damaged_qty > 0 && `${g.damaged_qty} NC`}
                          {g.damaged_qty > 0 && g.short_qty > 0 && ' · '}
                          {g.short_qty > 0 && `${g.short_qty} short`}
                        </span>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4 mb-6">
        {data.purchase_trend.length > 0 && (
          <div className="card p-4">
            <h3 className="text-sm font-semibold mb-4">Voucher Trend</h3>
            <ResponsiveContainer width="100%" height={250}>
              <LineChart data={data.purchase_trend}>
                <CartesianGrid strokeDasharray="3 3" />
                <XAxis dataKey="month" fontSize={12} />
                <YAxis fontSize={12} />
                <Tooltip formatter={(v: number) => formatCurrency(v)} />
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

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        {data.top_categories.length > 0 && (
          <div className="card p-4">
            <h3 className="text-sm font-semibold mb-4">Stock by Type</h3>
            <ResponsiveContainer width="100%" height={200}>
              <BarChart data={data.top_categories} layout="vertical">
                <CartesianGrid strokeDasharray="3 3" />
                <XAxis type="number" fontSize={12} />
                <YAxis dataKey="category" type="category" fontSize={12} width={110} />
                <Tooltip />
                <Bar dataKey="qty" fill="#3b82f6" />
              </BarChart>
            </ResponsiveContainer>
          </div>
        )}
        {data.sub_process_split.length > 0 && (
          <div className="card p-4">
            <h3 className="text-sm font-semibold mb-4">Work in Progress by Process</h3>
            <ResponsiveContainer width="100%" height={200}>
              <PieChart>
                <Pie data={data.sub_process_split} dataKey="qty" nameKey="category" innerRadius={45} outerRadius={75}>
                  {data.sub_process_split.map((entry, index) => (
                    <Cell key={entry.category} fill={SPLIT_COLOURS[index % SPLIT_COLOURS.length]} />
                  ))}
                </Pie>
                <Tooltip formatter={(v: number) => `${formatNumber(v)} pcs`} />
                <Legend />
              </PieChart>
            </ResponsiveContainer>
          </div>
        )}
      </div>
    </div>
  );
}
