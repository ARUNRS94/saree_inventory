import { ChevronDown, ChevronUp, ChevronsUpDown } from 'lucide-react';

export type SortDir = 'asc' | 'desc';

export interface SortState {
  sort_by: string;
  sort_dir: SortDir;
}

interface Column<T> {
  header: string;
  accessor: keyof T | ((row: T) => React.ReactNode);
  className?: string;
  hideOnMobile?: boolean;
  /** Server-side sort key. Omit to make the column unsortable. */
  sortKey?: string;
}

interface Props<T> {
  columns: Column<T>[];
  data: T[];
  onRowClick?: (row: T) => void;
  keyField: keyof T;
  sort?: SortState;
  onSortChange?: (sort: SortState) => void;
}

export function DataTable<T>({ columns, data, onRowClick, keyField, sort, onSortChange }: Props<T>) {
  const toggleSort = (sortKey: string) => {
    if (!onSortChange) return;
    const dir: SortDir = sort?.sort_by === sortKey && sort.sort_dir === 'asc' ? 'desc' : 'asc';
    onSortChange({ sort_by: sortKey, sort_dir: dir });
  };

  return (
    <div className="overflow-x-auto">
      <table className="w-full text-sm">
        <thead>
          <tr className="border-b border-gray-200 bg-gray-50">
            {columns.map((col, i) => {
              const sortable = !!col.sortKey && !!onSortChange;
              const active = sortable && sort?.sort_by === col.sortKey;
              return (
                <th key={i} className={`px-4 py-3 text-left font-semibold text-gray-600 whitespace-nowrap ${col.hideOnMobile ? 'hidden md:table-cell' : ''} ${col.className || ''}`}>
                  {sortable ? (
                    <button
                      type="button"
                      onClick={() => toggleSort(col.sortKey!)}
                      aria-sort={active ? (sort!.sort_dir === 'asc' ? 'ascending' : 'descending') : 'none'}
                      className={`inline-flex items-center gap-1 hover:text-gray-900 ${active ? 'text-primary-700' : ''}`}
                    >
                      {col.header}
                      {active ? (
                        sort!.sort_dir === 'asc'
                          ? <ChevronUp className="h-3.5 w-3.5" />
                          : <ChevronDown className="h-3.5 w-3.5" />
                      ) : (
                        <ChevronsUpDown className="h-3.5 w-3.5 text-gray-300" />
                      )}
                    </button>
                  ) : col.header}
                </th>
              );
            })}
          </tr>
        </thead>
        <tbody>
          {data.map((row) => (
            <tr key={String(row[keyField])} onClick={() => onRowClick?.(row)} className={`border-b border-gray-100 hover:bg-gray-50 ${onRowClick ? 'cursor-pointer' : ''}`}>
              {columns.map((col, i) => (
                <td key={i} className={`px-4 py-3 ${col.hideOnMobile ? 'hidden md:table-cell' : ''} ${col.className || ''}`}>
                  {typeof col.accessor === 'function' ? col.accessor(row) : String(row[col.accessor] ?? '-')}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

interface PaginationProps {
  page: number;
  total: number;
  pageSize: number;
  onChange: (page: number) => void;
}

export function Pagination({ page, total, pageSize, onChange }: PaginationProps) {
  const totalPages = Math.ceil(total / pageSize);
  if (totalPages <= 1) return null;
  return (
    <div className="flex items-center justify-between px-4 py-3 text-sm">
      <span className="text-gray-500">Showing {(page - 1) * pageSize + 1}-{Math.min(page * pageSize, total)} of {total}</span>
      <div className="flex gap-1">
        <button className="btn-secondary text-xs px-3 py-1" disabled={page <= 1} onClick={() => onChange(page - 1)}>Prev</button>
        <button className="btn-secondary text-xs px-3 py-1" disabled={page >= totalPages} onClick={() => onChange(page + 1)}>Next</button>
      </div>
    </div>
  );
}
