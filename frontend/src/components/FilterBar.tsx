import { SearchInput } from './SearchInput';

interface FilterOption {
  value: string;
  label: string;
}

interface FilterBarProps {
  search?: { value: string; onChange: (v: string) => void; placeholder?: string };
  filters?: { label: string; value: string; onChange: (v: string) => void; options: FilterOption[] }[];
  dateRange?: { from: string; to: string; onFromChange: (v: string) => void; onToChange: (v: string) => void };
  onClear?: () => void;
}

export function FilterBar({ search, filters, dateRange, onClear }: FilterBarProps) {
  const hasActiveFilters = filters?.some((f) => f.value) || dateRange?.from || dateRange?.to;

  return (
    <div className="flex flex-col sm:flex-row gap-3 flex-wrap items-start sm:items-end">
      {search && (
        <div className="w-full sm:w-64">
          <SearchInput value={search.value} onChange={search.onChange} placeholder={search.placeholder} />
        </div>
      )}
      {filters?.map((f) => (
        <div key={f.label} className="w-full sm:w-auto">
          <label className="text-xs text-gray-500 mb-0.5 block">{f.label}</label>
          <select className="input text-sm py-1.5 sm:w-40" value={f.value} onChange={(e) => f.onChange(e.target.value)}>
            {f.options.map((o) => <option key={o.value} value={o.value}>{o.label}</option>)}
          </select>
        </div>
      ))}
      {dateRange && (
        <>
          <div className="w-full sm:w-auto">
            <label className="text-xs text-gray-500 mb-0.5 block">From</label>
            <input type="date" className="input text-sm py-1.5" value={dateRange.from} onChange={(e) => dateRange.onFromChange(e.target.value)} />
          </div>
          <div className="w-full sm:w-auto">
            <label className="text-xs text-gray-500 mb-0.5 block">To</label>
            <input type="date" className="input text-sm py-1.5" value={dateRange.to} onChange={(e) => dateRange.onToChange(e.target.value)} />
          </div>
        </>
      )}
      {onClear && hasActiveFilters && (
        <button className="text-xs text-primary-600 hover:underline whitespace-nowrap pt-4" onClick={onClear}>Clear filters</button>
      )}
    </div>
  );
}
