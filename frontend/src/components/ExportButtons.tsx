import { Download } from 'lucide-react';
import api from '@/services/api';

type Params = Record<string, string | number | boolean | undefined>;

export async function downloadReport(report: string, format: 'csv' | 'pdf', params: Params) {
  const response = await api.get(`/reports/${report}/${format}`, { params, responseType: 'blob' });
  const link = document.createElement('a');
  link.href = URL.createObjectURL(response.data);
  link.download = `${report}_report.${format}`;
  link.click();
  URL.revokeObjectURL(link.href);
}

export function ExportButtons({ report, params }: { report: string; params: Params }) {
  return (
    <div className="flex gap-2">
      <button type="button" className="btn-secondary text-sm flex items-center gap-1" onClick={() => downloadReport(report, 'csv', params)}>
        <Download className="h-4 w-4" /> CSV
      </button>
      <button type="button" className="btn-secondary text-sm flex items-center gap-1" onClick={() => downloadReport(report, 'pdf', params)}>
        <Download className="h-4 w-4" /> PDF
      </button>
    </div>
  );
}
