#!/usr/bin/env python3
"""Compare continuous checkpoints with independent TimeLimit runs."""

import csv
import glob
import json
import os
import re
import statistics
import sys


CHECKPOINT_TIMES = [5, 15, 30, 60, 120, 300, 600, 1000, 1200, 1800, 2700, 3600, 5400, 7200]
METRICS = ["runtime_seconds", "gap", "shd", "f1score", "nnz"]


def numeric(value):
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def mean(values):
    values = [value for value in values if value is not None]
    return statistics.mean(values) if values else ""


def load_checkpoint_rows(path):
    with open(path, newline="", encoding="utf-8-sig") as handle:
        rows = list(csv.DictReader(handle))
    rows = [row for row in rows if row.get("experiment") == "METHOD_G_CONTINUOUS_CHECKPOINTS"]
    parsed = {}
    for row in rows:
        seed = str(row.get("seed", "")).strip()
        arrays = {}
        for metric, field in {
            "gap": "checkpoint_gap",
            "shd": "checkpoint_SHD",
            "f1score": "checkpoint_F1",
            "nnz": "checkpoint_NNZ",
        }.items():
            value = row.get(field, "")
            arrays[metric] = json.loads(value) if value else []
        values_by_time = {}
        for index, target in enumerate(CHECKPOINT_TIMES):
            if not arrays["gap"] or index >= len(arrays["gap"]):
                continue
            values_by_time[target] = {
                "runtime_seconds": float(target),
                **{metric: numeric(arrays[metric][index]) for metric in arrays},
            }
        parsed[seed] = values_by_time
    return parsed


def load_timelimit_rows(pattern):
    parsed = {}
    for path in glob.glob(pattern):
        match = re.search(r"_(\d+)s_5clique\.csv$", path)
        if not match:
            continue
        target = int(match.group(1))
        with open(path, newline="", encoding="utf-8-sig") as handle:
            rows = list(csv.DictReader(handle))
        # Legacy tables encode seeds by row order. Later experiments may have
        # been appended, so the original independent baseline is rows 1--5.
        for seed_index, row in enumerate(rows[:5], start=1):
            seed = str(row.get("seed", "")).strip() or str(seed_index)
            parsed.setdefault(seed, {})[target] = {
                metric: numeric(row.get(metric)) for metric in METRICS
            }
    return parsed


def averaged_row(source, data, target, seeds):
    output = {"time_limit": target, "source": source, "seed": "mean"}
    for metric in METRICS:
        output[metric] = mean([
            data[seed][target].get(metric)
            for seed in seeds
            if target in data.get(seed, {})
        ])
    return output


def main():
    checkpoint_table = os.environ["CHECKPOINT_TABLE"]
    timelimit_glob = os.environ["TIMELIMIT_TABLE_GLOB"]
    output_table = os.environ["OUTPUT_TABLE"]
    mode = os.environ.get("COMPARE_MODE", "average").strip().lower()
    if mode not in {"average", "by_seed"}:
        raise ValueError("COMPARE_MODE must be 'average' or 'by_seed'")

    checkpoints = load_checkpoint_rows(checkpoint_table)
    timelimits = load_timelimit_rows(timelimit_glob)
    common_seeds = sorted(set(checkpoints) & set(timelimits), key=lambda value: int(value))
    common_times = [
        target for target in CHECKPOINT_TIMES
        if any(target in rows for rows in checkpoints.values())
        and any(target in rows for rows in timelimits.values())
    ]

    output_rows = []
    if mode == "average":
        checkpoint_seeds = sorted(checkpoints, key=lambda value: int(value))
        timelimit_seeds = sorted(timelimits, key=lambda value: int(value))
        for target in common_times:
            output_rows.append(averaged_row("checkpoint", checkpoints, target, checkpoint_seeds))
            output_rows.append(averaged_row("timelimit", timelimits, target, timelimit_seeds))
    else:
        for target in common_times:
            for seed in common_seeds:
                if target not in checkpoints[seed] or target not in timelimits[seed]:
                    continue
                output_rows.append({
                    "time_limit": target,
                    "source": "checkpoint",
                    "seed": seed,
                    **checkpoints[seed][target],
                })
                output_rows.append({
                    "time_limit": target,
                    "source": "timelimit",
                    "seed": seed,
                    **timelimits[seed][target],
                })

    os.makedirs(os.path.dirname(output_table), exist_ok=True)
    fields = ["time_limit", "source", "seed", *METRICS]
    with open(output_table, "w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(output_rows)
    print(f"mode={mode} common_times={common_times} common_seeds={common_seeds}")
    print(f"wrote {len(output_rows)} rows: {output_table}")


if __name__ == "__main__":
    main()
