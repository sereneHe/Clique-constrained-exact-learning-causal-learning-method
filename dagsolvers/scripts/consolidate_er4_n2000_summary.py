#!/usr/bin/env python3
"""Consolidate ER-4-0, n=2000 records from the archived 96-column summaries."""

from __future__ import annotations

import csv
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SOURCE_DIR = ROOT / "results" / "总结table-96列" / "n2000"
OUTPUT = ROOT / "results" / "summary" / "summary_experiments_er-4-0_n2000.csv"
KEY_COLUMNS = (
    "method", "dataset", "features", "samples", "p", "edge_ratio",
    "degree",
)


def main() -> None:
    source_paths = sorted(SOURCE_DIR.glob("*.csv"), key=lambda path: path.stat().st_mtime)
    rows_by_key: dict[tuple[str, ...], dict[str, str]] = {}
    fieldnames: list[str] | None = None
    matched = 0

    for path in source_paths:
        with path.open(newline="") as handle:
            reader = csv.DictReader(handle)
            if reader.fieldnames and fieldnames is None:
                fieldnames = reader.fieldnames
            for row in reader:
                if (
                    row.get("dataset") != "cliquefree_er"
                    or row.get("samples") != "2000"
                    or row.get("edge_ratio") != "4"
                ):
                    continue
                matched += 1
                key = tuple(row.get(column, "") for column in KEY_COLUMNS)
                rows_by_key[key] = row

    if fieldnames is None:
        raise FileNotFoundError(f"No CSV source files found in {SOURCE_DIR}")

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    ordered_rows = sorted(
        rows_by_key.values(),
        key=lambda row: (
            row.get("method", ""),
            int(float(row.get("features") or 0)),
            int(float(row.get("seed") or 0)),
            float(row.get("time_limit") or 0),
        ),
    )
    with OUTPUT.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(ordered_rows)

    print(f"Scanned {len(source_paths)} files; matched {matched} ER-4-0 n=2000 rows.")
    print(f"Wrote {len(ordered_rows)} unique configurations to {OUTPUT}")


if __name__ == "__main__":
    main()
