import { useEffect, useState } from 'react';
import api from '@/services/api';
import type { StockSummary, StockValuation } from '@/types';
import { PageHeader } from '@/components/PageHeader';
import { DataTable } from '@/components/DataTable';
import { LoadingState, EmptyState } from '@/components/LoadingState';
import { formatCurrency } from '@/utils/format';
import { Download } from 'lucide-react';

export default function ReportsPage() {
  const [tab, setTab] = useState<'stock' | 'valuation'>('stock');
  const [stock, setStock] = useState<StockSummary[]>([]);
  const [valuation, setValuation] = useState<StockValuation[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    setLoading(true);
    if (tab === 'stock') {
      api.get('/inventory/stock').then((r) => setStock(r.data)).finally(() => setLoading(false));
    } else {
      api.get('/inventory/valuation').then((r) => setValuation(r.data)).finally(() => setLoading(false));
    }
  }, [tab]);

  const downloadCSV = () => {
    const url = tab === 'stock' ? '/reports/stock/csv' : '/reports/valuation/csv';
    api.get(url, { responseType: 'blob' }).then((r) => {
      const a = document.createElement('a');
      a.href = URL.createObjectURL(r.data);
      a.download = `${tab}_report.csv`;
      a.click();
    });
  };

  const downloadPDF = () => {
    const url = tab === 'stock' ? '/reports/stock/pdf' : '/reports/valuation/pdf';
    api.get(url, { responseType: 'blob' }).then((r) => {
      const a = document.createElement('a');
      a.href = URL.createObjectURL(r.data);
      a.download = `${tab}_report.pdf`;
      a.click();
    });
  };

  return (
    <div>
      <PageHeader title="Reports" actions={
        <div className="flex gap-2">
          <button className="btn-secondary text-sm flex items-center gap-1" onClick={downloadCSV}><Download className="h-4 w-4" /> CSV</button>
          <button className="btn-secondary text-sm flex items-center gap-1" onClick={downloadPDF}><Download className="h-4 w-4" /> PDF</button>
        </div>
      } />

      <div className="flex gap-2 mb-4">
        <button className={tab === 'stock' ? 'btn-primary text-sm' : 'btn-secondary text-sm'} onClick={() => setTab('stock')}>Stock Report</button>
        <button className={tab === 'valuation' ? 'btn-primary text-sm' : 'btn-secondary text-sm'} onClick={() => setTab('valuation')}>Valuation</button>
      </div>

      <div className="card">
        {loading ? <LoadingState /> : tab === 'stock' ? (
          stock.length === 0 ? <EmptyState /> : (
            <DataTable keyField="saree_id" data={stock} columns={[
              { header: 'Code', accessor: 'saree_code' },
              { header: 'Name', accessor: 'saree_name' },
              { header: 'Type', accessor: 'fabric' },
              { header: 'Stock', accessor: 'current_stock', className: 'font-semibold' },
            ]} />
          )
        ) : (
          valuation.length === 0 ? <EmptyState /> : (
            <>
              <DataTable keyField="saree_id" data={valuation} columns={[
                { header: 'Code', accessor: 'saree_code' },
                { header: 'Name', accessor: 'saree_name' },
                { header: 'Stock', accessor: 'current_stock' },
                { header: 'Rate', accessor: (r) => formatCurrency(r.latest_rate), hideOnMobile: true },
                { header: 'Value', accessor: (r) => formatCurrency(r.value), className: 'font-semibold' },
              ]} />
              <div className="px-4 py-3 border-t border-gray-100 text-right font-semibold">
                Total: {formatCurrency(valuation.reduce((s, r) => s + r.value, 0))}
              </div>
            </>
          )
        )}
      </div>
    </div>
  );
}
