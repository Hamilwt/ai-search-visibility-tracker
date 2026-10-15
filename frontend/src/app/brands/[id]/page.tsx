"use client";

import Link from "next/link";
import { use, useEffect, useState } from "react";

import { ShareChart } from "@/components/ShareChart";
import { EmptyState, ErrorState, LoadingState } from "@/components/States";
import { ApiError, api } from "@/lib/api";
import type { ShareOfVoiceResponse } from "@/lib/types";

type ViewState = "loading" | "error" | "ready";

export default function BrandDashboard({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = use(params);
  const [view, setView] = useState<ViewState>("loading");
  const [data, setData] = useState<ShareOfVoiceResponse | null>(null);
  const [error, setError] = useState("");

  async function load() {
    setView("loading");
    try {
      setData(await api.shareOfVoice(Number(id)));
      setView("ready");
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Could not load dashboard");
      setView("error");
    }
  }

  useEffect(() => {
    void load();
  }, []);

  return (
    <main className="mx-auto max-w-3xl p-6">
      <Link href="/" className="text-sm text-blue-600 underline">
        ← All runs
      </Link>
      <h1 className="mt-2 text-2xl font-bold">
        {data ? data.brand_name : `Brand ${id}`}
      </h1>

      {view === "loading" && <LoadingState message="Loading dashboard…" />}
      {view === "error" && <ErrorState message={error} onRetry={() => void load()} />}
      {view === "ready" && data && data.points.length === 0 && (
        <EmptyState
          title="No runs yet"
          hint="Create a run for this brand to see share-of-voice."
        />
      )}
      {view === "ready" && data && data.points.length > 0 && (
        <>
          <div className="mt-6">
            <ShareChart points={data.points} />
          </div>
          <table className="mt-6 w-full text-sm">
            <thead>
              <tr className="text-left text-gray-500">
                <th className="py-2">Run</th>
                <th>Date</th>
                <th>Target</th>
                <th>Total</th>
                <th>Share</th>
                <th>Avg rank</th>
              </tr>
            </thead>
            <tbody>
              {data.points.map((point) => (
                <tr key={point.run_id} className="border-t">
                  <td className="py-2">#{point.run_id}</td>
                  <td>{new Date(point.triggered_at).toLocaleDateString()}</td>
                  <td>{point.target_mentions}</td>
                  <td>{point.total_mentions}</td>
                  <td>{point.share === null ? "—" : `${point.share}%`}</td>
                  <td>
                    {point.avg_rank_position === null
                      ? "—"
                      : point.avg_rank_position.toFixed(1)}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </>
      )}
    </main>
  );
}
