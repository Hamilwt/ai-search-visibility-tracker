import type {
  BrandOut,
  ProviderName,
  RunCreateResponse,
  RunDetailOut,
  RunSummaryOut,
  ShareOfVoiceResponse,
} from "./types";

const BASE_URL =
  process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

/** Thrown for non-2xx responses; carries the backend error envelope. */
export class ApiError extends Error {
  code: string;
  status: number;

  constructor(code: string, message: string, status: number) {
    super(message);
    this.code = code;
    this.status = status;
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${BASE_URL}${path}`, {
    ...init,
    headers: { "Content-Type": "application/json", ...init?.headers },
  });
  const body = (await response.json()) as unknown;
  if (!response.ok) {
    const envelope = body as {
      error?: { code?: string; message?: string };
    };
    throw new ApiError(
      envelope.error?.code ?? "http_error",
      envelope.error?.message ?? `Request failed (${response.status})`,
      response.status,
    );
  }
  return body as T;
}

export const api = {
  listBrands(): Promise<BrandOut[]> {
    return request<BrandOut[]>("/brands");
  },

  listRuns(brandId?: number): Promise<RunSummaryOut[]> {
    const query = brandId !== undefined ? `?brand_id=${brandId}` : "";
    return request<RunSummaryOut[]>(`/runs${query}`);
  },

  createRun(
    brandId: number,
    prompts: string[],
    provider: ProviderName,
  ): Promise<RunCreateResponse> {
    return request<RunCreateResponse>("/runs", {
      method: "POST",
      body: JSON.stringify({
        brand_id: brandId,
        prompts,
        provider,
      }),
    });
  },

  getRun(runId: number): Promise<RunDetailOut> {
    return request<RunDetailOut>(`/runs/${runId}`);
  },

  shareOfVoice(brandId: number, days = 30): Promise<ShareOfVoiceResponse> {
    return request<ShareOfVoiceResponse>(
      `/brands/${brandId}/share-of-voice?days=${days}`,
    );
  },
};

export { BASE_URL };
