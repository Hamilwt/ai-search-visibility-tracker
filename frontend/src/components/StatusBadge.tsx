"use client";

const COLORS: Record<string, string> = {
  pending: "bg-yellow-100 text-yellow-800",
  running: "bg-blue-100 text-blue-800",
  completed: "bg-green-100 text-green-800",
  failed: "bg-red-100 text-red-800",
};

export function StatusBadge({ status }: { status: string }) {
  const color = COLORS[status] ?? "bg-gray-100 text-gray-800";
  return (
    <span className={`rounded-full px-2 py-1 text-xs font-medium ${color}`}>
      {status}
    </span>
  );
}
