"""Background run pipeline: prompts in, extracted rows out.

Runs after the 202 response is sent, with its own database session.
"""

from datetime import UTC, datetime

from sqlalchemy import select

from app.db import SessionLocal
from app.llm.extractor import Extractor
from app.llm.factory import get_provider
from app.models.brand import Brand, Competitor, Prompt
from app.models.run import Citation, Mention, Response, Run


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
        extractor = Extractor(provider)
        try:
            for prompt_id in prompt_ids:
                prompt = prompts_by_id.get(prompt_id)
                if prompt is None:
                    continue
                generated = await provider.generate(prompt.query_text)
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
