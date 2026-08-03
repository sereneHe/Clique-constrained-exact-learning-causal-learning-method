#!/usr/bin/env python3
"""Build the long-form synthetic-data-characteristics CSV from saved artifacts."""

from __future__ import annotations

import csv
import re
from collections import defaultdict
from pathlib import Path

import numpy as np


ROOT = Path(__file__).resolve().parents[1]
SUMMARY_DIR = ROOT / "results" / "summary"
INPUT_TEX = SUMMARY_DIR / "dataset_characteristics.tex"
OUTPUT_CSV = SUMMARY_DIR / "dataset_characteristics.csv"
PER_SEED_OUTPUT_CSV = SUMMARY_DIR / "dataset_characteristics_per_seed.csv"
TARGETS = ("ER-5-0", "ER-4-0", "SF-5-0")


def numeric_matrix(path: Path) -> list[list[float]] | None:
    try:
        rows = [
            [float(value) for value in row if value.strip()]
            for row in csv.reader(path.open(newline=""))
        ]
    except (OSError, ValueError):
        return None
    return rows or None


def r2_from_x_and_w(x: list[list[float]], w: list[list[float]]) -> float | None:
    d = len(w)
    if not x or any(len(row) != d for row in x) or len(w) != d or any(len(row) != d for row in w):
        return None
    x_array, w_array = np.asarray(x, dtype=float), np.asarray(w, dtype=float)
    scores: list[float] = []
    for node in range(d):
        if not np.any(np.abs(w_array[:, node]) > 1e-12):
            continue
        observed = x_array[:, node]
        predicted = x_array @ w_array[:, node]
        mean = float(np.mean(observed))
        denominator = float(np.sum((observed - mean) ** 2))
        if denominator:
            scores.append(1.0 - float(np.sum((observed - predicted) ** 2)) / denominator)
    return sum(scores) / len(scores) if scores else None


def density_from_w(w: list[list[float]]) -> float | None:
    d = len(w)
    if d < 2 or any(len(row) != d for row in w):
        return None
    edges = sum(abs(value) > 1e-12 for row in w for value in row)
    return 100.0 * edges / (d * (d - 1) / 2)


def split_range(text: str, sample_index: int) -> tuple[str, str]:
    value = text.replace(r"\%", "%").replace("$^\\dagger$", "").replace("†", "").strip()
    by_sample = [item.strip() for item in value.split(" / ")]
    value = by_sample[min(sample_index, len(by_sample) - 1)]
    if "--" in value:
        lower, upper = (item.strip() for item in value.split("--", 1))
        if upper.endswith("%") and not lower.endswith("%"):
            lower += "%"
        return lower, upper
    return value, value


def records_from_tex() -> list[dict[str, str]]:
    text = INPUT_TEX.read_text()
    blocks = re.findall(r"(?ms)^(\d+\s*&.*?\\\\)\s*$", text)
    records: list[dict[str, str]] = []
    for block in blocks:
        cells = [cell.strip().rstrip("\\").strip() for cell in re.sub(r"\s+", " ", block).split(" & ")]
        if len(cells) != 12:
            raise ValueError(f"Expected 12 cells, got {len(cells)}: {block}")
        for dataset, offset in (("ER-4-0", 0), ("ER-5-0", 4), ("SF-5-0", 8)):
            nodes, nominal, density, r2 = cells[offset : offset + 4]
            nominal = nominal.replace(r"\%", "%")
            for sample, sample_index in ((200, 0), (2000, 1)):
                density_lower, density_upper = split_range(density, sample_index)
                r2_lower, r2_upper = split_range(r2, sample_index)
                records.append(
                    {
                        "dataset": dataset,
                        "sample": str(sample),
                        "nodes": nodes,
                        "nominal_density": nominal,
                        "realized_density_lower": density_lower,
                        "realized_density_upper": density_upper,
                        "R2_lower": r2_lower,
                        "R2_upper": r2_upper,
                    }
                )
    if len(records) != 54:
        raise ValueError(f"Expected 54 table records, got {len(records)}")
    return records


def problem_config(run_dir: Path) -> tuple[str, int, int, int] | None:
    candidates = (
        run_dir / ".hydra" / "config.yaml",
        run_dir / "config.yaml",
        run_dir / "artifacts" / "config.yaml",
    )
    for path in candidates:
        if not path.is_file():
            continue
        text = path.read_text(errors="ignore")
        problem = re.search(r"(?ms)^problem:\s*$\n(.*?)(?=^[A-Za-z_][\w-]*:\s*$|\Z)", text)
        if not problem:
            continue
        body = problem.group(1)
        def get(name: str) -> str | None:
            match = re.search(rf"(?m)^\s*{re.escape(name)}:\s*([^\s#]+)", body)
            return match.group(1) if match else None
        name, d, n, seed, ratio = (
            get("name"),
            get("number_of_variables"),
            get("number_of_samples"),
            get("seed"),
            get("intra_edge_ratio"),
        )
        if not all((name, d, n, seed, ratio)):
            continue
        scenario = {
            ("cliquefree_er", "4"): "ER-4-0",
            ("cliquefree_er", "5"): "ER-5-0",
            ("cliquefree_sf", "5"): "SF-5-0",
        }.get((name, ratio))
        if scenario:
            return scenario, int(d), int(n), int(seed)
    return None


def artifact_runs() -> dict[tuple[str, int, int, int], tuple[float, float]]:
    candidates: dict[tuple[str, int, int, int], list[Path]] = defaultdict(list)
    artifact_paths = list((ROOT / "mlruns").glob("*/*/artifacts/W_true.csv"))
    artifact_paths.extend((ROOT / "multirun").rglob("W_true.csv"))
    artifact_paths.extend((ROOT / "results").glob("cliquefree-*/multirun/**/W_true.csv"))
    for w_path in artifact_paths:
        if "results/summary" in str(w_path):
            continue
        run_dir = w_path.parent
        if run_dir.name == "artifacts":
            run_dir = run_dir.parent
        config = problem_config(run_dir)
        if not config:
            continue
        scenario, d, n, seed = config
        if scenario not in TARGETS or d not in (11, 15, 20, 25, 30, 35, 40, 45, 50) or n not in (200, 2000):
            continue
        if w_path.with_name("X.csv").is_file():
            candidates[(scenario, d, n, seed)].append(w_path)

    selected: dict[tuple[str, int, int, int], tuple[float, float]] = {}
    for key, paths in candidates.items():
        # Repeated solver runs generate identical data for a seed.  Pick one
        # deterministically, preferring the newest artifact if duplicates exist.
        w_path = max(paths, key=lambda path: path.stat().st_mtime)
        x, w = numeric_matrix(w_path.with_name("X.csv")), numeric_matrix(w_path)
        if x is None or w is None:
            continue
        density, r2 = density_from_w(w), r2_from_x_and_w(x, w)
        if density is not None and r2 is not None:
            selected[key] = density, r2
    return selected


def main() -> None:
    records = records_from_tex()
    artifacts = artifact_runs()
    grouped: dict[tuple[str, int, int], list[tuple[float, float]]] = defaultdict(list)
    for (dataset, nodes, sample, _seed), values in artifacts.items():
        grouped[(dataset, sample, nodes)].append(values)

    for row in records:
        key = (row["dataset"], int(row["sample"]), int(row["nodes"]))
        values = grouped.get(key, [])
        row["realized_density_mean"] = f"{sum(value[0] for value in values) / len(values):.2f}%" if values else ""
        row["R2_mean"] = f"{sum(value[1] for value in values) / len(values):.3f}" if values else ""
        row["artifact_seed_count"] = str(len(values))

    ordered = sorted(records, key=lambda row: (TARGETS.index(row["dataset"]), int(row["sample"]), int(row["nodes"])))
    fields = [
        "dataset", "sample", "nodes", "nominal_density",
        "realized_density_lower", "realized_density_upper", "realized_density_mean",
        "R2_lower", "R2_upper", "R2_mean", "artifact_seed_count",
    ]
    with OUTPUT_CSV.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(ordered)

    nominal_density = {
        (row["dataset"], int(row["sample"]), int(row["nodes"])): row["nominal_density"]
        for row in records
    }
    per_seed_rows = []
    for (dataset, nodes, sample, seed), (density, r2) in sorted(
        artifacts.items(), key=lambda item: (TARGETS.index(item[0][0]), item[0][2], item[0][1], item[0][3])
    ):
        per_seed_rows.append({
            "dataset": dataset,
            "sample": sample,
            "nodes": nodes,
            "nominal_density": nominal_density[(dataset, sample, nodes)],
            "realized_density": f"{density:.2f}%",
            "R2": f"{r2:.3f}",
            "seed": seed,
        })
    with PER_SEED_OUTPUT_CSV.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=[
            "dataset", "sample", "nodes", "nominal_density", "realized_density", "R2", "seed",
        ])
        writer.writeheader()
        writer.writerows(per_seed_rows)
    missing = [row for row in ordered if not row["artifact_seed_count"] or row["artifact_seed_count"] == "0"]
    print(f"Wrote {len(ordered)} summary rows to {OUTPUT_CSV}")
    print(f"Wrote {len(per_seed_rows)} per-seed rows to {PER_SEED_OUTPUT_CSV}")
    print(f"Rows without artifacts: {len(missing)}")
    for row in missing:
        print(f"  {row['dataset']}, n={row['sample']}, d={row['nodes']}")


if __name__ == "__main__":
    main()
