import { useEffect, useState, useCallback } from 'react';
import api from '@/services/api';
import type { PurchaseOrder, Contact, Item, PaginatedResponse } from '@/types';
import { PageHeader } from '@/components/PageHeader';
import { FilterBar } from '@/components/FilterBar';
import { DataTable, Pagination } from '@/components/DataTable';
import { StatusBadge } from '@/components/StatusBadge';
import { LoadingState, EmptyState } from '@/components/LoadingState';
import { useConfirmDialog } from '@/components/ConfirmDialog';
import { formatDate, formatCurrency, sumBy } from '@/utils/format';
import { itemTypeLabel } from '@/utils/itemTypes';
import { CUSTOMER, SUB_VENDOR } from '@/utils/contactTypes';

type POLineForm = {
  item_id: string;
  stock_out_item_id: string;
  target_fg_item_id: string;
  quantity: string;
  rate: string;
  lr_number: string;
};

const emptyLine = (): POLineForm => ({ item_id: '', stock_out_item_id: '', target_fg_item_id: '', quantity: '', rate: '', lr_number: '' });

export default function PurchaseOrdersPage() {
  const [data, setData] = useState<PaginatedResponse<PurchaseOrder>>({ items: [], total: 0, page: 1, page_size: 50 });
  const [page, setPage] = useState(1);
  const [search, setSearch] = useState('');
  const [filterStatus, setFilterStatus] = useState('');
  const [filterContact, setfilterContact] = useState('');
  const [dateFrom, setDateFrom] = useState('');
  const [dateTo, setDateTo] = useState('');
  const [loading, setLoading] = useState(true);
  const [showForm, setShowForm] = useState(false);
  const [contacts, setContacts] = useState<Contact[]>([]);
  const [items, setItems] = useState<Item[]>([]);
  const [allItems, setAllItems] = useState<Item[]>([]);
  // Numeric fields are held as strings so the box can be cleared instead of snapping back to 0.
  const [form, setForm] = useState({ contact_id: '', remarks: '' });
  const [draft, setDraft] = useState<POLineForm>(emptyLine());
  const [lines, setLines] = useState<POLineForm[]>([]);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');
  const { confirm, dialog } = useConfirmDialog();

  const load = useCallback(() => {
    setLoading(true);
    api.get('/purchase-orders', { params: {
      page, page_size: 50, search: search || undefined,
      status: filterStatus || undefined, contact_id: filterContact || undefined,
      date_from: dateFrom || undefined, date_to: dateTo || undefined,
    } }).then((r) => setData(r.data)).finally(() => setLoading(false));
  }, [page, search, filterStatus, filterContact, dateFrom, dateTo]);

  useEffect(() => { load(); }, [load]);
  useEffect(() => {
    api.get('/contacts', { params: { page_size: 200 } }).then((r) => setContacts(r.data.items.filter((s: Contact) => s.contact_type !== CUSTOMER)));
    api.get('/items', { params: { page_size: 500 } }).then((r) => setAllItems(r.data.items));
  }, []);

  const selectedContact = contacts.find((s) => s.contact_id === Number(form.contact_id));
  const isSubVendor = selectedContact?.contact_type === SUB_VENDOR;

  useEffect(() => {
    const itemType = isSubVendor ? 'Sub process' : 'RM';
    setItems(allItems.filter((s) => s.item_type === itemType));
  }, [form.contact_id, allItems, isSubVendor]);

  const openNew = () => { setForm({ contact_id: '', remarks: '' }); setDraft(emptyLine()); setLines([]); setShowForm(true); setError(''); };

  const itemLabel = (id: string) => {
    const match = allItems.find((s) => s.item_id === Number(id));
    return match ? `${match.item_code} - ${match.item_name}` : '-';
  };

  const draftError = () => {
    if (!form.contact_id) return 'Select the vendor before adding items.';
    if (!draft.item_id) return 'Select a stock in item.';
    if (Number(draft.quantity) <= 0) return 'Quantity must be greater than zero.';
    if (draft.rate === '' || Number(draft.rate) < 0) return 'Enter a rate of zero or more.';
    if (isSubVendor && !draft.stock_out_item_id) return 'Select the stock out item.';
    if (isSubVendor && !draft.target_fg_item_id) return 'Select the target FG item.';
    const duplicate = lines.some((line) => line.item_id === draft.item_id && line.lr_number === draft.lr_number);
    if (duplicate) return 'That item is already on this PO with the same LR number.';
    return '';
  };

  const addLine = () => {
    const problem = draftError();
    if (problem) { setError(problem); return; }
    setError('');
    setLines((prev) => [...prev, draft]);
    // Vendor-level selections usually repeat down the PO, so only the per-item fields reset.
    setDraft({ ...emptyLine(), stock_out_item_id: draft.stock_out_item_id, target_fg_item_id: draft.target_fg_item_id });
  };

  const removeLine = (index: number) => setLines((prev) => prev.filter((_, i) => i !== index));

  const lineAmount = (line: POLineForm) => Number(line.quantity || 0) * Number(line.rate || 0);
  const totalAmount = lines.reduce((sum, line) => sum + lineAmount(line), 0);

  const save = async (e: React.FormEvent) => {
    e.preventDefault();
    if (lines.length === 0) { setError('Add at least one item to the PO.'); return; }
    if (!(await confirm('Create Purchase Order', `Create this purchase order with ${lines.length} item(s) and post stock movements?`))) return;
    setSaving(true); setError(''); setSuccess('');
    try {
      const body = {
        contact_id: Number(form.contact_id),
        remarks: form.remarks || null,
        items: lines.map((line) => ({
          item_id: Number(line.item_id),
          quantity: Number(line.quantity),
          rate: Number(line.rate),
          stock_out_item_id: isSubVendor && line.stock_out_item_id ? Number(line.stock_out_item_id) : null,
          target_fg_item_id: isSubVendor && line.target_fg_item_id ? Number(line.target_fg_item_id) : null,
          lr_number: line.lr_number || null,
        })),
      };
      const res = await api.post('/purchase-orders', body);
      setSuccess(`Purchase Order ${res.data.po_number} created.`);
      setShowForm(false); load();
    } catch (err: unknown) { setError((err as { response?: { data?: { detail?: string } } })?.response?.data?.detail || 'Failed'); }
    finally { setSaving(false); }
  };

  const cancelPO = async (po: PurchaseOrder) => {
    if (!(await confirm('Cancel Purchase Order', `Cancel ${po.po_number} and reverse any Sub vendor WIP/stock issue movements?`, true))) return;
    try {
      await api.post(`/purchase-orders/${po.po_id}/cancel`);
      setSuccess(`PO ${po.po_number} cancelled.`); load();
    } catch (err: unknown) { setError((err as { response?: { data?: { detail?: string } } })?.response?.data?.detail || 'Failed'); }
  };

  const fgItems = allItems.filter((s) => s.item_type === 'FG');
  const rmfgItems = allItems.filter((s) => s.item_type === 'RM' || s.item_type === 'FG');

  return (
    <div>
      {dialog}
      <PageHeader title="Purchase Orders" actions={<button className="btn-primary text-sm" onClick={openNew}>+ Create PO</button>} />
      {success && <div className="bg-green-50 text-green-700 text-sm px-4 py-2 rounded-lg mb-4">{success}</div>}
      {error && <div className="bg-red-50 text-red-700 text-sm px-4 py-2 rounded-lg mb-4">{error}</div>}

      {showForm && (
        <div className="card p-4 sm:p-6 mb-6">
          <h3 className="font-semibold mb-4">New Purchase Order</h3>
          <form onSubmit={save}>
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
              <div><label className="label">Raw Material / Sub Vendor *</label>
                <select className="input" value={form.contact_id} onChange={(e) => { setForm({ ...form, contact_id: e.target.value }); setDraft(emptyLine()); setLines([]); }} required>
                  <option value="">Select</option>
                  {contacts.map((s) => <option key={s.contact_id} value={s.contact_id}>{s.contact_name} ({s.contact_type})</option>)}
                </select>
              </div>
              <div className="sm:col-span-1 lg:col-span-2"><label className="label">Remarks (applies to whole PO)</label>
                <input className="input" value={form.remarks} onChange={(e) => setForm({ ...form, remarks: e.target.value })} />
              </div>
            </div>

            <div className="mt-6 border border-gray-200 rounded-lg p-3">
              <h4 className="font-medium text-sm mb-3">Add Item</h4>
              <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
                <div><label className="label">Stock In Item *</label>
                  <select className="input" value={draft.item_id} onChange={(e) => setDraft({ ...draft, item_id: e.target.value })}>
                    <option value="">Select</option>
                    {items.map((s) => <option key={s.item_id} value={s.item_id}>{s.item_code} - {s.item_name}</option>)}
                  </select>
                </div>
                {isSubVendor && (
                  <>
                    <div><label className="label">Stock Out Item (RM/FG) *</label>
                      <select className="input" value={draft.stock_out_item_id} onChange={(e) => setDraft({ ...draft, stock_out_item_id: e.target.value })}>
                        <option value="">Select</option>
                        {rmfgItems.map((s) => <option key={s.item_id} value={s.item_id}>{s.item_code} - {s.item_name} ({itemTypeLabel(s.item_type)})</option>)}
                      </select>
                    </div>
                    <div><label className="label">Target FG Item (For GRN) *</label>
                      <select className="input" value={draft.target_fg_item_id} onChange={(e) => setDraft({ ...draft, target_fg_item_id: e.target.value })}>
                        <option value="">Select</option>
                        {fgItems.map((s) => <option key={s.item_id} value={s.item_id}>{s.item_code} - {s.item_name}</option>)}
                      </select>
                    </div>
                  </>
                )}
                <div><label className="label">Quantity *</label><input className="input" type="number" min={1} value={draft.quantity} onChange={(e) => setDraft({ ...draft, quantity: e.target.value })} /></div>
                <div><label className="label">Rate / Process Charges *</label><input className="input" type="number" min={0} step={0.01} value={draft.rate} onChange={(e) => setDraft({ ...draft, rate: e.target.value })} /></div>
                <div><label className="label">LR Number</label><input className="input" maxLength={50} value={draft.lr_number} onChange={(e) => setDraft({ ...draft, lr_number: e.target.value })} /></div>
                <div><label className="label">Amount</label><p className="input bg-gray-50">{formatCurrency(lineAmount(draft))}</p></div>
                <div className="flex items-end">
                  <button type="button" className="btn-primary text-sm w-full" onClick={addLine}>+ Add to List</button>
                </div>
              </div>
            </div>

            <div className="mt-6">
              <h4 className="font-medium text-sm mb-2">Items on this PO ({lines.length})</h4>
              {lines.length === 0 ? (
                <p className="text-sm text-gray-500 border border-dashed border-gray-300 rounded-lg px-3 py-6 text-center">
                  No items yet. Fill the fields above and choose "Add to List".
                </p>
              ) : (
                <div className="overflow-x-auto border border-gray-200 rounded-lg">
                  <table className="w-full text-sm">
                    <thead className="bg-gray-50 text-gray-600">
                      <tr>
                        <th className="px-3 py-2 text-left font-medium">#</th>
                        <th className="px-3 py-2 text-left font-medium">Stock In Item</th>
                        {isSubVendor && <th className="px-3 py-2 text-left font-medium">Stock Out</th>}
                        {isSubVendor && <th className="px-3 py-2 text-left font-medium">Target FG</th>}
                        <th className="px-3 py-2 text-right font-medium">Qty</th>
                        <th className="px-3 py-2 text-right font-medium">Rate</th>
                        <th className="px-3 py-2 text-left font-medium">LR No</th>
                        <th className="px-3 py-2 text-right font-medium">Amount</th>
                        <th className="px-3 py-2" />
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-gray-100">
                      {lines.map((line, index) => (
                        <tr key={index}>
                          <td className="px-3 py-2 text-gray-500">{index + 1}</td>
                          <td className="px-3 py-2">{itemLabel(line.item_id)}</td>
                          {isSubVendor && <td className="px-3 py-2">{itemLabel(line.stock_out_item_id)}</td>}
                          {isSubVendor && <td className="px-3 py-2">{itemLabel(line.target_fg_item_id)}</td>}
                          <td className="px-3 py-2 text-right">{line.quantity}</td>
                          <td className="px-3 py-2 text-right">{formatCurrency(line.rate)}</td>
                          <td className="px-3 py-2">{line.lr_number || '-'}</td>
                          <td className="px-3 py-2 text-right font-medium">{formatCurrency(lineAmount(line))}</td>
                          <td className="px-3 py-2 text-right">
                            <button type="button" className="text-red-600 text-xs hover:underline" onClick={() => removeLine(index)}>Remove</button>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </div>

            <div className="mt-4 flex flex-wrap items-center gap-4">
              <span className="text-sm font-medium">Total: {formatCurrency(totalAmount)}</span>
              <div className="flex gap-2">
                <button type="submit" className="btn-primary text-sm" disabled={saving || lines.length === 0}>{saving ? 'Creating...' : 'Create PO'}</button>
                <button type="button" className="btn-secondary text-sm" onClick={() => setShowForm(false)}>Cancel</button>
              </div>
            </div>
          </form>
        </div>
      )}

      <div className="card">
        <div className="p-4 border-b border-gray-100">
          <FilterBar
            search={{ value: search, onChange: (v) => { setSearch(v); setPage(1); }, placeholder: 'Search PO number, contact...' }}
            filters={[
              { label: 'Status', value: filterStatus, onChange: (v) => { setFilterStatus(v); setPage(1); },
                options: [{ value: '', label: 'All' }, { value: 'OPEN', label: 'Open' }, { value: 'PARTIAL', label: 'Partial' }, { value: 'CLOSED', label: 'Closed' }, { value: 'CANCELLED', label: 'Cancelled' }] },
              { label: 'Contact', value: filterContact, onChange: (v) => { setfilterContact(v); setPage(1); },
                options: [{ value: '', label: 'All Contacts' }, ...contacts.map((s) => ({ value: String(s.contact_id), label: s.contact_name }))] },
            ]}
            dateRange={{ from: dateFrom, to: dateTo, onFromChange: (v) => { setDateFrom(v); setPage(1); }, onToChange: (v) => { setDateTo(v); setPage(1); } }}
            onClear={() => { setSearch(''); setFilterStatus(''); setfilterContact(''); setDateFrom(''); setDateTo(''); setPage(1); }}
          />
        </div>
        {loading ? <LoadingState /> : data.items.length === 0 ? <EmptyState /> : (
          <>
            <DataTable keyField="po_id" data={data.items} columns={[
              { header: 'PO No', accessor: 'po_number' },
              { header: 'Contact', accessor: 'contact_name' },
              { header: 'Type', accessor: 'contact_type', hideOnMobile: true },
              { header: 'Date', accessor: (r) => formatDate(r.po_date) },
              { header: 'Items', accessor: (r) => r.items.map((i) => i.item_code).join(', '), hideOnMobile: true },
              { header: 'LR No', accessor: (r) => r.items.map((i) => i.lr_number).filter(Boolean).join(', ') || '-', hideOnMobile: true },
              { header: 'Qty', accessor: (r) => sumBy(r.items, (i) => i.ordered_qty) },
              { header: 'Amount', accessor: (r) => formatCurrency(sumBy(r.items, (i) => i.amount)), hideOnMobile: true },
              { header: 'Status', accessor: (r) => <StatusBadge status={r.status} /> },
              { header: '', accessor: (r) => r.status !== 'CANCELLED' && r.status !== 'CLOSED' ? (
                <button className="text-red-600 text-xs hover:underline" onClick={(e) => { e.stopPropagation(); cancelPO(r); }}>Cancel</button>
              ) : null },
            ]} />
            <Pagination page={page} total={data.total} pageSize={data.page_size} onChange={setPage} />
          </>
        )}
      </div>
    </div>
  );
}
