interface Column<T> {
  header: string;
  accessor: keyof T | ((row: T) => React.ReactNode);
  className?: string;
  hideOnMobile?: boolean;
}

interface Props<T> {
  columns: Column<T>[];
  data: T[];
  onRowClick?: (row: T) => void;
  keyField: keyof T;
}

export function DataTable<T>({ columns, data, onRowClick, keyField }: Props<T>) {
  return (
    <div className="overflow-x-auto">
      <table className="w-full text-sm">
        <thead>
          <tr className="border-b border-gray-200 bg-gray-50">
            {columns.map((col, i) => (
              <th key={i} className={`px-4 py-3 text-left font-semibold text-gray-600 whitespace-nowrap ${col.hideOnMobile ? 'hidden md:table-cell' : ''} ${col.className || ''}`}>
                {col.header}
              </th>
            ))}
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
