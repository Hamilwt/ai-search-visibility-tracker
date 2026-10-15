from datetime import datetime

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Text,
    func,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models import Base


class Brand(Base):
    __tablename__ = "brands"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    __table_args__ = (
        CheckConstraint("char_length(name) >= 1", name="ck_brands_name_nonempty"),
        Index("ix_brands_name_lower", func.lower(name), unique=True),
    )

    competitors: Mapped[list["Competitor"]] = relationship(
        back_populates="brand", passive_deletes=True
    )
    prompts: Mapped[list["Prompt"]] = relationship(back_populates="brand", passive_deletes=True)


class Competitor(Base):
    __tablename__ = "competitors"

    id: Mapped[int] = mapped_column(primary_key=True)
    brand_id: Mapped[int] = mapped_column(
        ForeignKey("brands.id", ondelete="CASCADE"), nullable=False
    )
    competitor_name: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    __table_args__ = (
        CheckConstraint(
            "char_length(competitor_name) BETWEEN 1 AND 200",
            name="ck_competitors_name_length",
        ),
        Index(
            "ix_competitors_brand_lower_name",
            brand_id,
            func.lower(competitor_name),
            unique=True,
        ),
    )

    brand: Mapped["Brand"] = relationship(back_populates="competitors")


class Prompt(Base):
    __tablename__ = "prompts"

    id: Mapped[int] = mapped_column(primary_key=True)
    brand_id: Mapped[int] = mapped_column(
        ForeignKey("brands.id", ondelete="CASCADE"), nullable=False
    )
    query_text: Mapped[str] = mapped_column(Text, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="true")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    __table_args__ = (
        CheckConstraint(
            "char_length(query_text) BETWEEN 1 AND 2000",
            name="ck_prompts_query_length",
        ),
        Index(
            "ix_prompts_brand_query",
            brand_id,
            query_text,
            unique=True,
        ),
        Index(
            "ix_prompts_active_brand",
            brand_id,
            postgresql_where=text("is_active"),
        ),
    )

    brand: Mapped["Brand"] = relationship(back_populates="prompts")
