"""Export stored responses to a CSV template for hand-labeling.

Run from the backend directory:
    python scripts/export_for_labels.py [--limit 30] [--out labels_template.csv]

Label syntax for the two blank columns:
    expected_brands:  Acme@1;Umbrella@2      (rank after @ is optional)
    expected_urls:    https://example.com/a;https://example.org/b
"""

import argparse
import asyncio
import csv
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import select  # noqa: E402
from sqlalchemy.ext.asyncio import create_async_engine  # noqa: E402

from app.db import DEFAULT_DATABASE_URL  # noqa: E402
from app.models.brand import Prompt  # noqa: E402
from app.models.run import Response  # noqa: E402

COLUMNS = [
    "id",
    "run_id",
    "prompt_id",
    "query_text",
    "raw_response",
    "expected_brands",
    "expected_urls",
]


async def export(limit: int, out_path: str) -> int:
    url = os.getenv("DATABASE_URL", DEFAULT_DATABASE_URL)
    engine = create_async_engine(url)
    try:
        async with engine.connect() as conn:
            rows = (
                await conn.execute(
                    select(Response, Prompt.query_text)
                    .join(Prompt, Prompt.id == Response.prompt_id)
                    .where(Response.status == "success")
                    .order_by(Response.id.desc())
                    .limit(limit)
                )
            ).all()
    finally:
        await engine.dispose()
    with open(out_path, "w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=COLUMNS)
        writer.writeheader()
        for response, query_text in rows:
            writer.writerow(
                {
                    "id": response.id,
                    "run_id": response.run_id,
                    "prompt_id": response.prompt_id,
                    "query_text": query_text,
                    "raw_response": response.raw_response,
                    "expected_brands": "",
                    "expected_urls": "",
                }
            )
    return len(rows)


def main() -> None:
    parser = argparse.ArgumentParser(description="Export responses for hand-labeling.")
    parser.add_argument("--limit", type=int, default=30)
    parser.add_argument("--out", default="labels_template.csv")
    args = parser.parse_args()
    count = asyncio.run(export(args.limit, args.out))
    print(f"Exported {count} responses to {args.out}")


if __name__ == "__main__":
    main()
