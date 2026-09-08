import { useEffect, useState, useCallback } from 'react';
import api from '@/services/api';
import type { StockSummary, StockLedgerEntry, PaginatedResponse } from '@/types';
import { PageHeader } from '@/components/PageHeader';
import { FilterBar } from '@/components/FilterBar';
import { DataTable, Pagination } from '@/components/DataTable';
import { LoadingState, EmptyState } from '@/components/LoadingState';
import { formatDate } from '@/utils/format';
import { ITEM_TYPE_OPTIONS, itemTypeLabel } from '@/utils/itemTypes';

const TXN_TYPES = ['PURCHASE', 'SUB_VENDOR_ISSUE', 'WIP_STOCK_IN', 'SUB_VENDOR_GRN', 'WIP_STOCK_OUT', 'JOBWORK_ISSUE', 'JOBWORK_RECEIPT', 'CUSTOMER_ISSUE', 'STOCK_ADJUSTMENT'];

export default function InventoryPage() {
  const [tab, setTab] = useState<'stock' | 'ledger'>('stock');
  const [stock, setStock] = useState<StockSummary[]>([]);
  const [ledger, setLedger] = useState<PaginatedResponse<StockLedgerEntry>>({ items: [], total: 0, page: 1, page_size: 50 });
  const [page, setPage] = useState(1);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState('');
  const [stockType, setStockType] = useState('');
  const [txnType, setTxnType] = useState('');
  const [dateFrom, setDateFrom] = useState('');
  const [dateTo, setDateTo] = useState('');

  const load = useCallback(() => {
    setLoading(true);
    if (tab === 'stock') {
      api.get('/inventory/stock').then((r) => setStock(r.data)).finally(() => setLoading(false));
    } else {
      api.get('/inventory/ledger', { params: {
        page, page_size: 50, search: search || undefined,
        transaction_type: txnType || undefined,
        date_from: dateFrom || undefined, date_to: dateTo || undefined,
      } }).then((r) => setLedger(r.data)).finally(() => setLoading(false));
    }
  }, [tab, page, search, txnType, dateFrom, dateTo]);

  useEffect(() => { load(); }, [load]);

  const filtered = tab === 'stock' ? stock.filter((s) => {
    const matchText = !search || `${s.item_code} ${s.item_name}`.toLowerCase().includes(search.toLowerCase());
    const matchType = !stockType || s.item_type === stockType;
    return matchText && matchType;
  }) : [];

  return (
    <div>
      <PageHeader title="Inventory" />

      <div className="flex gap-2 mb-4">
        <button className={tab === 'stock' ? 'btn-primary text-sm' : 'btn-secondary text-sm'} onClick={() => { setTab('stock'); setPage(1); }}>Stock Summary</button>
        <button className={tab === 'ledger' ? 'btn-primary text-sm' : 'btn-secondary text-sm'} onClick={() => { setTab('ledger'); setPage(1); }}>Stock Ledger</button>
      </div>

      <div className="card">
        <div className="p-4 border-b border-gray-100">
          {tab === 'stock' ? (
            <FilterBar
              search={{ value: search, onChange: setSearch, placeholder: 'Filter by code or name...' }}
              filters={[{
                label: 'Type', value: stockType, onChange: setStockType,
                options: [{ value: '', label: 'All Types' }, ...ITEM_TYPE_OPTIONS],
              }]}
              onClear={() => { setSearch(''); setStockType(''); }}
            />
          ) : (
            <FilterBar
              search={{ value: search, onChange: (v) => { setSearch(v); setPage(1); }, placeholder: 'Search reference, item...' }}
              filters={[{
                label: 'Transaction Type', value: txnType, onChange: (v) => { setTxnType(v); setPage(1); },
                options: [{ value: '', label: 'All Types' }, ...TXN_TYPES.map((t) => ({ value: t, label: t.replace(/_/g, ' ') }))],
              }]}
              dateRange={{ from: dateFrom, to: dateTo, onFromChange: (v) => { setDateFrom(v); setPage(1); }, onToChange: (v) => { setDateTo(v); setPage(1); } }}
              onClear={() => { setSearch(''); setTxnType(''); setDateFrom(''); setDateTo(''); setPage(1); }}
            />
          )}
        </div>
        {loading ? <LoadingState /> : tab === 'stock' ? (
          filtered.length === 0 ? <EmptyState /> : (
            <DataTable keyField="item_id" data={filtered} columns={[
              { header: 'Code', accessor: 'item_code' },
              { header: 'Name', accessor: 'item_name' },
              { header: 'Type', accessor: (s) => itemTypeLabel(s.item_type) },
              { header: 'Stock', accessor: 'current_stock', className: 'font-semibold' },
            ]} />
          )
        ) : (
          ledger.items.length === 0 ? <EmptyState /> : (
            <>
              <DataTable keyField="ledger_id" data={ledger.items} columns={[
                { header: 'Date', accessor: (r) => formatDate(r.transaction_date) },
                { header: 'Type', accessor: 'transaction_type' },
                { header: 'Reference', accessor: 'reference_no', hideOnMobile: true },
                { header: 'Item', accessor: (r) => `${r.item_code} - ${r.item_name}` },
                { header: 'In', accessor: 'qty_in' },
                { header: 'Out', accessor: 'qty_out' },
                { header: 'Rate', accessor: 'rate', hideOnMobile: true },
              ]} />
              <Pagination page={page} total={ledger.total} pageSize={ledger.page_size} onChange={setPage} />
            </>
          )
        )}
      </div>
    </div>
  );
}
