"""Extractor unit tests. The provider is scripted; no network calls are made."""

import json

from app.llm.base import BaseLLMProvider, LLMResult
from app.llm.extractor import Extractor


class ScriptedProvider(BaseLLMProvider):
    """Replays canned texts, recording every prompt it receives."""

    def __init__(self, texts: list[str]) -> None:
        self._texts = texts
        self.prompts: list[str] = []

    async def generate(self, prompt: str) -> LLMResult:
        self.prompts.append(prompt)
        return LLMResult(text=self._texts.pop(0), model_name="t", latency_ms=1)


def valid_output() -> str:
    return json.dumps(
        {
            "mentions": [
                {
                    "brand_name": "Acme",
                    "rank_position": 1,
                    "sentiment": "positive",
                    "is_target_brand": False,  # model is wrong; server decides
                },
                {"brand_name": "Umbrella", "rank_position": 2},
            ],
            "citations": [
                {"url": "https://WWW.example.com/a", "domain": "ignored"},
                {"url": "not a url", "domain": "ignored"},
            ],
            "status": "success",
        }
    )


async def test_extract_success_computes_target_and_domain() -> None:
    extractor = Extractor(ScriptedProvider([valid_output()]))
    result = await extractor.extract("Acme rocks", "Acme", ["Umbrella"])
    assert result.status == "success"
    assert [(m.brand_name, m.is_target_brand) for m in result.mentions] == [
        ("Acme", True),
        ("Umbrella", False),
    ]
    # www stripped, lowercased, model-supplied domain overwritten, bad URL dropped.
    assert [(c.url, c.domain) for c in result.citations] == [
        ("https://WWW.example.com/a", "example.com")
    ]


async def test_extract_strips_markdown_fences() -> None:
    extractor = Extractor(ScriptedProvider(["```json\n" + valid_output() + "\n```"]))
    result = await extractor.extract("answer", "Acme", ["Umbrella"])
    assert result.status == "success"
    assert len(result.mentions) == 2


async def test_extract_repairs_malformed_json_once() -> None:
    provider = ScriptedProvider(["definitely not json", valid_output()])
    result = await Extractor(provider).extract("answer", "Acme", ["Umbrella"])
    assert result.status == "success"
    assert len(provider.prompts) == 2
    assert "not valid JSON" in provider.prompts[1]


async def test_extract_repairs_schema_violation() -> None:
    # Valid JSON but wrong shape: must also trigger the repair path
    # (pydantic.ValidationError, not just JSONDecodeError).
    bad_shape = json.dumps({"mentions": "oops", "citations": []})
    provider = ScriptedProvider([bad_shape, valid_output()])
    result = await Extractor(provider).extract("answer", "Acme", ["Umbrella"])
    assert result.status == "success"
    assert len(provider.prompts) == 2


async def test_extract_failed_after_two_bad_outputs() -> None:
    provider = ScriptedProvider(["garbage one", "garbage two"])
    result = await Extractor(provider).extract("answer", "Acme", ["Umbrella"])
    assert result.status == "failed_extraction"
    assert result.mentions == []
    assert result.citations == []
    assert len(provider.prompts) == 2
