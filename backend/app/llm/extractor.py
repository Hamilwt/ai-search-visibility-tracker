"""Turn a raw model answer into validated extraction JSON.

One repair attempt on malformed output, then a defined
``failed_extraction`` result instead of an exception.
"""

import json
from urllib.parse import urlparse

from pydantic import ValidationError

from app.llm.base import BaseLLMProvider
from app.llm.schemas import CitedUrl, ExtractionResult, MentionItem


def normalize_domain(url: str) -> str | None:
    """Lowercased hostname with a leading ``www.`` stripped.

    Returns None when no hostname can be parsed (caller drops the citation).
    """
    host = (urlparse(url).hostname or "").lower()
    if not host:
        return None
    if host.startswith("www."):
        host = host[4:]
    return host


def strip_fences(text: str) -> str:
    """Remove a wrapping ```json ... ``` fence if the model added one."""
    cleaned = text.strip()
    if cleaned.startswith("```") and cleaned.endswith("```"):
        lines = cleaned.splitlines()
        body = lines[1:-1] if len(lines) > 2 else []
        cleaned = "\n".join(body).strip()
        if cleaned.startswith("json"):
            cleaned = cleaned[4:].strip()
    return cleaned


def _parse(raw: str, target: str) -> ExtractionResult:
    data = json.loads(strip_fences(raw))
    result = ExtractionResult.model_validate(data)
    mentions = [
        MentionItem(
            brand_name=m.brand_name,
            rank_position=m.rank_position,
            sentiment=m.sentiment,
        )
        for m in result.mentions
    ]
    citations: list[CitedUrl] = []
    for citation in result.citations:
        domain = normalize_domain(citation.url)
        if domain is None:
            continue
        citations.append(CitedUrl(url=citation.url, domain=domain))
    # Decided here, never trusted from the model.
    for mention in mentions:
        mention.is_target_brand = mention.brand_name.casefold() == target.casefold()
    return ExtractionResult(mentions=mentions, citations=citations, status="success")


EXTRACTION_TEMPLATE = """\
You analyze an answer about competing brands and extract structured data.

Target brand: {target}
Competitor brands: {competitors}

Answer to analyze:
\"\"\"
{answer}
\"\"\"

Output JSON ONLY (no markdown fences, no commentary) matching this schema.
List every brand from the target/competitor lists that the answer mentions,
in the order they are ranked or recommended (rank_position starts at 1).
Include every URL the answer cites.
Schema:
{schema}
"""

REPAIR_TEMPLATE = """\
Your previous output was not valid JSON for the required schema.
Error: {error}

Previous output:
\"\"\"
{raw}
\"\"\"

Fix it now. Output JSON ONLY matching this schema:
{schema}
"""


class Extractor:
    """Runs extraction over a provider: answer text in, validated JSON out."""

    def __init__(self, provider: BaseLLMProvider) -> None:
        self._provider = provider

    async def extract(self, answer: str, target: str, competitors: list[str]) -> ExtractionResult:
        schema = ExtractionResult.model_json_schema()
        prompt = EXTRACTION_TEMPLATE.format(
            target=target,
            competitors=", ".join(competitors) or "(none listed)",
            answer=answer,
            schema=schema,
        )
        raw = (await self._provider.generate(prompt)).text
        try:
            return _parse(raw, target)
        except (json.JSONDecodeError, ValidationError) as first_error:
            repair = REPAIR_TEMPLATE.format(error=first_error, raw=raw, schema=schema)
            repaired = (await self._provider.generate(repair)).text
            try:
                return _parse(repaired, target)
            except (json.JSONDecodeError, ValidationError):
                return ExtractionResult(status="failed_extraction")
