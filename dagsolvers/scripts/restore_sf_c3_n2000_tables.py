#!/usr/bin/env python3
"""Restore the SF-5-0 C3 d=40/50 n=2000 static tables from archived run logs."""

from __future__ import annotations

import csv
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "results" / "总结table-96列" / "n2000" / "experiments_exdbn_clique_summary_8.csv"
TARGET_DIR = ROOT / "results" / "cliquefree-sf-5-0" / "static_n2000"


def main() -> None:
    with SOURCE.open(newline="") as handle:
        reader = csv.DictReader(handle)
        fields = reader.fieldnames
        if not fields:
            raise ValueError(f"No header in {SOURCE}")
        rows_by_nodes = {40: [], 50: []}
        for row in reader:
            if (
                row.get("method") == "clique-C3"
                and row.get("dataset") == "cliquefree_sf"
                and row.get("samples") == "2000"
                and row.get("features") in {"40", "50"}
            ):
                nodes = int(row["features"])
                row["dataset"] = f"static_cliquefree-sf-5-0_gauss_d{nodes}_n2000"
                rows_by_nodes[nodes].append(row)

    for nodes, rows in rows_by_nodes.items():
        rows.sort(key=lambda row: int(float(row.get("degree") or 0)))
        target = TARGET_DIR / f"clique_C3_runtime_static_cliquefree-sf-5-0_gauss_d{nodes}_n2000_1800s_5clique.csv"
        with target.open("w", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
            writer.writeheader()
            writer.writerows(rows)
        print(f"Restored {len(rows)} rows to {target}")


if __name__ == "__main__":
    main()
