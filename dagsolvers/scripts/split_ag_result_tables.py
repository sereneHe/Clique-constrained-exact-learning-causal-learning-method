#!/usr/bin/env python3
"""Split mixed A-G result CSVs by batch, experiment type, TimeLimit, and Big-M."""

from __future__ import annotations

import csv
import re
from collections import defaultdict
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
RESULT_ROOT = PROJECT_ROOT / "dagsolvers/results/A-G实验记录"
OUTPUT_ROOT = RESULT_ROOT / "按批次_M_时间拆分"

SOURCES = {
    "第一次A-G实验记录-100m-1000s.csv": "第一次A-G实验记录",
    "第二次A-G实验记录-100m-1200s.csv": "第二次A-G实验记录",
    "experiments_exdbn_clique_summary.csv": "最新7种方法实验记录",
    "A-G_experiments_100m-60s.csv": "补充混合实验记录",
}

FINISHED_STATES = {"FINISHED", "OPTIMAL", "TIME_LIMIT", "DONE", "COMPLETED"}


def normalized_number(value: str, missing: str = "未记录") -> str:
    value = str(value or "").strip()
    if not value:
        return missing
    try:
        number = float(value)
    except ValueError:
        return value.replace("/", "-")
    return str(int(number)) if number.is_integer() else f"{number:g}"


def experiment_type(row: dict[str, str]) -> str:
    experiment = row.get("experiment", "")
    family = row.get("method_family", "")
    if family == "CALLBACK" or experiment.startswith("CALLBACK_"):
        return "Callback顺序实验"
    if family == "E" or "BIG_M" in experiment or "EDGE_SPECIFIC" in experiment:
        return "BigM实验"
    return "非BigM实验"


def effective_big_m(row: dict[str, str], kind: str) -> str:
    """Use the intended M encoded in Big-M experiment names when old logs misreported big_m."""
    experiment = row.get("experiment", "")
    if kind == "BigM实验":
        if "EDGE_SPECIFIC" in experiment:
            return "edge-specific-Mij"
        explicit = re.search(r"BIG_M_(\d+)", experiment)
        if explicit:
            return explicit.group(1)
    return normalized_number(row.get("big_m", ""))


def read_csv(path: Path) -> tuple[list[str], list[dict[str, str]]]:
    with path.open(newline="", encoding="utf-8-sig") as handle:
        reader = csv.DictReader(handle)
        return list(reader.fieldnames or []), list(reader)


def write_csv(path: Path, fieldnames: list[str], rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def main() -> None:
    OUTPUT_ROOT.mkdir(parents=True, exist_ok=True)
    for old in OUTPUT_ROOT.glob("*.csv"):
        old.unlink()

    index_rows: list[dict[str, str | int]] = []
    for source_name, batch_name in SOURCES.items():
        source_path = RESULT_ROOT / source_name
        if not source_path.exists():
            continue
        fieldnames, rows = read_csv(source_path)
        groups: dict[tuple[str, str, str], list[dict[str, str]]] = defaultdict(list)
        for row in rows:
            kind = experiment_type(row)
            time_limit = normalized_number(row.get("time_limit", ""))
            big_m = effective_big_m(row, kind)
            if source_name == "第一次A-G实验记录-100m-1000s.csv" and kind == "BigM实验" and time_limit == "1000":
                big_m = "10/20/50/100/edge-specific-Mij"
            groups[(kind, time_limit, big_m)].append(row)

        source_written = 0
        for (kind, time_limit, big_m), group_rows in sorted(groups.items()):
            if big_m == "10/20/50/100/edge-specific-Mij":
                m_token = "M10-M20-M50-M100-M-edge-specific-Mij-合并"
            else:
                m_token = f"M{big_m}" if re.fullmatch(r"\d+(?:\.\d+)?", big_m) else f"M-{big_m}"
            filename = f"{batch_name}-{kind}-{time_limit}s-{m_token}.csv"
            output_path = OUTPUT_ROOT / filename
            write_csv(output_path, fieldnames, group_rows)
            source_written += len(group_rows)
            experiments = sorted({row.get("experiment", "") for row in group_rows if row.get("experiment")})
            completed = sum(str(row.get("status", "")).upper() in FINISHED_STATES for row in group_rows)
            index_rows.append({
                "source_table": source_name,
                "batch": batch_name,
                "experiment_type": kind,
                "time_limit_s": time_limit,
                "big_m": big_m,
                "output_table": filename,
                "row_count": len(group_rows),
                "completed_rows": completed,
                "experiment_count": len(experiments),
                "experiments": "; ".join(experiments),
            })
        if source_written != len(rows):
            raise RuntimeError(f"Row reconciliation failed for {source_name}: {source_written} != {len(rows)}")

    # Consolidate every Big-M table across batches into one auditable master table.
    big_m_index = [row for row in index_rows if row["experiment_type"] == "BigM实验"]
    master_rows: list[dict[str, str]] = []
    master_fields = ["source_table", "experiment_batch", "source_split_table", "effective_big_m"]
    master_experiments: set[str] = set()
    master_times: set[str] = set()
    master_ms: set[str] = set()
    for item in big_m_index:
        split_path = OUTPUT_ROOT / str(item["output_table"])
        split_fields, split_rows = read_csv(split_path)
        for field in split_fields:
            if field not in master_fields:
                master_fields.append(field)
        for row in split_rows:
            enriched = dict(row)
            enriched["source_table"] = str(item["source_table"])
            enriched["experiment_batch"] = str(item["batch"])
            enriched["source_split_table"] = str(item["output_table"])
            enriched["effective_big_m"] = effective_big_m(row, "BigM实验")
            master_rows.append(enriched)
            if row.get("experiment"):
                master_experiments.add(row["experiment"])
        master_times.add(str(item["time_limit_s"]))
        master_ms.add(str(item["big_m"]))
        split_path.unlink()

    if big_m_index:
        master_name = "Big M实验.csv"
        write_csv(OUTPUT_ROOT / master_name, master_fields, master_rows)
        index_rows = [row for row in index_rows if row["experiment_type"] != "BigM实验"]
        index_rows.insert(0, {
            "source_table": "多个原始表",
            "batch": "第一次A-G/第二次A-G/最新7种方法/补充混合",
            "experiment_type": "BigM实验",
            "time_limit_s": "/".join(sorted(master_times, key=lambda value: float(value))),
            "big_m": "/".join(sorted(master_ms)),
            "output_table": master_name,
            "row_count": len(master_rows),
            "completed_rows": sum(str(row.get("status", "")).upper() in FINISHED_STATES for row in master_rows),
            "experiment_count": len(master_experiments),
            "experiments": "; ".join(sorted(master_experiments)),
        })

    index_fields = [
        "source_table", "batch", "experiment_type", "time_limit_s", "big_m",
        "output_table", "row_count", "completed_rows", "experiment_count", "experiments",
    ]
    write_csv(OUTPUT_ROOT / "拆分索引.csv", index_fields, index_rows)
    print(f"Wrote {len(index_rows)} split tables to {OUTPUT_ROOT}")


if __name__ == "__main__":
    main()
