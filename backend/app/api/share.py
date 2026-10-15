from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.schemas import ShareOfVoicePoint, ShareOfVoiceResponse
from app.db import get_session
from app.models.brand import Brand
from app.models.run import Mention, Response, Run

router = APIRouter(tags=["analytics"])


def _aggregate(rows: list[Mention], target: str) -> tuple[int, dict[str, int], float | None]:
    """Count target vs competitor mentions; average target rank.

    Competitor names group case-insensitively under first-seen spelling.
    """
    target_folded = target.casefold()
    target_count = 0
    target_ranks: list[int] = []
    competitors: dict[str, int] = {}
    seen_spelling: dict[str, str] = {}
    for row in rows:
        if row.brand_name.casefold() == target_folded:
            target_count += 1
            if row.rank_position is not None:
                target_ranks.append(row.rank_position)
            continue
        key = row.brand_name.casefold()
        seen_spelling.setdefault(key, row.brand_name)
        competitors[seen_spelling[key]] = competitors.get(seen_spelling[key], 0) + 1
    avg_rank = sum(target_ranks) / len(target_ranks) if target_ranks else None
    return target_count, competitors, avg_rank


@router.get("/brands/{brand_id}/share-of-voice", response_model=ShareOfVoiceResponse)
async def share_of_voice(
    brand_id: int,
    days: int = Query(default=30, gt=0, le=365),
    session: AsyncSession = Depends(get_session),
) -> ShareOfVoiceResponse:
    brand = await session.get(Brand, brand_id)
    if brand is None:
        raise HTTPException(status_code=404, detail=f"Brand {brand_id} not found")
    since = datetime.now(UTC) - timedelta(days=days)
    runs = list(
        await session.scalars(
            select(Run)
            .where(Run.brand_id == brand.id, Run.triggered_at >= since)
            .order_by(Run.triggered_at)
        )
    )
    points: list[ShareOfVoicePoint] = []
    for run in runs:
        rows = list(
            await session.scalars(
                select(Mention)
                .join(Response, Response.id == Mention.response_id)
                .where(Response.run_id == run.id)
            )
        )
        target_count, competitors, avg_rank = _aggregate(rows, brand.name)
        total = len(rows)
        points.append(
            ShareOfVoicePoint(
                run_id=run.id,
                triggered_at=run.triggered_at,
                target_mentions=target_count,
                competitor_mentions=competitors,
                total_mentions=total,
                share=round(target_count / total * 100, 2) if total else None,
                avg_rank_position=avg_rank,
            )
        )
    return ShareOfVoiceResponse(
        brand_id=brand.id,
        brand_name=brand.name,
        target_brand=brand.name,
        points=points,
    )
