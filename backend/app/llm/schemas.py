from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

Sentiment = Literal["positive", "neutral", "negative"]
ExtractionStatus = Literal["success", "failed_extraction"]


class MentionItem(BaseModel):
    """One brand mentioned in an answer."""

    model_config = ConfigDict(extra="forbid")

    brand_name: str = Field(min_length=1)
    rank_position: int | None = Field(default=None, ge=1)
    sentiment: Sentiment | None = None
    # Allowed in model output but ALWAYS overwritten server-side by Extractor.
    is_target_brand: bool = False


class CitedUrl(BaseModel):
    """One URL cited in an answer."""

    model_config = ConfigDict(extra="forbid")

    url: str = Field(min_length=1)
    domain: str = Field(min_length=1)


class ExtractionResult(BaseModel):
    """Validated extraction output. ``failed_extraction`` means the model
    never produced parseable JSON (see extractor); lists are then empty.
    """

    model_config = ConfigDict(extra="forbid")

    mentions: list[MentionItem] = Field(default_factory=list)
    citations: list[CitedUrl] = Field(default_factory=list)
    status: ExtractionStatus = "success"
