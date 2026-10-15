/** Mirrors of the backend Pydantic schemas (backend/app/api/schemas.py).
 *  Kept in sync by hand; the compiler catches drift at usage sites.
 */

export type ProviderName = "gemini" | "openai";

export interface BrandOut {
  id: number;
  name: string;
}

export interface RunSummaryOut {
  id: number;
  brand_id: number;
  brand_name: string;
  status: string;
  triggered_at: string;
  completed_at: string | null;
  response_count: number;
}

export interface RunCreateResponse {
  run_id: number;
  status: string;
}

export interface MentionOut {
  brand_name: string;
  rank_position: number | null;
  is_target_brand: boolean;
  sentiment: string | null;
}

export interface CitationOut {
  url: string;
  domain: string;
}

export interface ResponseOut {
  id: number;
  prompt_id: number;
  query_text: string;
  raw_response: string;
  model_name: string;
  latency_ms: number | null;
  status: string;
  mentions: MentionOut[];
  citations: CitationOut[];
}

export interface RunDetailOut {
  id: number;
  brand_id: number;
  status: string;
  triggered_at: string;
  completed_at: string | null;
  error_message: string | null;
  responses: ResponseOut[];
}

export interface ShareOfVoicePoint {
  run_id: number;
  triggered_at: string;
  target_mentions: number;
  competitor_mentions: Record<string, number>;
  total_mentions: number;
  /** 0-100 percentage; null when the run has zero mentions. */
  share: number | null;
  avg_rank_position: number | null;
}

export interface ShareOfVoiceResponse {
  brand_id: number;
  brand_name: string;
  target_brand: string;
  points: ShareOfVoicePoint[];
}
