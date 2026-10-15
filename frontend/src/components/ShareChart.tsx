"use client";

import {
  CartesianGrid,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

import type { ShareOfVoicePoint } from "@/lib/types";

interface ChartRow {
  label: string;
  share: number | null;
}

export function ShareChart({ points }: { points: ShareOfVoicePoint[] }) {
  const data: ChartRow[] = points.map((point) => ({
    label: `run ${point.run_id}`,
    share: point.share,
  }));
  return (
    <div className="h-64 w-full">
      <ResponsiveContainer width="100%" height="100%">
        <LineChart data={data}>
          <CartesianGrid strokeDasharray="3 3" />
          <XAxis dataKey="label" />
          <YAxis domain={[0, 100]} tickFormatter={(value) => `${value}%`} />
          <Tooltip formatter={(value) => `${value ?? "—"}%`} />
          <Line type="monotone" dataKey="share" stroke="#2563eb" dot />
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}
