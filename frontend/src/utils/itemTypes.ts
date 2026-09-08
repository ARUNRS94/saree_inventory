/** Item type codes are stored in the database; these are the labels shown to users. */
export const ITEM_TYPE_LABELS: Record<string, string> = {
  RM: 'Raw Material',
  'Sub process': 'Sub Process',
  FG: 'Finished Goods',
};

export const ITEM_TYPE_OPTIONS = Object.entries(ITEM_TYPE_LABELS).map(([value, label]) => ({ value, label }));

export function itemTypeLabel(code: string | null | undefined): string {
  if (!code) return '';
  return ITEM_TYPE_LABELS[code] ?? code;
}
