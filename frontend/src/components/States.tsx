"use client";

interface MessageProps {
  message: string;
}

export function LoadingState({ message }: MessageProps) {
  return <p className="py-8 text-center text-gray-500">{message}</p>;
}

interface ErrorProps extends MessageProps {
  onRetry: () => void;
}

export function ErrorState({ message, onRetry }: ErrorProps) {
  return (
    <div className="py-8 text-center">
      <p className="text-red-600">{message}</p>
      <button
        type="button"
        onClick={onRetry}
        className="mt-3 rounded bg-gray-900 px-4 py-2 text-sm text-white"
      >
        Retry
      </button>
    </div>
  );
}

interface EmptyProps {
  title: string;
  hint: string;
}

export function EmptyState({ title, hint }: EmptyProps) {
  return (
    <div className="py-8 text-center">
      <p className="font-medium">{title}</p>
      <p className="mt-1 text-sm text-gray-500">{hint}</p>
    </div>
  );
}
