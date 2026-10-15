"use client";

import Link from "next/link";
import { useEffect, useState } from "react";

import { EmptyState, ErrorState, LoadingState } from "@/components/States";
import { StatusBadge } from "@/components/StatusBadge";
import { ApiError, api } from "@/lib/api";
import type { RunSummaryOut } from "@/lib/types";

type ViewState = "loading" | "error" | "ready";

export default function RunsPage() {
  const [view, setView] = useState<ViewState>("loading");
  const [runs, setRuns] = useState<RunSummaryOut[]>([]);
  const [error, setError] = useState("");

  async function load() {
    setView("loading");
    try {
      setRuns(await api.listRuns());
      setView("ready");
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Could not load runs");
      setView("error");
    }
  }

  useEffect(() => {
    void load();
  }, []);

  return (
    <main className="mx-auto max-w-3xl p-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold">Runs</h1>
        <Link
          href="/runs/new"
          className="rounded bg-gray-900 px-4 py-2 text-sm text-white"
        >
          New run
        </Link>
      </div>

      {view === "loading" && <LoadingState message="Loading runs…" />}
      {view === "error" && <ErrorState message={error} onRetry={() => void load()} />}
      {view === "ready" && runs.length === 0 && (
        <EmptyState
          title="No runs yet"
          hint="Create your first run to measure brand visibility."
        />
      )}
      {view === "ready" && runs.length > 0 && (
        <ul className="mt-6 space-y-3">
          {runs.map((run) => (
            <li key={run.id} className="rounded border p-4">
              <div className="flex items-center justify-between">
                <span className="font-medium">
                  Run #{run.id} · {run.brand_name}
                </span>
                <StatusBadge status={run.status} />
              </div>
              <p className="mt-1 text-sm text-gray-500">
                {run.response_count} responses ·{" "}
                {new Date(run.triggered_at).toLocaleString()}
              </p>
              <Link
                href={`/brands/${run.brand_id}`}
                className="mt-2 inline-block text-sm text-blue-600 underline"
              >
                View brand dashboard
              </Link>
            </li>
          ))}
        </ul>
      )}
    </main>
  );
}
