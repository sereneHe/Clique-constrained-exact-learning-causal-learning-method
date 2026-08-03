#!/usr/bin/env python3
"""Merge one A--G sweep summary into the curated seven-method table."""

from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd


KEY_COLUMNS = [
    "experiment",
    "dataset",
    "features",
    "samples",
    "p",
    "edge_ratio",
    "big_m",
    "seed",
    "time_limit",
]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("incoming")
    parser.add_argument("output")
    args = parser.parse_args()

    incoming = Path(args.incoming).expanduser().resolve()
    output = Path(args.output).expanduser().resolve()
    frames = []
    if output.exists():
        frames.append(pd.read_csv(output))
    frames.append(pd.read_csv(incoming))

    merged = pd.concat(frames, ignore_index=True, sort=False)
    keys = [column for column in KEY_COLUMNS if column in merged.columns]
    merged = merged.drop_duplicates(subset=keys, keep="last")
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = output.with_suffix(output.suffix + ".tmp")
    merged.to_csv(temporary, index=False)
    temporary.replace(output)
    print(f"Merged {len(frames[-1])} rows; {len(merged)} total rows in {output}")


if __name__ == "__main__":
    main()
