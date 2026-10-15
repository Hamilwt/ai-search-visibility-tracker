"""create initial schema

Revision ID: 0001
Revises:
Create Date: 2026-10-15

Creates all seven tables: brands, competitors, prompts, runs,
responses, mentions, citations.
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "brands",
        sa.Column("id", sa.Integer(), sa.Identity(), primary_key=True),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.CheckConstraint("char_length(name) >= 1", name="ck_brands_name_nonempty"),
    )
    op.create_index("ix_brands_name_lower", "brands", [sa.text("lower(name)")], unique=True)

    op.create_table(
        "competitors",
        sa.Column("id", sa.Integer(), sa.Identity(), primary_key=True),
        sa.Column(
            "brand_id",
            sa.Integer(),
            sa.ForeignKey("brands.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("competitor_name", sa.Text(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.CheckConstraint(
            "char_length(competitor_name) BETWEEN 1 AND 200",
            name="ck_competitors_name_length",
        ),
    )
    op.create_index(
        "ix_competitors_brand_lower_name",
        "competitors",
        ["brand_id", sa.text("lower(competitor_name)")],
        unique=True,
    )

    op.create_table(
        "prompts",
        sa.Column("id", sa.Integer(), sa.Identity(), primary_key=True),
        sa.Column(
            "brand_id",
            sa.Integer(),
            sa.ForeignKey("brands.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("query_text", sa.Text(), nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default="true", nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.CheckConstraint(
            "char_length(query_text) BETWEEN 1 AND 2000",
            name="ck_prompts_query_length",
        ),
        sa.UniqueConstraint("brand_id", "query_text", name="ix_prompts_brand_query"),
    )
    op.create_index(
        "ix_prompts_active_brand",
        "prompts",
        ["brand_id"],
        postgresql_where=sa.text("is_active"),
    )

    op.create_table(
        "runs",
        sa.Column("id", sa.Integer(), sa.Identity(), primary_key=True),
        sa.Column(
            "brand_id",
            sa.Integer(),
            sa.ForeignKey("brands.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("status", sa.Text(), server_default="pending", nullable=False),
        sa.Column(
            "triggered_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.CheckConstraint(
            "status IN ('pending', 'running', 'completed', 'failed')",
            name="ck_runs_status",
        ),
        sa.CheckConstraint(
            "completed_at IS NULL OR completed_at >= triggered_at",
            name="ck_runs_completed_after_triggered",
        ),
    )
    op.create_index(
        "ix_runs_brand_triggered",
        "runs",
        ["brand_id", sa.text("triggered_at DESC")],
    )
    op.create_index(
        "ix_runs_open_status",
        "runs",
        ["status"],
        postgresql_where=sa.text("status IN ('pending', 'running')"),
    )

    op.create_table(
        "responses",
        sa.Column("id", sa.Integer(), sa.Identity(), primary_key=True),
        sa.Column(
            "run_id",
            sa.Integer(),
            sa.ForeignKey("runs.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "prompt_id",
            sa.Integer(),
            sa.ForeignKey("prompts.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("raw_response", sa.Text(), nullable=False),
        sa.Column("model_name", sa.Text(), nullable=False),
        sa.Column("latency_ms", sa.Integer(), nullable=True),
        sa.Column("status", sa.Text(), nullable=False),
        sa.CheckConstraint(
            "status IN ('success', 'failed_extraction', 'error')",
            name="ck_responses_status",
        ),
        sa.CheckConstraint(
            "latency_ms IS NULL OR latency_ms >= 0",
            name="ck_responses_latency_nonnegative",
        ),
    )
    op.create_index("ix_responses_run_prompt", "responses", ["run_id", "prompt_id"], unique=True)
    op.create_index("ix_responses_run_status", "responses", ["run_id", "status"])

    op.create_table(
        "mentions",
        sa.Column("id", sa.Integer(), sa.Identity(), primary_key=True),
        sa.Column(
            "response_id",
            sa.Integer(),
            sa.ForeignKey("responses.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("brand_name", sa.Text(), nullable=False),
        sa.Column("rank_position", sa.Integer(), nullable=True),
        sa.Column(
            "is_target_brand",
            sa.Boolean(),
            server_default="false",
            nullable=False,
        ),
        sa.Column("sentiment", sa.Text(), nullable=True),
        sa.CheckConstraint(
            "rank_position IS NULL OR rank_position >= 1",
            name="ck_mentions_rank_positive",
        ),
        sa.CheckConstraint(
            "sentiment IS NULL OR sentiment IN ('positive', 'neutral', 'negative')",
            name="ck_mentions_sentiment",
        ),
    )
    op.create_index(
        "ix_mentions_response_brand",
        "mentions",
        ["response_id", "brand_name"],
        unique=True,
    )
    op.create_index("ix_mentions_brand", "mentions", ["brand_name"])
    op.create_index("ix_mentions_response_rank", "mentions", ["response_id", "rank_position"])

    op.create_table(
        "citations",
        sa.Column("id", sa.Integer(), sa.Identity(), primary_key=True),
        sa.Column(
            "response_id",
            sa.Integer(),
            sa.ForeignKey("responses.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("url", sa.Text(), nullable=False),
        sa.Column("domain", sa.Text(), nullable=False),
        sa.CheckConstraint("char_length(url) >= 1", name="ck_citations_url_nonempty"),
    )
    op.create_index(
        "ix_citations_response_url",
        "citations",
        ["response_id", "url"],
        unique=True,
    )
    op.create_index("ix_citations_domain", "citations", ["domain"])


def downgrade() -> None:
    op.drop_table("citations")
    op.drop_table("mentions")
    op.drop_table("responses")
    op.drop_table("runs")
    op.drop_table("prompts")
    op.drop_table("competitors")
    op.drop_table("brands")
