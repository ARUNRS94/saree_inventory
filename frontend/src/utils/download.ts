import api from '@/services/api';

/** Downloads a CSV/PDF blob from the API and triggers a browser save. */
export async function downloadFile(url: string, filename: string, params?: Record<string, unknown>) {
  const res = await api.get(url, { params, responseType: 'blob' });
  const href = URL.createObjectURL(res.data);
  const a = document.createElement('a');
  a.href = href;
  a.download = filename;
  a.click();
  URL.revokeObjectURL(href);
}
