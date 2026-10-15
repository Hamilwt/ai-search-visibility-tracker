"""Background run pipeline: prompts in, extracted rows out.

Runs after the 202 response is sent, with its own database session.
"""

import asyncio
import os
import uuid
from contextlib import suppress
from datetime import UTC, datetime

from sqlalchemy import select

from app.agents.extraction_graph import build_extraction_graph, run_extraction
from app.db import SessionLocal
from app.llm.extractor import Extractor
from app.llm.factory import get_provider
from app.llm.settings import get_settings
from app.llm.tracing import TracedProvider
from app.models.brand import Brand, Competitor, Prompt
from app.models.run import Citation, Mention, Response, Run
from app.observability.client import get_langfuse_client

# v2 reflection graph is the primary path; "0" restores the v1 Extractor.
USE_LANGGRAPH = os.getenv("USE_EXTRACTION_V2", "1") != "0"


async def execute_run(run_id: int, prompt_ids: list[int], provider_name: str) -> None:
    async with SessionLocal() as session:
        run = await session.get(Run, run_id)
        if run is None:
            return
        brand = await session.get(Brand, run.brand_id)
        if brand is None:
            run.status = "failed"
            run.error_message = f"Brand {run.brand_id} no longer exists"
            await session.commit()
            return

        run.status = "running"
        await session.commit()

        competitors = list(
            await session.scalars(
                select(Competitor.competitor_name).where(Competitor.brand_id == brand.id)
            )
        )
        prompts_by_id = {
            prompt.id: prompt
            for prompt in await session.scalars(select(Prompt).where(Prompt.id.in_(prompt_ids)))
        }

        provider = get_provider(provider_name)
        settings = get_settings()
        langfuse_client = get_langfuse_client(settings)
        trace_id = uuid.uuid4().hex if langfuse_client is not None else ""
        try:
            for prompt_id in prompt_ids:
                prompt = prompts_by_id.get(prompt_id)
                if prompt is None:
                    continue
                answer_traced = TracedProvider(
                    provider,
                    langfuse_client,
                    trace_id=trace_id,
                    run_id=run.id,
                    brand_id=brand.id,
                    prompt_id=prompt.id,
                    provider_name=provider_name,
                    call_kind="answer",
                )
                extraction_traced = TracedProvider(
                    provider,
                    langfuse_client,
                    trace_id=trace_id,
                    run_id=run.id,
                    brand_id=brand.id,
                    prompt_id=prompt.id,
                    provider_name=provider_name,
                    call_kind="extraction",
                )
                extractor = Extractor(extraction_traced)
                graph = build_extraction_graph(extraction_traced) if USE_LANGGRAPH else None
                generated = await answer_traced.generate(prompt.query_text)
                if graph is not None:
                    extracted = await run_extraction(graph, generated.text, brand.name, competitors)
                else:
                    extracted = await extractor.extract(
                        generated.text,
                        brand.name,
                        competitors,
                    )
                response = Response(
                    run_id=run.id,
                    prompt_id=prompt.id,
                    raw_response=generated.text,
                    model_name=generated.model_name,
                    latency_ms=generated.latency_ms,
                    status=extracted.status,
                )
                session.add(response)
                await session.flush()  # assigns response.id for children
                for mention in extracted.mentions:
                    session.add(
                        Mention(
                            response_id=response.id,
                            brand_name=mention.brand_name,
                            rank_position=mention.rank_position,
                            is_target_brand=mention.is_target_brand,
                            sentiment=mention.sentiment,
                        )
                    )
                for citation in extracted.citations:
                    session.add(
                        Citation(
                            response_id=response.id,
                            url=citation.url,
                            domain=citation.domain,
                        )
                    )
                await session.flush()  # partial progress survives a later crash
            run.status = "completed"
            run.completed_at = datetime.now(UTC)
        except Exception as exc:
            run.status = "failed"
            run.error_message = f"{type(exc).__name__}: {exc}"
        await session.commit()
        # Observability must never fail the run: flush in a thread so a slow
        # or unreachable Langfuse endpoint can't block the worker either.
        if langfuse_client is not None:
            with suppress(Exception):
                await asyncio.to_thread(langfuse_client.flush)
