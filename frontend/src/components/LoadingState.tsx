export function LoadingState({ message = 'Loading...' }: { message?: string }) {
  return (
    <div className="flex items-center justify-center py-12">
      <div className="text-center">
        <div className="animate-spin rounded-full h-10 w-10 border-b-2 border-primary-600 mx-auto mb-3" />
        <p className="text-gray-500 text-sm">{message}</p>
      </div>
    </div>
  );
}

export function EmptyState({ message = 'No data found.' }: { message?: string }) {
  return (
    <div className="flex items-center justify-center py-12">
      <p className="text-gray-400 text-sm">{message}</p>
    </div>
  );
}

export function ErrorState({ message = 'Something went wrong.' }: { message?: string }) {
  return (
    <div className="flex items-center justify-center py-12">
      <p className="text-red-500 text-sm">{message}</p>
    </div>
  );
}
