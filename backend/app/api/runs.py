from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, Request
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.errors import RateLimited
from app.api.rate_limit import check_rate_limit, client_ip
from app.api.schemas import (
    CitationOut,
    MentionOut,
    ResponseOut,
    RunCreateRequest,
    RunCreateResponse,
    RunDetailOut,
    RunSummaryOut,
)
from app.db import get_session
from app.llm.settings import get_settings
from app.models.brand import Brand, Prompt
from app.models.run import Response, Run
from app.services.pipeline import execute_run

router = APIRouter(tags=["runs"])


@router.get("/runs", response_model=list[RunSummaryOut])
async def list_runs(
    brand_id: int | None = None,
    limit: int = Query(default=20, gt=0, le=100),
    session: AsyncSession = Depends(get_session),
) -> list[RunSummaryOut]:
    stmt = (
        select(Run, Brand.name, func.count(Response.id))
        .join(Brand, Brand.id == Run.brand_id)
        .outerjoin(Response, Response.run_id == Run.id)
        .group_by(Run.id, Brand.name)
        .order_by(Run.id.desc())
        .limit(limit)
    )
    if brand_id is not None:
        stmt = stmt.where(Run.brand_id == brand_id)
    return [
        RunSummaryOut(
            id=run.id,
            brand_id=run.brand_id,
            brand_name=brand_name,
            status=run.status,
            triggered_at=run.triggered_at,
            completed_at=run.completed_at,
            response_count=count,
        )
        for run, brand_name, count in await session.execute(stmt)
    ]


async def _upsert_prompts(session: AsyncSession, brand_id: int, queries: list[str]) -> list[int]:
    existing = {
        prompt.query_text: prompt
        for prompt in await session.scalars(
            select(Prompt).where(Prompt.brand_id == brand_id, Prompt.query_text.in_(queries))
        )
    }
    ordered_ids: list[int] = []
    for query in queries:
        prompt = existing.get(query)
        if prompt is None:
            prompt = Prompt(brand_id=brand_id, query_text=query)
            session.add(prompt)
            await session.flush()
            existing[query] = prompt
        elif not prompt.is_active:
            prompt.is_active = True
        ordered_ids.append(prompt.id)
    return ordered_ids


@router.post("/runs", response_model=RunCreateResponse, status_code=202)
async def create_run(
    request: RunCreateRequest,
    background_tasks: BackgroundTasks,
    http_request: Request,
    session: AsyncSession = Depends(get_session),
) -> RunCreateResponse:
    settings = get_settings()
    if len(request.prompts) > settings.max_prompts_per_run:
        raise RateLimited(
            "prompt_limit_exceeded",
            f"At most {settings.max_prompts_per_run} prompts per run",
        )
    retry_after = check_rate_limit(client_ip(http_request), settings.max_runs_per_hour_per_ip)
    if retry_after is not None:
        raise RateLimited(
            "rate_limited",
            f"At most {settings.max_runs_per_hour_per_ip} runs per hour",
            retry_after,
        )
    brand = await session.get(Brand, request.brand_id)
    if brand is None:
        raise HTTPException(status_code=404, detail=f"Brand {request.brand_id} not found")
    prompt_ids = await _upsert_prompts(session, brand.id, request.prompts)
    run = Run(brand_id=brand.id, status="pending")
    session.add(run)
    await session.flush()
    await session.commit()
    background_tasks.add_task(execute_run, run.id, prompt_ids, request.provider)
    return RunCreateResponse(run_id=run.id, status="pending")


@router.get("/runs/{run_id}", response_model=RunDetailOut)
async def get_run(run_id: int, session: AsyncSession = Depends(get_session)) -> RunDetailOut:
    run = await session.get(Run, run_id)
    if run is None:
        raise HTTPException(status_code=404, detail=f"Run {run_id} not found")
    responses = list(
        await session.scalars(
            select(Response)
            .where(Response.run_id == run.id)
            .options(selectinload(Response.mentions), selectinload(Response.citations))
            .order_by(Response.id)
        )
    )
    prompts = {
        prompt.id: prompt
        for prompt in await session.scalars(
            select(Prompt).where(Prompt.id.in_([response.prompt_id for response in responses]))
        )
    }
    return RunDetailOut(
        id=run.id,
        brand_id=run.brand_id,
        status=run.status,
        triggered_at=run.triggered_at,
        completed_at=run.completed_at,
        error_message=run.error_message,
        responses=[
            ResponseOut(
                id=response.id,
                prompt_id=response.prompt_id,
                query_text=prompts[response.prompt_id].query_text,
                raw_response=response.raw_response,
                model_name=response.model_name,
                latency_ms=response.latency_ms,
                status=response.status,
                mentions=[MentionOut.model_validate(m) for m in response.mentions],
                citations=[CitationOut.model_validate(c) for c in response.citations],
            )
            for response in responses
        ],
    )
