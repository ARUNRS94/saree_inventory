import { useState } from 'react';

interface ConfirmDialogProps {
  open: boolean;
  title: string;
  message: string;
  onConfirm: () => void;
  onCancel: () => void;
  destructive?: boolean;
}

export function ConfirmDialog({ open, title, message, onConfirm, onCancel, destructive }: ConfirmDialogProps) {
  if (!open) return null;
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4">
      <div className="bg-white rounded-xl shadow-xl max-w-sm w-full p-6">
        <h3 className="text-lg font-semibold mb-2">{title}</h3>
        <p className="text-sm text-gray-600 mb-6">{message}</p>
        <div className="flex justify-end gap-3">
          <button className="btn-secondary text-sm" onClick={onCancel}>Cancel</button>
          <button className={destructive ? 'btn-danger text-sm' : 'btn-primary text-sm'} onClick={onConfirm}>Confirm</button>
        </div>
      </div>
    </div>
  );
}

export function useConfirmDialog() {
  const [state, setState] = useState<{ open: boolean; title: string; message: string; resolve: ((v: boolean) => void) | null; destructive?: boolean }>({
    open: false, title: '', message: '', resolve: null,
  });

  const confirm = (title: string, message: string, destructive?: boolean): Promise<boolean> =>
    new Promise((resolve) => setState({ open: true, title, message, resolve, destructive }));

  const dialog = (
    <ConfirmDialog
      open={state.open}
      title={state.title}
      message={state.message}
      destructive={state.destructive}
      onConfirm={() => { state.resolve?.(true); setState((s) => ({ ...s, open: false })); }}
      onCancel={() => { state.resolve?.(false); setState((s) => ({ ...s, open: false })); }}
    />
  );

  return { confirm, dialog };
}
