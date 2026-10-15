"""Metric tests: pure functions, synthetic data, no database."""

import pytest

from app.eval.metrics import (
    ScoreCounts,
    parse_brand_labels,
    parse_url_labels,
    precision,
    rank_match_rate,
    recall,
    score_sets,
)


def test_parse_brand_labels() -> None:
    assert parse_brand_labels("Acme@1;Umbrella@2") == [("acme", 1), ("umbrella", 2)]
    assert parse_brand_labels("  Solo  ") == [("solo", None)]
    assert parse_brand_labels("A@1;;B@2;") == [("a", 1), ("b", 2)]
    assert parse_brand_labels("") == []


def test_parse_brand_labels_rejects_bad_ranks() -> None:
    with pytest.raises(ValueError):
        parse_brand_labels("Acme@zero")
    with pytest.raises(ValueError):
        parse_brand_labels("Acme@0")
    with pytest.raises(ValueError):
        parse_brand_labels("@2")


def test_parse_url_labels() -> None:
    assert parse_url_labels("HTTPS://X.com/A;;https://y.org/") == [
        "https://x.com/a",
        "https://y.org/",
    ]
    assert parse_url_labels("") == []


def test_score_sets() -> None:
    assert score_sets({"a", "b"}, {"b", "c"}) == ScoreCounts(tp=1, fp=1, fn=1)
    assert score_sets(set(), set()) == ScoreCounts()


def test_precision_and_recall() -> None:
    counts = ScoreCounts(tp=1, fp=1, fn=3)
    assert precision(counts) == 0.5
    assert recall(counts) == 0.25


def test_precision_recall_none_on_empty() -> None:
    # Divide-by-zero must yield None (printed as n/a), never crash or fake 1.0.
    assert precision(ScoreCounts()) is None
    assert recall(ScoreCounts()) is None
    assert rank_match_rate(0, 0) is None


def test_counts_accumulate_for_micro_average() -> None:
    total = ScoreCounts(tp=1, fp=1, fn=0) + ScoreCounts(tp=1, fp=0, fn=1)
    assert total == ScoreCounts(tp=2, fp=1, fn=1)
    assert precision(total) == pytest.approx(2 / 3)
    assert recall(total) == pytest.approx(2 / 3)


def test_rank_match_rate() -> None:
    assert rank_match_rate(3, 4) == 0.75
