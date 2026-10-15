from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

ProviderName = Literal["gemini", "openai"]
RunStatus = Literal["pending", "running", "completed", "failed"]

MAX_PROMPTS_PER_RUN = 50
MAX_PROMPT_LENGTH = 2000


class RunCreateRequest(BaseModel):
    brand_id: int = Field(gt=0)
    prompts: list[str] = Field(min_length=1, max_length=MAX_PROMPTS_PER_RUN)
    provider: ProviderName = "gemini"

    @field_validator("prompts")
    @classmethod
    def prompts_must_be_nonblank(cls, value: list[str]) -> list[str]:
        cleaned = [item.strip() for item in value]
        for item in cleaned:
            if not item:
                raise ValueError("prompts must not contain blank strings")
            if len(item) > MAX_PROMPT_LENGTH:
                raise ValueError(f"each prompt must be at most {MAX_PROMPT_LENGTH} characters")
        return cleaned


class RunCreateResponse(BaseModel):
    run_id: int
    status: RunStatus


class BrandOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str


class RunSummaryOut(BaseModel):
    id: int
    brand_id: int
    brand_name: str
    status: str
    triggered_at: datetime
    completed_at: datetime | None
    response_count: int


class MentionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    brand_name: str
    rank_position: int | None
    is_target_brand: bool
    sentiment: str | None


class CitationOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    url: str
    domain: str


class ResponseOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    prompt_id: int
    query_text: str
    raw_response: str
    model_name: str
    latency_ms: int | None
    status: str
    mentions: list[MentionOut] = Field(default_factory=list)
    citations: list[CitationOut] = Field(default_factory=list)


class RunDetailOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    brand_id: int
    status: str
    triggered_at: datetime
    completed_at: datetime | None
    error_message: str | None
    responses: list[ResponseOut] = Field(default_factory=list)


class ShareOfVoicePoint(BaseModel):
    run_id: int
    triggered_at: datetime
    target_mentions: int
    competitor_mentions: dict[str, int]
    total_mentions: int
    # 0-100 percentage. None when nothing was mentioned (never a fake 0%).
    share: float | None
    avg_rank_position: float | None


class ShareOfVoiceResponse(BaseModel):
    brand_id: int
    brand_name: str
    target_brand: str
    points: list[ShareOfVoicePoint] = Field(default_factory=list)


class ErrorDetail(BaseModel):
    code: str
    message: str
    details: dict | None = None


class ErrorResponse(BaseModel):
    error: ErrorDetail
