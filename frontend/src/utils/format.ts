export function toNumber(value: unknown): number {
  const n = typeof value === 'number' ? value : Number(value);
  return Number.isFinite(n) ? n : 0;
}

export function sumBy<T>(rows: T[], pick: (row: T) => unknown): number {
  return rows.reduce((total, row) => total + toNumber(pick(row)), 0);
}

export function formatCurrency(value: unknown): string {
  return new Intl.NumberFormat('en-IN', { style: 'currency', currency: 'INR', minimumFractionDigits: 2 }).format(toNumber(value));
}

export function formatNumber(value: unknown): string {
  return new Intl.NumberFormat('en-IN').format(toNumber(value));
}

export function formatDate(date: string | null): string {
  if (!date) return '-';
  return new Date(date).toLocaleDateString('en-IN', { year: 'numeric', month: 'short', day: 'numeric' });
}
