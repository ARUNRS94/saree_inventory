import { useEffect, useMemo, useState } from 'react';
import api from '@/services/api';
import type { StockSummary, StockValuation, StockLedgerEntry, PaginatedResponse } from '@/types';
import { PageHeader } from '@/components/PageHeader';
import { FilterBar } from '@/components/FilterBar';
import { DataTable } from '@/components/DataTable';
import { StatsCard } from '@/components/StatsCard';
import { LoadingState, EmptyState } from '@/components/LoadingState';
import { formatCurrency, formatDate, formatNumber, sumBy } from '@/utils/format';
import { ITEM_TYPE_OPTIONS, itemTypeLabel } from '@/utils/itemTypes';
import { Download, Package, IndianRupee, ArrowLeftRight } from 'lucide-react';

type Tab = 'stock' | 'valuation' | 'movement';

const TXN_TYPES = ['PURCHASE', 'SUB_VENDOR_ISSUE', 'WIP_STOCK_IN', 'SUB_VENDOR_GRN', 'WIP_STOCK_OUT', 'JOBWORK_ISSUE', 'JOBWORK_RECEIPT', 'CUSTOMER_ISSUE', 'STOCK_ADJUSTMENT'];

const TABS: { value: Tab; label: string }[] = [
  { value: 'stock', label: 'Stock Report' },
  { value: 'valuation', label: 'Valuation' },
  { value: 'movement', label: 'Stock Movement' },
];

export default function ReportsPage() {
  const [tab, setTab] = useState<Tab>('stock');
  const [stock, setStock] = useState<StockSummary[]>([]);
  const [valuation, setValuation] = useState<StockValuation[]>([]);
  const [movement, setMovement] = useState<StockLedgerEntry[]>([]);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState('');
  const [itemType, setItemType] = useState('');
  const [vendor, setVendor] = useState('');
  const [vendorOptions, setVendorOptions] = useState<string[]>([]);
  const [voucherNumber, setVoucherNumber] = useState('');
  const [vendorVoucherNumber, setVendorVoucherNumber] = useState('');
  const [voucherOptions, setVoucherOptions] = useState<{ voucher_numbers: string[]; vendor_voucher_numbers: string[] }>({ voucher_numbers: [], vendor_voucher_numbers: [] });
  const [hideZero, setHideZero] = useState(false);
  const [txnType, setTxnType] = useState('');
  const [dateFrom, setDateFrom] = useState('');
  const [dateTo, setDateTo] = useState('');

  const params = useMemo(() => (tab === 'movement'
    ? { search: search || undefined, transaction_type: txnType || undefined, date_from: dateFrom || undefined, date_to: dateTo || undefined }
    : {
      search: search || undefined, item_type: itemType || undefined, vendor: vendor || undefined,
      hide_zero: hideZero || undefined, voucher_number: voucherNumber || undefined,
      vendor_voucher_number: vendorVoucherNumber || undefined,
    }
  ), [tab, search, itemType, vendor, hideZero, voucherNumber, vendorVoucherNumber, txnType, dateFrom, dateTo]);

  useEffect(() => {
    api.get('/contacts', { params: { page_size: 300 } })
      .then((r) => setVendorOptions(r.data.items.map((c: { contact_name: string }) => c.contact_name).sort()));
    api.get('/inventory/vouchers').then((r) => setVoucherOptions(r.data));
  }, []);

  useEffect(() => {
    setLoading(true);
    if (tab === 'stock') {
      api.get('/inventory/stock', { params }).then((r) => setStock(r.data)).finally(() => setLoading(false));
    } else if (tab === 'valuation') {
      api.get('/inventory/valuation', { params }).then((r) => setValuation(r.data)).finally(() => setLoading(false));
    } else {
      api.get('/inventory/ledger', { params: { ...params, page: 1, page_size: 500 } })
        .then((r) => setMovement((r.data as PaginatedResponse<StockLedgerEntry>).items))
        .finally(() => setLoading(false));
    }
  }, [tab, params]);

  const download = (format: 'csv' | 'pdf') => {
    api.get(`/reports/${tab}/${format}`, { params, responseType: 'blob' }).then((r) => {
      const a = document.createElement('a');
      a.href = URL.createObjectURL(r.data);
      a.download = `${tab}_report.${format}`;
      a.click();
      URL.revokeObjectURL(a.href);
    });
  };

  const clearFilters = () => {
    setSearch(''); setItemType(''); setVendor(''); setHideZero(false);
    setVoucherNumber(''); setVendorVoucherNumber('');
    setTxnType(''); setDateFrom(''); setDateTo('');
  };

  const totalStock = sumBy(stock, (s) => s.current_stock);
  const totalValue = sumBy(valuation, (r) => r.value);
  const netMovement = sumBy(movement, (r) => r.qty_in) - sumBy(movement, (r) => r.qty_out);

  // The cards summarise whichever report is on screen, so they match the applied filters.
  const cards = tab === 'stock'
    ? [
      { title: 'Items', value: formatNumber(stock.length), icon: <Package className="h-6 w-6" /> },
      { title: 'Total quantity', value: formatNumber(totalStock), icon: <ArrowLeftRight className="h-6 w-6" /> },
    ]
    : tab === 'valuation'
      ? [
        { title: 'Items', value: formatNumber(valuation.length), icon: <Package className="h-6 w-6" /> },
        { title: 'Inventory value', value: formatCurrency(totalValue), icon: <IndianRupee className="h-6 w-6" /> },
      ]
      : [
        { title: 'Movements', value: formatNumber(movement.length), icon: <ArrowLeftRight className="h-6 w-6" /> },
        { title: 'Net quantity', value: formatNumber(netMovement), icon: <Package className="h-6 w-6" /> },
      ];

  return (
    <div>
      <PageHeader title="Reports" actions={
        <div className="flex gap-2">
          <button className="btn-secondary text-sm flex items-center gap-1" onClick={() => download('csv')}><Download className="h-4 w-4" /> CSV</button>
          <button className="btn-secondary text-sm flex items-center gap-1" onClick={() => download('pdf')}><Download className="h-4 w-4" /> PDF</button>
        </div>
      } />

      <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 mb-4">
        {cards.map((c) => <StatsCard key={c.title} title={c.title} value={c.value} icon={c.icon} />)}
      </div>

      <div className="flex gap-2 mb-4">
        {TABS.map((t) => (
          <button key={t.value} className={tab === t.value ? 'btn-primary text-sm' : 'btn-secondary text-sm'} onClick={() => setTab(t.value)}>{t.label}</button>
        ))}
      </div>

      <div className="card">
        <div className="p-4 border-b border-gray-100">
          {tab === 'movement' ? (
            <FilterBar
              search={{ value: search, onChange: setSearch, placeholder: 'Search reference or item...' }}
              filters={[{
                label: 'Transaction Type', value: txnType, onChange: setTxnType,
                options: [{ value: '', label: 'All Types' }, ...TXN_TYPES.map((t) => ({ value: t, label: t.replace(/_/g, ' ') }))],
              }]}
              dateRange={{ from: dateFrom, to: dateTo, onFromChange: setDateFrom, onToChange: setDateTo }}
              onClear={clearFilters}
            />
          ) : (
            <>
              <FilterBar
                search={{ value: search, onChange: setSearch, placeholder: 'Search item name or code...' }}
                filters={[
                  { label: 'Type', value: itemType, onChange: setItemType,
                    options: [{ value: '', label: 'All Types' }, ...ITEM_TYPE_OPTIONS] },
                  { label: 'Vendor', value: vendor, onChange: setVendor,
                    options: [{ value: '', label: 'All Vendors' }, ...vendorOptions.map((v) => ({ value: v, label: v }))] },
                  { label: 'GSS Voucher No', value: voucherNumber, onChange: setVoucherNumber,
                    options: [{ value: '', label: 'All Vouchers' }, ...voucherOptions.voucher_numbers.map((v) => ({ value: v, label: v }))] },
                  { label: 'Vendor Voucher No', value: vendorVoucherNumber, onChange: setVendorVoucherNumber,
                    options: [{ value: '', label: 'All Vendor Vouchers' }, ...voucherOptions.vendor_voucher_numbers.map((v) => ({ value: v, label: v }))] },
                ]}
                onClear={clearFilters}
              />
              <label className="flex items-center gap-2 text-sm text-gray-600 mt-3">
                <input type="checkbox" checked={hideZero} onChange={(e) => setHideZero(e.target.checked)} />
                Hide items with zero stock
              </label>
            </>
          )}
        </div>

        {loading ? <LoadingState /> : tab === 'stock' ? (
          stock.length === 0 ? <EmptyState /> : (
            <>
              <DataTable keyField="item_id" data={stock} columns={[
                { header: 'Name', accessor: 'item_name' },
                { header: 'Type', accessor: (s) => itemTypeLabel(s.item_type) },
                { header: 'GSS Voucher No', accessor: (s) => s.voucher_numbers.join(', ') || '-', hideOnMobile: true },
                { header: 'Vendor Voucher No', accessor: (s) => s.vendor_voucher_numbers.join(', ') || '-', hideOnMobile: true },
                { header: 'Vendors', accessor: (s) => s.vendors.join(', ') || '-' },
                { header: 'Stock', accessor: 'current_stock', className: 'font-semibold' },
              ]} />
              <div className="px-4 py-3 border-t border-gray-100 text-right font-semibold">
                Total: {formatNumber(totalStock)} pcs across {stock.length} item(s)
              </div>
            </>
          )
        ) : tab === 'valuation' ? (
          valuation.length === 0 ? <EmptyState /> : (
            <>
              <DataTable keyField="item_id" data={valuation} columns={[
                { header: 'Name', accessor: 'item_name' },
                { header: 'Type', accessor: (r) => itemTypeLabel(r.item_type), hideOnMobile: true },
                { header: 'GSS Voucher No', accessor: (r) => r.voucher_numbers.join(', ') || '-', hideOnMobile: true },
                { header: 'Vendor Voucher No', accessor: (r) => r.vendor_voucher_numbers.join(', ') || '-', hideOnMobile: true },
                { header: 'Vendors', accessor: (r) => r.vendors.join(', ') || '-', hideOnMobile: true },
                { header: 'Stock', accessor: 'current_stock' },
                { header: 'Rate', accessor: (r) => formatCurrency(r.latest_rate), hideOnMobile: true },
                { header: 'Value', accessor: (r) => formatCurrency(r.value), className: 'font-semibold' },
              ]} />
              <div className="px-4 py-3 border-t border-gray-100 text-right font-semibold">
                Total: {formatCurrency(totalValue)}
              </div>
            </>
          )
        ) : (
          movement.length === 0 ? <EmptyState /> : (
            <>
              <DataTable keyField="ledger_id" data={movement} columns={[
                { header: 'Date', accessor: (r) => formatDate(r.transaction_date) },
                { header: 'Type', accessor: (r) => r.transaction_type.replace(/_/g, ' ') },
                { header: 'Reference', accessor: 'reference_no', hideOnMobile: true },
                { header: 'Item', accessor: 'item_name' },
                { header: 'In', accessor: 'qty_in' },
                { header: 'Out', accessor: 'qty_out' },
                { header: 'Rate', accessor: (r) => formatCurrency(r.rate), hideOnMobile: true },
              ]} />
              <div className="px-4 py-3 border-t border-gray-100 text-right font-semibold">
                {movement.length} movement(s) | net {formatNumber(netMovement)} pcs
              </div>
            </>
          )
        )}
      </div>
    </div>
  );
}
