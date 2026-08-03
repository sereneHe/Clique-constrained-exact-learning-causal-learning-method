#!/usr/bin/env python3
"""Summarize callback-order runs from their combined stdout log."""

from __future__ import annotations

import argparse
import csv
import json
import re
from collections import defaultdict
from pathlib import Path
from statistics import mean


METHODS = {
    "CALLBACK_1800_CYCLE_ONLY": "Cycle-only",
    "CALLBACK_1800_CLIQUE_ONLY": "Clique-only",
    # Historical names are retained so old logs are summarized correctly.
    "CALLBACK_1800_CYCLE_FIRST": "Cycle-early",
    "CALLBACK_1800_CLIQUE_FIRST": "Clique-early",
    "CALLBACK_1800_CYCLE_EARLY": "Cycle-early",
    "CALLBACK_1800_CLIQUE_EARLY": "Clique-early",
    "CALLBACK_1800_CYCLE_THEN_CLIQUE": "Cycle-then-Clique",
    "CALLBACK_1800_CLIQUE_THEN_CYCLE": "Clique-then-Cycle",
}


def method_name(metadata: dict[str, object]) -> str | None:
    experiment = metadata.get("experiment")
    if experiment in METHODS:
        return METHODS[str(experiment)]
    cycle = bool(metadata.get("enable_cycle_constraints"))
    clique = bool(metadata.get("enable_clique_constraints"))
    if cycle and not clique:
        return "Cycle-only"
    if clique and not cycle:
        return "Clique-only"
    delayed = bool(metadata.get("delayed_second_separation"))
    if cycle and clique and metadata.get("separation_order") == "cycle_first":
        return "Cycle-early" if delayed else "Cycle-then-Clique"
    if cycle and clique and metadata.get("separation_order") == "clique_first":
        return "Clique-early" if delayed else "Clique-then-Cycle"
    return None


def last(pattern: str, text: str, cast=float):
    values = re.findall(pattern, text)
    return cast(values[-1]) if values else None


def parse_runs(path: Path) -> list[dict[str, object]]:
    runs: list[dict[str, object]] = []
    block: list[str] = []
    for line in path.read_text(errors="replace").splitlines():
        block.append(line)
        if not line.startswith("[EXPERIMENT-METADATA] "):
            continue
        metadata = json.loads(line.split(" ", 1)[1])
        method = method_name(metadata)
        intra = metadata.get("intra_edge_ratio")
        inter = metadata.get("inter_edge_ratio")
        text = "\n".join(block)
        callback_seconds = last(
            r"User-callback calls \d+, time in user-callback ([0-9.]+) sec", text
        )
        runtime_seconds = last(r"Explored \d+ nodes .*? in ([0-9.]+) seconds", text)
        mipsol_total = last(r"\[CALLBACK-SUMMARY\] mipsol_total=(\d+)", text, int)
        mipsol_rejected = last(r"mipsol_rejected=(\d+)", text, int)
        if method is not None and intra == inter and None not in (
            callback_seconds,
            runtime_seconds,
            mipsol_total,
            mipsol_rejected,
        ):
            runs.append(
                {
                    "graph_density": f"er-{intra}-0",
                    "method": method,
                    "seed": metadata.get("seed"),
                    "callback_inside_seconds": callback_seconds,
                    "callback_inside_ratio": callback_seconds / runtime_seconds,
                    "callback_outside_seconds": runtime_seconds - callback_seconds,
                    "callback_outside_ratio": 1.0 - callback_seconds / runtime_seconds,
                    "lazy_constraints": last(r"Lazy constraints:\s+(\d+)", text, int),
                    "nodes": last(r"Explored (\d+) nodes", text, int),
                    "gap": last(r"gap ([0-9.]+)%", text),
                    "mipsol_total": mipsol_total,
                    "rejection_rate": mipsol_rejected / mipsol_total if mipsol_total else 0.0,
                    "cycle_cuts": last(r"cycle_constraints_added=(\d+)", text, int),
                    "clique_cuts": last(r"clique_constraints_added=(\d+)", text, int),
                    "solve_after_last_constraint_seconds": last(
                        r"solve_after_last_constraint_seconds=([0-9.eE+-]+)", text
                    ),
                }
            )
        block = []
    return runs


def write_csv(path: Path, rows: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("log", type=Path)
    parser.add_argument("--output-dir", type=Path, default=Path("callback_order_summary"))
    args = parser.parse_args()
    runs = parse_runs(args.log)
    if not runs:
        raise SystemExit("No completed callback-order runs found")
    write_csv(args.output_dir / "callback_order_runs.csv", runs)

    grouped: dict[tuple[str, str], list[dict[str, object]]] = defaultdict(list)
    for row in runs:
        grouped[(str(row["graph_density"]), str(row["method"]))].append(row)
    columns = [key for key in runs[0] if key != "seed"]
    summary: list[dict[str, object]] = []
    for (density, method), group in sorted(grouped.items()):
        row: dict[str, object] = {"graph_density": density, "method": method, "seeds": len(group)}
        for column in columns[2:]:
            values = [item[column] for item in group if item[column] is not None]
            row[column] = mean(values) if values else None
        summary.append(row)
    write_csv(args.output_dir / "callback_order_summary.csv", summary)
    print(f"Wrote {len(runs)} runs and {len(summary)} summary rows to {args.output_dir}")


if __name__ == "__main__":
    main()
