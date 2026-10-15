"""Graph tests: scripted provider, no network, no database."""

import json

from app.agents.extraction_graph import (
    MAX_ATTEMPTS,
    build_extraction_graph,
    run_extraction,
)
from app.llm.base import BaseLLMProvider, LLMResult
from app.llm.extractor import Extractor


class ScriptedProvider(BaseLLMProvider):
    def __init__(self, texts: list[str]) -> None:
        self._texts = list(texts)
        self.prompts: list[str] = []

    async def generate(self, prompt: str) -> LLMResult:
        self.prompts.append(prompt)
        assert self._texts, "scripted provider ran out of texts"
        return LLMResult(text=self._texts.pop(0), model_name="m", latency_ms=1)


def valid_output() -> str:
    return json.dumps(
        {
            "mentions": [{"brand_name": "Acme", "rank_position": 1}],
            "citations": [],
        }
    )


async def run_graph(texts: list[str]) -> tuple:
    provider = ScriptedProvider(texts)
    graph = build_extraction_graph(provider)
    result = await run_extraction(graph, "Acme wins", "Acme", ["Umbrella"])
    return result, provider


async def test_valid_first_try() -> None:
    result, provider = await run_graph([valid_output()])
    assert result.status == "success"
    assert result.mentions[0].brand_name == "Acme"
    assert result.mentions[0].is_target_brand is True
    assert len(provider.prompts) == 1


async def test_invalid_then_fixed() -> None:
    result, provider = await run_graph(["not json", valid_output()])
    assert result.status == "success"
    assert len(provider.prompts) == 2
    # The repair prompt carries the validation error for the critique loop.
    assert "JSONDecodeError" in provider.prompts[1]


async def test_always_invalid_fails_after_budget() -> None:
    result, provider = await run_graph(["bad one", "bad two", "bad three"])
    assert result.status == "failed_extraction"
    assert len(provider.prompts) == MAX_ATTEMPTS == 3


async def test_schema_violation_triggers_fix() -> None:
    bad_shape = json.dumps({"mentions": "oops"})
    result, provider = await run_graph([bad_shape, valid_output()])
    assert result.status == "success"
    assert "ValidationError" in provider.prompts[1]


async def test_v1_v2_parity_on_success() -> None:
    texts = [valid_output()]
    v1 = await Extractor(ScriptedProvider(texts)).extract("Acme wins", "Acme", ["Umbrella"])
    graph_result, _ = await run_graph([valid_output()])
    assert v1 == graph_result


async def test_v1_v2_parity_on_failure() -> None:
    v1 = await Extractor(ScriptedProvider(["nope", "nah"])).extract("x", "Acme", [])
    graph_result, _ = await run_graph(["nope", "nah", "never"])
    assert v1.status == graph_result.status == "failed_extraction"
    assert v1.mentions == graph_result.mentions == []
