from datetime import datetime

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    ForeignKey,
    Index,
    Integer,
    Text,
    func,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models import Base
from app.models.brand import Prompt


class Run(Base):
    __tablename__ = "runs"

    id: Mapped[int] = mapped_column(primary_key=True)
    brand_id: Mapped[int] = mapped_column(
        ForeignKey("brands.id", ondelete="CASCADE"), nullable=False
    )
    status: Mapped[str] = mapped_column(nullable=False, server_default="pending")
    triggered_at: Mapped[datetime] = mapped_column(nullable=False, server_default=func.now())
    completed_at: Mapped[datetime | None] = mapped_column(nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)

    __table_args__ = (
        CheckConstraint(
            "status IN ('pending', 'running', 'completed', 'failed')",
            name="ck_runs_status",
        ),
        CheckConstraint(
            "completed_at IS NULL OR completed_at >= triggered_at",
            name="ck_runs_completed_after_triggered",
        ),
        Index("ix_runs_brand_triggered", brand_id, triggered_at.desc()),
        Index(
            "ix_runs_open_status",
            "status",
            postgresql_where=text("status IN ('pending', 'running')"),
        ),
    )

    responses: Mapped[list["Response"]] = relationship(back_populates="run", passive_deletes=True)


class Response(Base):
    __tablename__ = "responses"

    id: Mapped[int] = mapped_column(primary_key=True)
    run_id: Mapped[int] = mapped_column(ForeignKey("runs.id", ondelete="CASCADE"), nullable=False)
    prompt_id: Mapped[int] = mapped_column(
        ForeignKey("prompts.id", ondelete="RESTRICT"), nullable=False
    )
    raw_response: Mapped[str] = mapped_column(Text, nullable=False)
    model_name: Mapped[str] = mapped_column(nullable=False)
    latency_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    status: Mapped[str] = mapped_column(nullable=False)

    __table_args__ = (
        CheckConstraint(
            "status IN ('success', 'failed_extraction', 'error')",
            name="ck_responses_status",
        ),
        CheckConstraint(
            "latency_ms IS NULL OR latency_ms >= 0",
            name="ck_responses_latency_nonnegative",
        ),
        Index("ix_responses_run_prompt", run_id, prompt_id, unique=True),
        Index("ix_responses_run_status", run_id, "status"),
    )

    run: Mapped["Run"] = relationship(back_populates="responses")
    prompt: Mapped["Prompt"] = relationship()
    mentions: Mapped[list["Mention"]] = relationship(
        back_populates="response", passive_deletes=True
    )
    citations: Mapped[list["Citation"]] = relationship(
        back_populates="response", passive_deletes=True
    )


class Mention(Base):
    __tablename__ = "mentions"

    id: Mapped[int] = mapped_column(primary_key=True)
    response_id: Mapped[int] = mapped_column(
        ForeignKey("responses.id", ondelete="CASCADE"), nullable=False
    )
    brand_name: Mapped[str] = mapped_column(Text, nullable=False)
    rank_position: Mapped[int | None] = mapped_column(Integer, nullable=True)
    is_target_brand: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="false")
    sentiment: Mapped[str | None] = mapped_column(nullable=True)

    __table_args__ = (
        CheckConstraint(
            "rank_position IS NULL OR rank_position >= 1",
            name="ck_mentions_rank_positive",
        ),
        CheckConstraint(
            "sentiment IS NULL OR sentiment IN ('positive', 'neutral', 'negative')",
            name="ck_mentions_sentiment",
        ),
        Index("ix_mentions_response_brand", response_id, brand_name, unique=True),
        Index("ix_mentions_brand", brand_name),
        Index("ix_mentions_response_rank", response_id, rank_position),
    )

    response: Mapped["Response"] = relationship(back_populates="mentions")


class Citation(Base):
    __tablename__ = "citations"

    id: Mapped[int] = mapped_column(primary_key=True)
    response_id: Mapped[int] = mapped_column(
        ForeignKey("responses.id", ondelete="CASCADE"), nullable=False
    )
    url: Mapped[str] = mapped_column(Text, nullable=False)
    domain: Mapped[str] = mapped_column(nullable=False)

    __table_args__ = (
        CheckConstraint("char_length(url) >= 1", name="ck_citations_url_nonempty"),
        Index("ix_citations_response_url", response_id, url, unique=True),
        Index("ix_citations_domain", domain),
    )

    response: Mapped["Response"] = relationship(back_populates="citations")
