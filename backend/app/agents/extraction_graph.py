"""Reflection graph for extraction: extract -> validate -> fix (up to 2 fixes).

The same provider contract as v1; the same templates and parser as v1.
The graph only adds structure: an explicit validation node and a
conditional edge that loops back with the error attached.
"""

import json
from typing import TypedDict

from langgraph.graph import END, StateGraph
from pydantic import ValidationError

from app.llm.base import BaseLLMProvider
from app.llm.extractor import (
    EXTRACTION_TEMPLATE,
    REPAIR_TEMPLATE,
    _parse,
)
from app.llm.schemas import ExtractionResult

MAX_ATTEMPTS = 3  # initial extraction + 2 fixes


class ExtractionState(TypedDict):
    answer: str
    target: str
    competitors: list[str]
    raw_attempt: str
    attempts: int
    validation_error: str | None
    result: ExtractionResult | None


def build_extraction_graph(provider: BaseLLMProvider):
    """Compile the reflection graph around an injected provider."""

    async def extract(state: ExtractionState) -> dict:
        schema = ExtractionResult.model_json_schema()
        prompt = EXTRACTION_TEMPLATE.format(
            target=state["target"],
            competitors=", ".join(state["competitors"]) or "(none listed)",
            answer=state["answer"],
            schema=schema,
        )
        raw = (await provider.generate(prompt)).text
        return {"raw_attempt": raw, "attempts": state["attempts"] + 1}

    async def validate(state: ExtractionState) -> dict:
        try:
            return {
                "result": _parse(state["raw_attempt"], state["target"]),
                "validation_error": None,
            }
        except (json.JSONDecodeError, ValidationError) as exc:
            return {
                "result": None,
                "validation_error": f"{type(exc).__name__}: {exc}",
            }

    async def fix(state: ExtractionState) -> dict:
        schema = ExtractionResult.model_json_schema()
        prompt = REPAIR_TEMPLATE.format(
            error=state["validation_error"],
            raw=state["raw_attempt"],
            schema=schema,
        )
        raw = (await provider.generate(prompt)).text
        return {
            "raw_attempt": raw,
            "attempts": state["attempts"] + 1,
            "validation_error": None,
        }

    def route(state: ExtractionState) -> str:
        if state["result"] is not None or state["attempts"] >= MAX_ATTEMPTS:
            return END
        return "fix"

    graph = StateGraph(ExtractionState)
    graph.add_node("extract", extract)
    graph.add_node("validate", validate)
    graph.add_node("fix", fix)
    graph.set_entry_point("extract")
    graph.add_edge("extract", "validate")
    graph.add_conditional_edges("validate", route)
    graph.add_edge("fix", "validate")
    return graph.compile()


async def run_extraction(
    graph, answer: str, target: str, competitors: list[str]
) -> ExtractionResult:
    """Execute the graph; exhausted fixes degrade to failed_extraction."""
    final = await graph.ainvoke(
        {
            "answer": answer,
            "target": target,
            "competitors": competitors,
            "raw_attempt": "",
            "attempts": 0,
            "validation_error": None,
            "result": None,
        }
    )
    if final["result"] is not None:
        return final["result"]
    return ExtractionResult(status="failed_extraction")
