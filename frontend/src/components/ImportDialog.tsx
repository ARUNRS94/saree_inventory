import { useEffect, useRef, useState } from 'react';
import api from '@/services/api';
import { downloadFile } from '@/utils/download';
import { Upload, Download, X } from 'lucide-react';

interface ImportError {
  row: number;
  value: string;
  reason: string;
}

interface ImportResult {
  imported: number;
  skipped: number;
  errors: ImportError[];
}

interface ImportSpec {
  entity: string;
  columns: string[];
  required: string[];
  key: string;
}

interface Props {
  entity: 'items' | 'contacts' | 'vendors' | 'process-types';
  title: string;
  onClose: () => void;
  onImported: () => void;
}

export function ImportDialog({ entity, title, onClose, onImported }: Props) {
  const [file, setFile] = useState<File | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [result, setResult] = useState<ImportResult | null>(null);
  const [spec, setSpec] = useState<ImportSpec | null>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  // Read the shape from the server so it always matches the downloadable template.
  useEffect(() => {
    api.get<ImportSpec[]>('/imports')
      .then((r) => setSpec(r.data.find((s) => s.entity === entity) ?? null))
      .catch(() => setError('Could not load the import format.'));
  }, [entity]);

  const downloadTemplate = async () => {
    setError('');
    try {
      await downloadFile(`/imports/${entity}/template`, `${entity}_template.csv`);
    } catch {
      setError('Could not download the template.');
    }
  };

  const upload = async () => {
    if (!file) return;
    setBusy(true); setError(''); setResult(null);
    try {
      const form = new FormData();
      form.append('file', file);
      const res = await api.post(`/imports/${entity}`, form, {
        headers: { 'Content-Type': 'multipart/form-data' },
      });
      setResult(res.data);
      if (res.data.imported > 0) onImported();
    } catch (err: unknown) {
      setError((err as { response?: { data?: { detail?: string } } })?.response?.data?.detail || 'Import failed.');
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4">
      <div className="bg-white rounded-xl shadow-xl w-full max-w-lg max-h-[90vh] overflow-y-auto">
        <div className="flex items-center justify-between px-6 py-4 border-b border-gray-100">
          <h3 className="text-lg font-semibold">Import {title}</h3>
          <button onClick={onClose} className="p-1 rounded hover:bg-gray-100"><X className="h-5 w-5" /></button>
        </div>

        <div className="p-6 space-y-4">
          <div>
            <p className="text-sm text-gray-600 mb-2">
              Upload a CSV with these columns. Rows whose {spec?.key ?? 'key'} already exists are skipped, not overwritten.
            </p>
            <div className="flex flex-wrap gap-1">
              {(spec?.columns ?? []).map((c) => (
                <span key={c} className="text-xs bg-gray-50 text-gray-600 px-1.5 py-0.5 rounded font-mono">
                  {c}{spec?.required.includes(c) ? '*' : ''}
                </span>
              ))}
            </div>
          </div>

          <button
            className="btn-secondary text-sm flex items-center gap-1.5"
            onClick={downloadTemplate}
            disabled={!spec}
          >
            <Download className="h-4 w-4" /> Download template
          </button>

          <div>
            <label className="label">CSV file</label>
            <input
              ref={inputRef}
              type="file"
              accept=".csv,text/csv"
              className="input"
              onChange={(e) => { setFile(e.target.files?.[0] || null); setResult(null); setError(''); }}
            />
          </div>

          {error && <div className="bg-red-50 text-red-700 text-sm px-4 py-2 rounded-lg">{error}</div>}

          {result && (
            <div className="space-y-2">
              <div className="flex gap-4 text-sm">
                <span className="text-green-700 font-medium">{result.imported} imported</span>
                <span className="text-amber-700 font-medium">{result.skipped} skipped</span>
                <span className="text-red-700 font-medium">{result.errors.length} failed</span>
              </div>
              {result.errors.length > 0 && (
                <div className="border border-gray-200 rounded-lg max-h-48 overflow-y-auto">
                  <table className="w-full text-xs">
                    <thead className="bg-gray-50 sticky top-0">
                      <tr>
                        <th className="px-2 py-1.5 text-left font-semibold text-gray-600">Row</th>
                        <th className="px-2 py-1.5 text-left font-semibold text-gray-600">Value</th>
                        <th className="px-2 py-1.5 text-left font-semibold text-gray-600">Reason</th>
                      </tr>
                    </thead>
                    <tbody>
                      {result.errors.map((e, i) => (
                        <tr key={i} className="border-t border-gray-100">
                          <td className="px-2 py-1.5">{e.row}</td>
                          <td className="px-2 py-1.5 font-mono">{e.value || '—'}</td>
                          <td className="px-2 py-1.5 text-red-600">{e.reason}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </div>
          )}
        </div>

        <div className="flex justify-end gap-2 px-6 py-4 border-t border-gray-100">
          <button className="btn-secondary text-sm" onClick={onClose}>{result ? 'Close' : 'Cancel'}</button>
          <button className="btn-primary text-sm flex items-center gap-1.5" onClick={upload} disabled={!file || busy}>
            <Upload className="h-4 w-4" /> {busy ? 'Importing...' : 'Import'}
          </button>
        </div>
      </div>
    </div>
  );
}
