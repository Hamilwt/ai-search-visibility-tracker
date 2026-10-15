"""Score hand-labeled CSVs against stored extraction output.

Run from the backend directory:
    python scripts/evaluate.py --labels labels/labeled_30.csv

Prints a markdown block ready to paste into docs/METRICS.md.
"""

import argparse
import asyncio
import csv
import os
import sys
from datetime import date

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import select  # noqa: E402
from sqlalchemy.ext.asyncio import create_async_engine  # noqa: E402

from app.db import DEFAULT_DATABASE_URL  # noqa: E402
from app.eval.metrics import (  # noqa: E402
    ScoreCounts,
    parse_brand_labels,
    parse_url_labels,
    precision,
    rank_match_rate,
    recall,
    score_sets,
)
from app.models.run import Citation, Mention, Response  # noqa: E402

REQUIRED_COLUMNS = {
    "id",
    "run_id",
    "prompt_id",
    "raw_response",
    "expected_brands",
    "expected_urls",
}


def fmt(value: float | None) -> str:
    return f"{value:.4f}" if value is not None else "n/a"


async def evaluate(labels_path: str) -> str:
    with open(labels_path, newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    missing = REQUIRED_COLUMNS - set(rows[0].keys() if rows else [])
    if missing:
        sys.exit(f"Missing columns in {labels_path}: {sorted(missing)}")

    url = os.getenv("DATABASE_URL", DEFAULT_DATABASE_URL)
    engine = create_async_engine(url)
    brand_total = ScoreCounts()
    url_total = ScoreCounts()
    rank_matched = 0
    rank_total = 0
    scored = 0
    skipped = 0
    try:
        async with engine.connect() as conn:
            for row in rows:
                response_id = (
                    await conn.execute(
                        select(Response.id).where(
                            Response.run_id == int(row["run_id"]),
                            Response.prompt_id == int(row["prompt_id"]),
                        )
                    )
                ).scalar_one_or_none()
                if response_id is None:
                    print(
                        f"Warning: no stored response for "
                        f"run {row['run_id']} prompt {row['prompt_id']}; skipping",
                        file=sys.stderr,
                    )
                    skipped += 1
                    continue
                mentions = (
                    await conn.execute(
                        select(Mention.brand_name, Mention.rank_position).where(
                            Mention.response_id == response_id
                        )
                    )
                ).all()
                citations = (
                    await conn.execute(
                        select(Citation.url).where(Citation.response_id == response_id)
                    )
                ).all()
                expected_brands = dict(parse_brand_labels(row["expected_brands"]))
                predicted_brands = {name.casefold(): rank for name, rank in mentions}
                brand_counts = score_sets(set(predicted_brands), set(expected_brands))
                brand_total += brand_counts
                for name in set(predicted_brands) & set(expected_brands):
                    if expected_brands[name] is not None:
                        rank_total += 1
                        if predicted_brands[name] == expected_brands[name]:
                            rank_matched += 1
                url_total += score_sets(
                    {url.lower() for (url,) in citations},
                    set(parse_url_labels(row["expected_urls"])),
                )
                scored += 1
    finally:
        await engine.dispose()

    return (
        f"## Evaluation ({date.today().isoformat()})\n"
        f"- Command: `python scripts/evaluate.py --labels {labels_path}`\n"
        f"- Rows scored: {scored} (skipped: {skipped})\n"
        f"- Brand mentions: TP={brand_total.tp} FP={brand_total.fp} "
        f"FN={brand_total.fn}\n"
        f"- Brand precision: {fmt(precision(brand_total))}\n"
        f"- Brand recall: {fmt(recall(brand_total))}\n"
        f"- URLs: TP={url_total.tp} FP={url_total.fp} FN={url_total.fn}\n"
        f"- URL precision: {fmt(precision(url_total))}\n"
        f"- URL recall: {fmt(recall(url_total))}\n"
        f"- Rank-match rate: {fmt(rank_match_rate(rank_matched, rank_total))}\n"
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Score hand-labeled extraction CSVs.")
    parser.add_argument("--labels", required=True)
    args = parser.parse_args()
    print(asyncio.run(evaluate(args.labels)), end="")


if __name__ == "__main__":
    main()
