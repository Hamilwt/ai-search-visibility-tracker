"""Pure evaluation math and label parsing. No DB, no I/O, no network.

Label syntax (human-written in the CSV):
- brands: ``Acme@1;Umbrella@2`` (rank after ``@`` is optional)
- urls: ``https://example.com/a;https://example.org/b``
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class ScoreCounts:
    tp: int = 0
    fp: int = 0
    fn: int = 0

    def __add__(self, other: "ScoreCounts") -> "ScoreCounts":
        return ScoreCounts(
            tp=self.tp + other.tp,
            fp=self.fp + other.fp,
            fn=self.fn + other.fn,
        )


def parse_brand_labels(cell: str) -> list[tuple[str, int | None]]:
    """Parse ``Name@rank;...`` into (casefolded name, rank-or-None) pairs."""
    items: list[tuple[str, int | None]] = []
    for chunk in cell.split(";"):
        chunk = chunk.strip()
        if not chunk:
            continue
        name, _, rank_text = chunk.partition("@")
        name = name.strip().casefold()
        if not name:
            raise ValueError(f"Empty brand name in label cell: {cell!r}")
        rank: int | None = None
        if rank_text.strip():
            try:
                rank = int(rank_text.strip())
            except ValueError:
                raise ValueError(f"Bad rank in label cell: {cell!r}") from None
            if rank < 1:
                raise ValueError(f"Rank must be >= 1 in label cell: {cell!r}")
        items.append((name, rank))
    return items


def parse_url_labels(cell: str) -> list[str]:
    """Parse ``url;...`` into lowercased URLs."""
    urls = [chunk.strip().lower() for chunk in cell.split(";")]
    return [url for url in urls if url]


def score_sets(predicted: set[str], expected: set[str]) -> ScoreCounts:
    """Set comparison. Callers pass already-normalized strings."""
    return ScoreCounts(
        tp=len(predicted & expected),
        fp=len(predicted - expected),
        fn=len(expected - predicted),
    )


def precision(counts: ScoreCounts) -> float | None:
    denom = counts.tp + counts.fp
    return counts.tp / denom if denom else None


def recall(counts: ScoreCounts) -> float | None:
    denom = counts.tp + counts.fn
    return counts.tp / denom if denom else None


def rank_match_rate(matched: int, total_tp: int) -> float | None:
    """Fraction of true-positive brands stored at the labeled rank."""
    return matched / total_tp if total_tp else None
