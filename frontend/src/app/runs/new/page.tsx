"use client";

import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";

import { ErrorState, LoadingState } from "@/components/States";
import { ApiError, api } from "@/lib/api";
import type { BrandOut, ProviderName } from "@/lib/types";

export default function NewRunPage() {
  const router = useRouter();
  const [brands, setBrands] = useState<BrandOut[]>([]);
  const [loadingBrands, setLoadingBrands] = useState(true);
  const [loadError, setLoadError] = useState("");
  const [brandId, setBrandId] = useState("");
  const [promptsText, setPromptsText] = useState("");
  const [provider, setProvider] = useState<ProviderName>("gemini");
  const [formError, setFormError] = useState("");
  const [submitting, setSubmitting] = useState(false);

  useEffect(() => {
    api
      .listBrands()
      .then((rows) => {
        setBrands(rows);
        setLoadingBrands(false);
      })
      .catch((err: unknown) => {
        setLoadError(
          err instanceof ApiError ? err.message : "Could not load brands",
        );
        setLoadingBrands(false);
      });
  }, []);

  async function onSubmit(event: React.FormEvent) {
    event.preventDefault();
    const prompts = promptsText
      .split("\n")
      .map((line) => line.trim())
      .filter((line) => line.length > 0);
    if (brandId === "") {
      setFormError("Choose a brand first.");
      return;
    }
    if (prompts.length === 0) {
      setFormError("Enter at least one prompt (one per line).");
      return;
    }
    setFormError("");
    setSubmitting(true);
    try {
      await api.createRun(Number(brandId), prompts, provider);
      router.push("/");
    } catch (err) {
      setFormError(
        err instanceof ApiError ? err.message : "Could not create run",
      );
      setSubmitting(false);
    }
  }

  if (loadingBrands) return <LoadingState message="Loading brands…" />;
  if (loadError)
    return (
      <main className="mx-auto max-w-xl p-6">
        <ErrorState message={loadError} onRetry={() => window.location.reload()} />
      </main>
    );

  return (
    <main className="mx-auto max-w-xl p-6">
      <h1 className="text-2xl font-bold">New run</h1>
      <form onSubmit={(event) => void onSubmit(event)} className="mt-6 space-y-4">
        <label className="block">
          <span className="text-sm font-medium">Brand</span>
          <select
            value={brandId}
            onChange={(event) => setBrandId(event.target.value)}
            className="mt-1 block w-full rounded border p-2"
          >
            <option value="">Select a brand…</option>
            {brands.map((brand) => (
              <option key={brand.id} value={brand.id}>
                {brand.name}
              </option>
            ))}
          </select>
        </label>

        <label className="block">
          <span className="text-sm font-medium">Prompts (one per line)</span>
          <textarea
            value={promptsText}
            onChange={(event) => setPromptsText(event.target.value)}
            rows={6}
            placeholder={"best widgets?\ncheapest widgets?"}
            className="mt-1 block w-full rounded border p-2"
          />
        </label>

        <label className="block">
          <span className="text-sm font-medium">Provider</span>
          <select
            value={provider}
            onChange={(event) => setProvider(event.target.value as ProviderName)}
            className="mt-1 block w-full rounded border p-2"
          >
            <option value="gemini">gemini</option>
            <option value="openai">openai</option>
          </select>
        </label>

        {formError !== "" && <p className="text-sm text-red-600">{formError}</p>}

        <button
          type="submit"
          disabled={submitting}
          className="rounded bg-gray-900 px-4 py-2 text-sm text-white disabled:opacity-50"
        >
          {submitting ? "Starting…" : "Start run"}
        </button>
      </form>
    </main>
  );
}
