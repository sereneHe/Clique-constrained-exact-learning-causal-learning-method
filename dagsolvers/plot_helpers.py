from __future__ import annotations

import csv
import math
import os
import re
from bisect import bisect_right
from collections import defaultdict
from pathlib import Path
from typing import Any

import matplotlib.pyplot as plt
from matplotlib.ticker import FuncFormatter
import numpy as np
import pandas as pd
from scipy.interpolate import PchipInterpolator

PROFILE_SOLVERS = {
    "runtime": "milp",
    "clique": "cliquewidth",
    "limit": "edge_limit",
}
TIME_LIMIT_SOLVER_LABELS = {
    "milp": "MILP",
    "clique": "Clique-width MILP",
    "edge_limit": "Edge-limit MILP",
}

TIME_LIMIT_SOLVER_STYLES = {
    "milp": {"color": "#1f77b4", "linestyle": "-"},
    "clique": {"color": "#ff7f0e", "linestyle": "-"},
    "edge_limit": {"color": "#2ca02c", "linestyle": "-"},
}

METRIC_LABELS = {
    "runtime_seconds": "Runtime",
    "lazy_count": "Lazy constraints",
    "best_shd": "Best SHD",
}

BASE_SOLVER_ORDER = ("milp", "cliquewidth", "edge_limit", "edge_limit_mean")
SOLVER_LABELS = {
    "milp": "MILP",
    "cliquewidth": "Clique Width",
    "edge_limit": "Edge Limit",
    "edge_limit_mean": "Edge Limit Mean",
}
SOLVER_COLORS = {
    "milp": "#ff7f0e",
    "cliquewidth": "#1f77b4",
    "edge_limit": "#2ca02c",
    "edge_limit_mean": "#2ca02c",
}
SOLVER_LINESTYLES = {
    "milp": "-",
    "cliquewidth": "-",
    "edge_limit": "-.",
    "edge_limit_mean": "-",
}
PROFILE_EPSILON = 1e-9


def time_limit_solver_key(name: str) -> str | None:
    if name.startswith("clique_runtime_"):
        return "clique"
    if name.startswith("limit_runtime_"):
        return "edge_limit"
    if name.startswith("runtime_"):
        return "milp"
    return None


def scenario_prefix_and_base_dir(report_dir: Path) -> tuple[str, Path]:
    match = re.match(r"^(.*)-(\d+)s$", report_dir.name)
    if match is None:
        raise ValueError(
            f"Cannot infer scenario prefix from report dir name: {report_dir.name}. "
            "Expected something like SF-5-0-1800s."
        )
    return match.group(1), report_dir.parent


def results_base_dir_for_report_dir(report_dir: Path, default_results_base_dir: Path) -> Path:
    env_base_dir = os.getenv("EXDBN_RESULTS_RUN_DIR")
    if env_base_dir:
        return Path(env_base_dir).resolve()
    if "reports" in report_dir.parts:
        parts = list(report_dir.parts)
        idx = parts.index("reports")
        parts[idx] = "results"
        return Path(*parts[: idx + 2]).resolve()
    return default_results_base_dir.resolve()


def collect_time_limit_summary(
    report_dir: Path,
    *,
    solver_labels: dict[str, str],
    default_results_base_dir: Path,
    sample_size: int = 200,
    d: int = 35,
) -> pd.DataFrame:
    scenario_prefix, _ = scenario_prefix_and_base_dir(report_dir)
    results_base_dir = results_base_dir_for_report_dir(report_dir, default_results_base_dir)
    time_limit_pattern = re.compile(rf"^{re.escape(scenario_prefix)}-(\d+)s$")
    rows: list[dict[str, Any]] = []
    for scenario_dir in sorted(results_base_dir.iterdir()):
        if not scenario_dir.is_dir():
            continue
        match = time_limit_pattern.match(scenario_dir.name)
        if not match:
            continue
        time_limit = int(match.group(1))
        static_dir = scenario_dir / f"static_n{sample_size}"
        if not static_dir.exists():
            continue
        for csv_path in sorted(static_dir.glob(f"*d{d}_n{sample_size}*.csv")):
            solver_key = time_limit_solver_key(csv_path.name)
            if solver_key is None:
                continue
            df = pd.read_csv(csv_path)
            if df.empty or "shd" not in df.columns:
                continue
            rows.append(
                {
                    "report_dir": scenario_dir.name,
                    "time_limit": time_limit,
                    "sample_size": sample_size,
                    "d": d,
                    "solver_key": solver_key,
                    "solver": solver_labels[solver_key],
                    "rows": len(df),
                    "mean_shd": float(df["shd"].mean()),
                    "sd_shd": float(df["shd"].std(ddof=1)) if len(df) > 1 else 0.0,
                    "mean_f1": float(df["f1score"].mean()) if "f1score" in df.columns else float("nan"),
                    "sd_f1": float(df["f1score"].std(ddof=1)) if "f1score" in df.columns and len(df) > 1 else 0.0,
                    "csv_path": str(csv_path),
                }
            )
    result = pd.DataFrame(rows)
    if not result.empty:
        result = result.sort_values(["solver_key", "time_limit"]).reset_index(drop=True)
    return result


def available_time_limit_d_values(
    report_dir: Path,
    *,
    default_results_base_dir: Path,
    sample_size: int = 200,
) -> list[int]:
    scenario_prefix, _ = scenario_prefix_and_base_dir(report_dir)
    results_base_dir = results_base_dir_for_report_dir(report_dir, default_results_base_dir)
    time_limit_pattern = re.compile(rf"^{re.escape(scenario_prefix)}-(\d+)s$")
    pattern = re.compile(rf".*_d(\d+)_n{sample_size}(?:_.*)?\.csv$")
    d_values: set[int] = set()
    for scenario_dir in sorted(results_base_dir.iterdir()):
        if not scenario_dir.is_dir():
            continue
        if not time_limit_pattern.match(scenario_dir.name):
            continue
        static_dir = scenario_dir / f"static_n{sample_size}"
        if not static_dir.exists():
            continue
        for csv_path in static_dir.glob("*.csv"):
            match = pattern.match(csv_path.name)
            if match:
                d_values.add(int(match.group(1)))
    return sorted(d_values)


def parse_gap_value(text: str) -> float:
    return float(text.rstrip("*"))


def results_run_dir_for_report_dir(report_dir: Path) -> Path:
    if "reports" in report_dir.parts:
        parts = list(report_dir.parts)
        idx = parts.index("reports")
        parts[idx] = "results"
        return Path(*parts).resolve()
    env_base_dir = os.getenv("EXDBN_RESULTS_RUN_DIR", "").strip()
    if env_base_dir:
        return Path(env_base_dir).resolve() / report_dir.name
    return report_dir.resolve()


def problem_key_from_name(path: Path) -> tuple[int, int]:
    match = re.search(r"_d(\d+)_n(\d+)(?:_.*)?\.csv$", path.name)
    if match is None:
        raise ValueError(f"Cannot parse d/n from {path}")
    return int(match.group(1)), int(match.group(2))


def load_limit_rows(path: Path) -> list[dict[str, float | int]]:
    with path.open() as handle:
        reader = csv.DictReader(handle)
        rows = []
        for row in reader:
            rows.append(
                {
                    "degree": int(float(row["degree"])),
                    "shd": float(row["shd"]),
                    "gap": float(row["gap"]),
                }
            )
    rows.sort(key=lambda row: int(row["degree"]))
    return rows


def collect_limit_tables(report_dir: Path) -> list[Path]:
    run_dir = results_run_dir_for_report_dir(report_dir)
    tables: list[Path] = []
    for sample_dir in (run_dir / "static_n200", run_dir / "static_n2000"):
        if sample_dir.exists():
            tables.extend(sorted(sample_dir.glob("limit_runtime_static_SF-5-0_gauss_d*_n*.csv")))
    return tables


def contiguous_shd_segments(rows: list[dict[str, float | int]]) -> list[list[dict[str, float | int]]]:
    if not rows:
        return []
    segments: list[list[dict[str, float | int]]] = []
    current = [rows[0]]
    for row in rows[1:]:
        prev = current[-1]
        if int(row["degree"]) == int(prev["degree"]) + 1 and float(row["shd"]) == float(prev["shd"]):
            current.append(row)
        else:
            segments.append(current)
            current = [row]
    segments.append(current)
    return segments


def contiguous_gap_segments(rows: list[dict[str, float | int]]) -> list[list[dict[str, float | int]]]:
    if not rows:
        return []
    segments: list[list[dict[str, float | int]]] = []
    current = [rows[0]]
    for row in rows[1:]:
        prev = current[-1]
        if int(row["degree"]) == int(prev["degree"]) + 1 and float(row["gap"]) == float(prev["gap"]):
            current.append(row)
        else:
            segments.append(current)
            current = [row]
    segments.append(current)
    return segments


def contiguous_gap_segments_2dp(rows: list[dict[str, float | int]]) -> list[list[dict[str, float | int]]]:
    if not rows:
        return []
    segments: list[list[dict[str, float | int]]] = []
    current = [rows[0]]
    for row in rows[1:]:
        prev = current[-1]
        if (
            int(row["degree"]) == int(prev["degree"]) + 1
            and round(float(row["gap"]), 2) == round(float(prev["gap"]), 2)
        ):
            current.append(row)
        else:
            segments.append(current)
            current = [row]
    segments.append(current)
    return segments


def select_stable_best_row(rows: list[dict[str, float | int]]) -> dict[str, float | int]:
    segments = contiguous_shd_segments(rows)
    stable_segments = [segment for segment in segments if len(segment) >= 2]
    if stable_segments:
        best_shd = min(float(segment[0]["shd"]) for segment in stable_segments)
        candidate_segments = [
            segment for segment in stable_segments if float(segment[0]["shd"]) == best_shd
        ]
        return min(candidate_segments, key=lambda segment: int(segment[0]["degree"]))[0]

    min_shd = min(float(row["shd"]) for row in rows)
    best_rows = [row for row in rows if float(row["shd"]) == min_shd]
    return min(best_rows, key=lambda row: int(row["degree"]))


def select_stable_min_gap_row(
    rows: list[dict[str, float | int]],
    *,
    gap_exact_stable_min_len: int = 3,
    gap_2dp_stable_min_len: int = 4,
    gap_2dp_fallback_min_len: int = 3,
) -> tuple[dict[str, float | int], bool]:
    segments = contiguous_gap_segments(rows)
    stable_segments = [segment for segment in segments if len(segment) >= gap_exact_stable_min_len]
    if stable_segments:
        best_gap = min(float(segment[0]["gap"]) for segment in stable_segments)
        candidate_segments = [segment for segment in stable_segments if float(segment[0]["gap"]) == best_gap]
        return min(candidate_segments, key=lambda segment: int(segment[0]["degree"]))[0], False

    segments_2dp = contiguous_gap_segments_2dp(rows)
    stable_segments_2dp = [segment for segment in segments_2dp if len(segment) >= gap_2dp_stable_min_len]
    if stable_segments_2dp:
        min_degree = min(int(row["degree"]) for row in rows)
        max_degree = max(int(row["degree"]) for row in rows)
        midpoint = (min_degree + max_degree) / 2.0
        late_segments_2dp = [
            segment for segment in stable_segments_2dp if int(segment[0]["degree"]) > midpoint
        ]
        candidate_pool = late_segments_2dp if late_segments_2dp else stable_segments_2dp
        best_gap_2dp = min(round(float(segment[0]["gap"]), 2) for segment in candidate_pool)
        candidate_segments_2dp = [
            segment
            for segment in candidate_pool
            if round(float(segment[0]["gap"]), 2) == best_gap_2dp
        ]
        return min(candidate_segments_2dp, key=lambda segment: int(segment[0]["degree"]))[0], True

    fallback_segments_2dp = [segment for segment in segments_2dp if len(segment) >= gap_2dp_fallback_min_len]
    if fallback_segments_2dp:
        min_degree = min(int(row["degree"]) for row in rows)
        max_degree = max(int(row["degree"]) for row in rows)
        midpoint = (min_degree + max_degree) / 2.0
        late_segments_2dp = [
            segment for segment in fallback_segments_2dp if int(segment[0]["degree"]) > midpoint
        ]
        candidate_pool = late_segments_2dp if late_segments_2dp else fallback_segments_2dp
        best_gap_2dp = min(round(float(segment[0]["gap"]), 2) for segment in candidate_pool)
        candidate_segments_2dp = [
            segment
            for segment in candidate_pool
            if round(float(segment[0]["gap"]), 2) == best_gap_2dp
        ]
        return min(candidate_segments_2dp, key=lambda segment: int(segment[0]["degree"]))[0], True

    min_gap = min(float(row["gap"]) for row in rows)
    best_rows = [row for row in rows if float(row["gap"]) == min_gap]
    return min(best_rows, key=lambda row: int(row["degree"])), False


def build_edge_limit_summaries(report_dir: Path) -> tuple[list[dict[str, object]], list[dict[str, object]]]:
    shd_summary: list[dict[str, object]] = []
    gap_summary: list[dict[str, object]] = []
    for table_path in collect_limit_tables(report_dir):
        d, n = problem_key_from_name(table_path)
        rows = load_limit_rows(table_path)
        if not rows:
            continue
        min_degree_row = select_stable_best_row(rows)
        min_gap_row, gap_from_2dp = select_stable_min_gap_row(rows)
        shd_summary.append(
            {
                "d": d,
                "n": n,
                "min_degree": int(min_degree_row["degree"]),
                "min_shd": float(min_degree_row["shd"]),
            }
        )
        gap_summary.append(
            {
                "d": d,
                "n": n,
                "min_degree": int(min_gap_row["degree"]),
                "gap": f"{float(min_gap_row['gap'])}*" if gap_from_2dp else float(min_gap_row["gap"]),
            }
        )
    shd_summary.sort(key=lambda row: (int(row["n"]), int(row["d"])))
    gap_summary.sort(key=lambda row: (int(row["n"]), int(row["d"])))
    return shd_summary, gap_summary


def write_summary_csv(path: Path, rows: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        path.write_text("")
        return
    with path.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def generate_edge_limit_summaries(report_dir: Path, output_dir: Path | None = None) -> tuple[Path, Path]:
    output_dir = (output_dir or (results_run_dir_for_report_dir(report_dir) / "tables")).resolve()
    shd_summary, gap_summary = build_edge_limit_summaries(report_dir.resolve())
    shd_path = output_dir / "edge_limit_min_shd_summary.csv"
    gap_path = output_dir / "edge_limit_min_gap_summary.csv"
    write_summary_csv(shd_path, shd_summary)
    write_summary_csv(gap_path, gap_summary)
    return shd_path, gap_path


def infer_edge_limit_source_label(summary_csv: Path) -> str:
    name = summary_csv.name.lower()
    if "shd" in name:
        return "shd"
    return "gap"


def load_edge_limit_rows_for_plot(summary_csv: Path, metric: str) -> dict[int, list[tuple[int, float]]]:
    rows_by_n: dict[int, list[tuple[int, float]]] = {200: [], 2000: []}
    with summary_csv.open() as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            d = int(row["d"])
            n = int(row["n"])
            if metric == "degree":
                value = float(int(row["min_degree"]))
            else:
                value = parse_gap_value(row["gap"])
            if n in rows_by_n:
                rows_by_n[n].append((d, value))

    for n in rows_by_n:
        rows_by_n[n].sort(key=lambda item: item[0])
    return rows_by_n


def safe_float(value: str | None) -> float:
    if value is None:
        return math.inf
    text = str(value).strip()
    if not text:
        return math.inf
    try:
        parsed = float(text)
    except ValueError:
        return math.inf
    if not math.isfinite(parsed) or parsed < 0:
        return math.inf
    return parsed


def mean_metric_from_rows(rows: list[dict[str, str]], key: str) -> str:
    finite = [safe_float(row.get(key)) for row in rows]
    finite = [value for value in finite if math.isfinite(value)]
    if not finite:
        return ""
    return str(sum(finite) / len(finite))


def problem_key(row: dict[str, str]) -> tuple[str, int, int, int]:
    section = str(row.get("section", "")).replace("_", "-")
    samples = int(float(row.get("samples", "0")))
    number_of_variables = int(float(row.get("number_of_variables", "0")))
    seed = int(float(row.get("seed", "0")))
    return section, samples, number_of_variables, seed


def problem_key_without_seed(row: dict[str, str]) -> tuple[str, int, int, int]:
    section, samples, number_of_variables, _seed = problem_key(row)
    return section, samples, number_of_variables, 0


def metric_value(row: dict[str, str], metric: str) -> float:
    status = str(row.get("status", "ok")).strip().lower()
    if status != "ok":
        return math.inf
    return safe_float(row.get(metric))


def first_present(row: dict[str, str], keys: tuple[str, ...]) -> str:
    for key in keys:
        value = row.get(key)
        if value is not None and str(value).strip():
            return str(value).strip()
    return ""


def first_numeric_series(df: pd.DataFrame, columns: tuple[str, ...]) -> pd.Series:
    for column in columns:
        if column in df.columns:
            series = pd.to_numeric(df[column], errors="coerce")
            if isinstance(series, pd.Series):
                return series
    return pd.Series(dtype=float)


def iter_solver_table_csvs(table_dir: Path):
    static_dirs = [path for path in sorted(table_dir.glob("static_n*")) if path.is_dir()]
    search_dirs = static_dirs or [table_dir]
    for search_dir in search_dirs:
        for csv_path in sorted(search_dir.glob("*.csv")):
            name = csv_path.name
            if (
                name.startswith("runtime_static_")
                or name.startswith("clique_runtime_static_")
                or name.startswith("limit_runtime_static_")
            ):
                yield csv_path


def collect_rows_from_table_dir(
    table_dir: Path,
    *,
    scenario_key: str | None = None,
    include_edge_limit: bool = True,
    include_edge_limit_mean: bool = True,
) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for csv_path in iter_solver_table_csvs(table_dir):
        solver_prefix = csv_path.name.split("_", 1)[0]
        solver = PROFILE_SOLVERS.get(solver_prefix)
        if solver is None:
            continue
        with csv_path.open(newline="") as handle:
            reader = list(csv.DictReader(handle))

        if solver == "edge_limit":
            selected_rows: list[tuple[dict[str, str], str]] = []
            if reader:
                if include_edge_limit:
                    selected_rows.append((reader[-1], "edge_limit"))
                if include_edge_limit_mean:
                    mean_row = dict(reader[-1])
                    mean_row["seed"] = "0"
                    mean_row["degree"] = "0"
                    for metric_key in ("runtime_seconds", "gap", "shd", "lazy_count"):
                        mean_row[metric_key] = mean_metric_from_rows(reader, metric_key)
                    selected_rows.append((mean_row, "edge_limit_mean"))
        else:
            selected_rows = [(row, solver) for row in reader]

        for row, row_solver in selected_rows:
            section = first_present(row, ("section", "scenario", "dataset"))
            if scenario_key and section and scenario_key not in section.replace("_", "-"):
                continue
            if scenario_key and not section:
                section = scenario_key
            if not section:
                continue
            samples = first_present(row, ("samples",))
            features = first_present(row, ("number_of_variables", "features"))
            seed = first_present(row, ("seed", "degree", "repeat"))
            runtime_seconds = first_present(row, ("runtime_seconds",))
            gap = first_present(row, ("gap",))
            shd = first_present(row, ("shd",))
            lazy_count = first_present(row, ("lazy_count",))
            status = first_present(row, ("status",)) or "ok"
            rows.append(
                {
                    "section": section,
                    "samples": samples,
                    "number_of_variables": features,
                    "seed": seed,
                    "solver": row_solver,
                    "status": status,
                    "runtime_seconds": runtime_seconds,
                    "best_shd": shd,
                    "shd": shd,
                    "gap": gap,
                    "lazy_count": lazy_count,
                }
            )
    if not rows:
        raise ValueError(f"No solver rows found under {table_dir}")
    return rows


def mean_finite(values: list[float]) -> float:
    finite = [value for value in values if math.isfinite(value)]
    if not finite:
        return math.inf
    return sum(finite) / len(finite)


def build_metric_matrix(
    rows: list[dict[str, str]],
    metric: str,
    *,
    solver_order: tuple[str, ...],
    mean_over_seeds: bool = False,
) -> list[list[float]]:
    rowmap: dict[tuple[tuple[str, int, int, int], str], float] = {}
    problems_by_solver: dict[str, set[tuple[str, int, int, int]]] = {
        solver: set() for solver in solver_order
    }

    if mean_over_seeds:
        grouped_values: dict[tuple[tuple[str, int, int, int], str], list[float]] = defaultdict(list)
        for row in rows:
            solver = str(row.get("solver", "")).strip().lower()
            if solver not in solver_order:
                continue
            problem = problem_key_without_seed(row)
            grouped_values[(problem, solver)].append(metric_value(row, metric))
            problems_by_solver[solver].add(problem)
        for key, values in grouped_values.items():
            rowmap[key] = mean_finite(values)
    else:
        for row in rows:
            solver = str(row.get("solver", "")).strip().lower()
            if solver not in solver_order:
                continue
            problem = problem_key(row)
            rowmap[(problem, solver)] = metric_value(row, metric)
            problems_by_solver[solver].add(problem)

    common_problems: set[tuple[str, int, int, int]] | None = None
    for solver in solver_order:
        solver_problems = problems_by_solver[solver]
        if common_problems is None:
            common_problems = set(solver_problems)
        else:
            common_problems &= solver_problems

    ordered_problems = sorted(common_problems or set())
    if not ordered_problems:
        raise ValueError(f"No common problems found across solvers for metric {metric}")

    matrix: list[list[float]] = []
    for problem in ordered_problems:
        matrix.append([rowmap[(problem, solver)] for solver in solver_order])
    return matrix


def active_solver_order(*, include_edge_limit: bool, include_edge_limit_mean: bool) -> tuple[str, ...]:
    solver_order = ["milp", "cliquewidth"]
    if include_edge_limit:
        solver_order.append("edge_limit")
    if include_edge_limit_mean:
        solver_order.append("edge_limit_mean")
    return tuple(solver_order)


def plot_time_limit_shd_summary(
    summary: pd.DataFrame,
    output_png: Path,
    *,
    sample_size: int,
    d: int,
    solvers: list[str],
) -> None:
    fig, ax = plt.subplots(figsize=(9, 5.5))
    for solver_key in solvers:
        subset = summary[summary["solver_key"] == solver_key].sort_values("time_limit")
        if subset.empty:
            continue
        style = TIME_LIMIT_SOLVER_STYLES[solver_key]
        x = subset["time_limit"].to_numpy(dtype=float)
        y = subset["mean_shd"].to_numpy(dtype=float)
        sd = subset["sd_shd"].to_numpy(dtype=float)
        ax.plot(
            x,
            y,
            label=TIME_LIMIT_SOLVER_LABELS[solver_key],
            linewidth=1.8,
            **style,
        )
        ax.fill_between(x, y - sd, y + sd, color=style["color"], alpha=0.18, linewidth=0)

    ax.set_xlabel("Time limit (s)")
    ax.set_ylabel("SHD mean ± sd")
    ax.set_title(f"SF-5-0, d={d}, n={sample_size}")
    ax.grid(True, alpha=0.25)
    ax.legend(loc="upper left", bbox_to_anchor=(1.02, 1.0), frameon=True)
    fig.tight_layout(rect=(0, 0, 0.82, 1))
    output_png.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(output_png, dpi=200, bbox_inches="tight")
    plt.close(fig)


def plot_time_limit_f1_summary(
    summary: pd.DataFrame,
    output_png: Path,
    *,
    sample_size: int,
    d: int,
    solvers: list[str],
) -> None:
    fig, ax = plt.subplots(figsize=(9, 5.5))
    for solver_key in solvers:
        subset = summary[summary["solver_key"] == solver_key].sort_values("time_limit")
        if subset.empty or "mean_f1" not in subset.columns or not subset["mean_f1"].notna().any():
            continue
        style = TIME_LIMIT_SOLVER_STYLES[solver_key]
        x = subset["time_limit"].to_numpy(dtype=float)
        y = subset["mean_f1"].to_numpy(dtype=float)
        sd = subset["sd_f1"].to_numpy(dtype=float)
        ax.plot(x, y, label=TIME_LIMIT_SOLVER_LABELS[solver_key], linewidth=1.8, **style)
        ax.fill_between(x, y - sd, y + sd, color=style["color"], alpha=0.18, linewidth=0)

    ax.set_xlabel("Time limit (s)")
    ax.set_ylabel("F1 mean ± sd")
    ax.set_ylim(0.0, 1.02)
    ax.set_title(f"SF-5-0, d={d}, n={sample_size}")
    ax.grid(True, alpha=0.25)
    ax.legend(loc="upper left", bbox_to_anchor=(1.02, 1.0), frameon=True)
    fig.tight_layout(rect=(0, 0, 0.82, 1))
    output_png.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(output_png, dpi=200, bbox_inches="tight")
    plt.close(fig)


def smooth_xy(x: list[int], y: list[float]) -> tuple[np.ndarray, np.ndarray]:
    x_arr = np.asarray(x, dtype=float)
    y_arr = np.asarray(y, dtype=float)
    if len(x_arr) < 3:
        return x_arr, y_arr
    x_dense = np.linspace(x_arr.min(), x_arr.max(), 300)
    y_dense = PchipInterpolator(x_arr, y_arr)(x_dense)
    return x_dense, y_dense


def plot_edge_limit_summary(summary_csv: Path, output_png: Path, *, metric: str) -> None:
    rows_by_n = load_edge_limit_rows_for_plot(summary_csv, metric=metric)
    source_label = infer_edge_limit_source_label(summary_csv)

    plt.rcParams.update(
        {
            "font.size": 11,
            "axes.labelsize": 12,
            "axes.titlesize": 12,
            "legend.fontsize": 10,
            "xtick.labelsize": 10,
            "ytick.labelsize": 10,
        }
    )

    fig, ax = plt.subplots(figsize=(7.2, 4.8), dpi=300)
    style = {
        200: {"color": "#2B6CB0", "label": "200"},
        2000: {"color": "#D97706", "label": "2,000"},
    }

    for n in (200, 2000):
        rows = rows_by_n[n]
        if not rows:
            continue
        x = [d for d, _ in rows]
        y = [deg for _, deg in rows]
        x_smooth, y_smooth = smooth_xy(x, y)
        ax.plot(x_smooth, y_smooth, color=style[n]["color"], linewidth=2.0, label=style[n]["label"])
        baseline = 5 if metric == "degree" else 0
        ax.fill_between(x_smooth, baseline, y_smooth, color=style[n]["color"], alpha=0.10)

    if metric == "degree":
        ax.plot(
            [5, 35],
            [5, 35],
            linestyle=(0, (6, 4)),
            linewidth=1.3,
            color="#5B6472",
            alpha=0.95,
            dash_capstyle="round",
            zorder=1,
        )

    ax.set_xlabel("Number of nodes (d)")
    ax.set_ylabel(f"Stable degree of {source_label.upper()}" if metric == "degree" else "Stable GAP")
    xticks = sorted({d for rows in rows_by_n.values() for d, _ in rows})
    ax.set_xticks(xticks)
    ax.set_xlim(left=5)
    ax.set_ylim(bottom=(5 if metric == "degree" else 0))
    ax.grid(True, axis="y", color="#D9D9D9", linewidth=0.6, alpha=0.7)
    ax.grid(False, axis="x")
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.spines["left"].set_linewidth(0.9)
    ax.spines["bottom"].set_linewidth(0.9)
    ax.tick_params(axis="both", width=0.8, length=4)
    ax.legend(loc="upper left", frameon=False, handlelength=2.8)
    fig.tight_layout()

    output_png.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(output_png, bbox_inches="tight")
    plt.close(fig)


def powertick(value: float, _pos: float) -> str:
    if abs(value - round(value)) < 1e-9:
        return rf"$2^{{{int(round(value))}}}$"
    return rf"$2^{{{value:.1f}}}$"


def build_performance_profile_tables(df: pd.DataFrame, metric: str) -> tuple[pd.DataFrame, pd.DataFrame]:
    instance_columns = ["section", "samples", "seed", "number_of_variables"]
    cost_column = metric

    profile_source = df[instance_columns + ["solver", cost_column, "status"]].copy()
    profile_source["cost"] = np.where(
        profile_source["status"] == "ok",
        pd.to_numeric(profile_source[cost_column], errors="coerce"),
        np.inf,
    )

    ratio_rows: list[dict[str, Any]] = []
    for instance_key, group in profile_source.groupby(instance_columns, dropna=False):
        group = group[["solver", "cost"]].drop_duplicates(subset=["solver"], keep="last")
        finite_costs = group.loc[np.isfinite(group["cost"]), "cost"]
        best_cost = float(finite_costs.min()) if not finite_costs.empty else np.inf
        for row in group.itertuples(index=False):
            cost = float(row.cost)
            if np.isfinite(cost) and np.isfinite(best_cost):
                ratio = (cost + PROFILE_EPSILON) / (best_cost + PROFILE_EPSILON)
            else:
                ratio = np.inf
            ratio_rows.append(
                {
                    "section": instance_key[0],
                    "samples": instance_key[1],
                    "seed": instance_key[2],
                    "number_of_variables": instance_key[3],
                    "solver": row.solver,
                    "cost": cost,
                    "best_cost": best_cost,
                    "ratio": ratio,
                }
            )

    ratios_df = pd.DataFrame(ratio_rows)
    if ratios_df.empty:
        return ratios_df, pd.DataFrame(columns=["solver", "tau", "profile_value"])

    finite_ratios = ratios_df.loc[np.isfinite(ratios_df["ratio"]), "ratio"].to_numpy()
    if finite_ratios.size == 0:
        taus = np.array([1.0], dtype=float)
    else:
        taus = np.unique(np.concatenate(([1.0], finite_ratios)))
        taus.sort()

    profile_rows: list[dict[str, Any]] = []
    total_instances = ratios_df[instance_columns].drop_duplicates().shape[0]
    solver_names = sorted(ratios_df["solver"].dropna().unique().tolist())
    for solver_name in solver_names:
        solver_ratios = ratios_df.loc[ratios_df["solver"] == solver_name, "ratio"].to_numpy()
        for tau in taus:
            profile_rows.append(
                {
                    "solver": solver_name,
                    "tau": float(tau),
                    "profile_value": float(np.mean(solver_ratios <= tau)) if total_instances else np.nan,
                }
            )

    return ratios_df, pd.DataFrame(profile_rows)


def plot_performance_profile(
    profile_df: pd.DataFrame,
    metric: str,
    section: str,
    samples: int,
    output_path: Path,
    dpi: int,
) -> None:
    fig, ax = plt.subplots(figsize=(8, 5))
    style_map = {
        "cliquewidth": ("Clique Width", "#1f77b4"),
        "milp": ("MILP", "#ff7f0e"),
    }

    for solver_name in sorted(profile_df["solver"].dropna().unique().tolist()):
        solver_profile = profile_df[profile_df["solver"] == solver_name].sort_values("tau")
        if solver_profile.empty:
            continue
        label, color = style_map.get(solver_name, (solver_name, None))
        ax.step(
            solver_profile["tau"],
            solver_profile["profile_value"],
            where="post",
            linewidth=2,
            label=label,
            color=color,
        )

    ax.set_title(f"{section} performance profile at N={samples} ({metric})")
    ax.set_xscale("log", base=2)
    ax.xaxis.set_major_formatter(FuncFormatter(lambda x, _pos: rf"$2^{{{np.log2(x):g}}}$" if x > 0 else ""))
    ax.set_xlabel("Within this factor of the best (log scale)")
    ax.set_ylabel("Solved fraction ρ(τ)")
    ax.set_ylim(-0.05, 1.05)
    ax.set_yticks([0.0, 0.25, 0.5, 0.75, 1.0])
    ax.grid(True, linestyle="--", alpha=0.4)
    ax.legend()
    fig.tight_layout()
    fig.savefig(output_path, dpi=dpi)
    plt.close(fig)


def materialize_profile_outputs(
    df: pd.DataFrame,
    metric: str,
    run_dir: Path,
    section: str,
    samples: int,
    dpi: int,
) -> dict[str, Path]:
    metric_suffix = metric.replace("_seconds", "").replace("_", "_")
    profile_plot_path = run_dir / f"performance_profile_{metric_suffix}.png"
    profile_path = run_dir / f"performance_profile_{metric_suffix}.csv"
    profile_ratios_path = run_dir / f"performance_profile_{metric_suffix}_ratios.csv"

    ratios_df, profile_df = build_performance_profile_tables(df, metric)
    ratios_df.to_csv(profile_ratios_path, index=False)
    profile_df.to_csv(profile_path, index=False)
    plot_performance_profile(profile_df, metric, section, samples, profile_plot_path, dpi)

    return {
        f"profile_plot_{metric}": profile_plot_path,
        f"profile_{metric}": profile_path,
        f"profile_ratios_{metric}": profile_ratios_path,
    }


def plot_performance_from_exdbn_run_tables(
    *,
    table_dir: Path,
    run_dir: Path,
    scenario_key: str,
    samples: int,
    metric: str = "shd",
    output_suffix: str | None = None,
    dpi: int = 200,
    write_plot: bool = True,
    allowed_d_values: set[int] | None = None,
) -> dict[str, Path]:
    solver_patterns = (
        ("milp", f"runtime_static_{scenario_key}_gauss_d*_n{samples}*.csv"),
        ("cliquewidth", f"clique_runtime_static_{scenario_key}_gauss_d*_n{samples}*.csv"),
        ("edge_limit", f"limit_runtime_static_{scenario_key}_gauss_d*_n{samples}*.csv"),
    )
    style_map = {
        "milp": ("MILP", "#ff7f0e", "-"),
        "cliquewidth": ("Clique Width", "#1f77b4", "--"),
        "edge_limit": ("Edge Limit", "#2ca02c", "-."),
    }

    metric = metric.lower()
    if metric not in {"shd", "gap"}:
        raise ValueError(f"Unsupported metric '{metric}'. Expected 'shd' or 'gap'.")

    rows: list[dict[str, Any]] = []
    for solver_name, pattern in solver_patterns:
        for csv_path in sorted(table_dir.glob(pattern)):
            df = pd.read_csv(csv_path)
            if df.empty:
                continue
            d_series = first_numeric_series(df, ("features", "number_of_variables", "d")).dropna()
            metric_series = first_numeric_series(df, (metric, f"best_{metric}", f"min_{metric}")).dropna()
            if d_series.empty or metric_series.empty:
                continue
            selected_value = float(metric_series.min())
            if solver_name == "edge_limit":
                degree_series = first_numeric_series(df, ("degree", "repeat", "seed"))
                degree5_rows = df.loc[degree_series == 5]
                degree5_metric = first_numeric_series(degree5_rows, (metric, f"best_{metric}", f"min_{metric}")).dropna()
                if not degree5_metric.empty:
                    selected_value = float(degree5_metric.iloc[0])
            rows.append(
                {
                    "scenario": scenario_key,
                    "samples": int(samples),
                    "solver": solver_name,
                    "number_of_variables": int(d_series.iloc[0]),
                    "min_" + metric: selected_value,
                    "source_file": str(csv_path),
                }
            )

    summary = pd.DataFrame(rows).sort_values(["number_of_variables", "solver"]).reset_index(drop=True)
    if allowed_d_values is not None:
        summary = summary[summary["number_of_variables"].isin(sorted(allowed_d_values))].reset_index(drop=True)
    if summary.empty:
        raise RuntimeError(f"No EXDBN runtime tables found under {table_dir} for {scenario_key}, n={samples}")

    metric_col = f"min_{metric}"
    threshold_col = f"solver_mean_{metric}_threshold"
    thresholds = (
        summary.groupby("number_of_variables", as_index=False)[metric_col]
        .mean()
        .rename(columns={metric_col: threshold_col})
    )
    summary = summary.merge(thresholds, on="number_of_variables", how="left")
    summary["performance"] = (summary[metric_col] <= summary[threshold_col]).astype(int)

    run_dir.mkdir(parents=True, exist_ok=True)
    suffix = f"_{output_suffix}" if output_suffix else ""
    plot_path = run_dir / f"performance{suffix}.png"
    summary_path = run_dir / f"performance_summary{suffix}.csv"
    summary.to_csv(summary_path, index=False)

    if not write_plot:
        return {"summary": summary_path}

    fig, ax = plt.subplots(figsize=(10, 5))
    for solver_name in ("milp", "cliquewidth", "edge_limit"):
        solver_summary = summary[summary["solver"] == solver_name].sort_values("number_of_variables")
        if solver_summary.empty:
            continue
        label, color, linestyle = style_map[solver_name]
        ax.step(
            solver_summary["number_of_variables"],
            solver_summary["performance"],
            where="mid",
            linewidth=2,
            label=label,
            color=color,
            linestyle=linestyle,
            alpha=0.8,
        )

    ax.set_title(f"{scenario_key} performance at N={samples} ({metric})")
    ax.set_xlabel("d (number of nodes)")
    ax.set_ylabel("Performance")
    ax.set_ylim(-0.05, 1.05)
    ax.set_yticks([0.0, 0.25, 0.5, 0.75, 1.0])
    ax.grid(True, linestyle="--", alpha=0.4)
    ax.legend(
        loc="upper left",
        bbox_to_anchor=(1.02, 1.0),
        borderaxespad=0.8,
        frameon=True,
        fontsize=9,
        handlelength=2.0,
        borderpad=0.4,
        labelspacing=0.3,
    )
    fig.subplots_adjust(right=0.78)
    fig.tight_layout(pad=1.5, rect=(0, 0, 0.78, 1))
    fig.savefig(plot_path, dpi=dpi, bbox_inches="tight")
    plt.close(fig)

    return {"plot": plot_path, "summary": summary_path}


def plot_combined_performance_from_summaries(
    *,
    summary_paths: list[Path],
    output_plot: Path,
    output_summary: Path | None = None,
    dpi: int = 200,
) -> dict[str, Path]:
    style_map = {
        "milp": ("MILP", "#ff7f0e"),
        "cliquewidth": ("Clique Width", "#1f77b4"),
        "edge_limit": ("Edge Limit", "#2ca02c"),
    }
    sample_linestyles = {200: "--", 2000: "-"}

    frames: list[pd.DataFrame] = []
    for path in summary_paths:
        if not path.exists():
            continue
        df = pd.read_csv(path)
        if df.empty:
            continue
        frames.append(df)

    if not frames:
        raise RuntimeError("No non-empty performance summary CSVs were supplied")

    summary = pd.concat(frames, ignore_index=True)
    summary = summary.sort_values(["samples", "number_of_variables", "solver"]).reset_index(drop=True)

    sample_values = sorted(pd.to_numeric(summary["samples"], errors="coerce").dropna().astype(int).unique().tolist())
    summary["combined_problem"] = pd.to_numeric(summary["number_of_variables"], errors="coerce").astype(int)
    summary["problem_label"] = summary.apply(
        lambda row: f"d={int(row['number_of_variables'])}, n={int(row['samples'])}",
        axis=1,
    )

    output_plot.parent.mkdir(parents=True, exist_ok=True)
    if output_summary is not None:
        output_summary.parent.mkdir(parents=True, exist_ok=True)
        summary.to_csv(output_summary, index=False)

    scenario_values = [str(value) for value in summary["scenario"].dropna().unique().tolist()]
    scenario_label = scenario_values[0] if scenario_values else "Scenario"

    fig, axes = plt.subplots(
        1,
        len(sample_values),
        figsize=(5 * len(sample_values), 5),
        sharey=True,
        squeeze=False,
    )
    for ax, samples_value in zip(axes[0], sample_values):
        sample_summary = summary[summary["samples"] == samples_value]
        for solver_name in ("milp", "cliquewidth", "edge_limit"):
            solver_summary = sample_summary[sample_summary["solver"] == solver_name].sort_values("number_of_variables")
            if solver_summary.empty:
                continue
            label_base, color = style_map.get(solver_name, (solver_name, None))
            ax.step(
                solver_summary["combined_problem"],
                solver_summary["performance"],
                where="mid",
                linewidth=2,
                label=label_base,
                color=color,
                linestyle=sample_linestyles.get(int(samples_value), "-"),
                alpha=0.8,
            )

        ax.set_title(f"N={int(samples_value)}")
        ax.set_xlabel("d (number of nodes)")
        ax.set_ylim(-0.05, 1.05)
        ax.set_yticks([0.0, 0.25, 0.5, 0.75, 1.0])
        d_ticks = sorted(
            pd.to_numeric(sample_summary["number_of_variables"], errors="coerce").dropna().astype(int).unique().tolist()
        )
        ax.set_xticks(d_ticks)
        ax.set_xticklabels([str(d_value) for d_value in d_ticks], fontsize=9)
        ax.grid(True, linestyle="--", alpha=0.4)

    axes[0][0].set_ylabel("Performance")
    handles, labels = axes[0][-1].get_legend_handles_labels()
    if not handles:
        handles, labels = axes[0][0].get_legend_handles_labels()
    fig.suptitle(f"{scenario_label} performance (SHD)")
    fig.legend(
        handles,
        labels,
        loc="upper center",
        bbox_to_anchor=(0.5, 0.02),
        ncol=max(1, len(labels)),
        frameon=True,
        fontsize=9,
        handlelength=2.0,
        borderpad=0.4,
        labelspacing=0.3,
    )
    fig.tight_layout(pad=1.5, rect=(0, 0.08, 1, 0.94))
    fig.savefig(output_plot, dpi=dpi, bbox_inches="tight")
    plt.close(fig)

    outputs = {"plot": output_plot}
    if output_summary is not None:
        outputs["summary"] = output_summary
    return outputs


def performance_ratios(matrix: list[list[float]], *, logscale: bool = True, drawtol: float = 0.0) -> tuple[list[list[float]], float]:
    if not matrix:
        raise ValueError("Empty matrix")

    normalized: list[list[float]] = []
    saw_zero = any(any(value == 0 for value in row) for row in matrix)
    for row in matrix:
        normalized.append([float(value) + 1.0 if saw_zero else float(value) for value in row])

    for i, row in enumerate(normalized):
        for j, value in enumerate(row):
            if math.isinf(value) or math.isnan(value) or value < 0:
                normalized[i][j] = math.nan

    ratios: list[list[float]] = []
    for row in normalized:
        finite_values = [value for value in row if math.isfinite(value)]
        minperf = min(finite_values) if finite_values else math.nan
        row_ratios: list[float] = []
        for value in row:
            if math.isfinite(value) and math.isfinite(minperf) and minperf != 0:
                row_ratios.append(value / minperf)
            else:
                row_ratios.append(math.nan)
        ratios.append(row_ratios)

    if 0 < drawtol < 1:
        drawtol += 1.0
    if drawtol > 0:
        for i, row in enumerate(ratios):
            for j, value in enumerate(row):
                if math.isfinite(value) and value <= drawtol:
                    ratios[i][j] = 1.0

    if logscale:
        for i, row in enumerate(ratios):
            for j, value in enumerate(row):
                if math.isfinite(value) and value > 0:
                    ratios[i][j] = math.log2(value)

    finite_values = [value for row in ratios for value in row if math.isfinite(value)]
    if not finite_values:
        raise ValueError("No finite ratios found while building benchmark profiles")
    max_ratio = max(finite_values)

    for i, row in enumerate(ratios):
        for j, value in enumerate(row):
            if math.isnan(value):
                ratios[i][j] = 2.0 * max_ratio
    nsolvers = len(ratios[0]) if ratios else 0
    for j in range(nsolvers):
        ratios.sort(key=lambda row: row[j])
    return ratios, max_ratio


def performance_profile_data(
    matrix: list[list[float]],
    *,
    solver_order: tuple[str, ...],
    logscale: bool = True,
    sampletol: float = 0.0,
    drawtol: float = 0.0,
) -> tuple[list[list[float]], list[list[float]], float]:
    del sampletol
    ratios, max_ratio = performance_ratios(matrix, logscale=logscale, drawtol=drawtol)
    nsolvers = len(solver_order)
    nproblems = len(ratios)
    left_x = 0.0 if logscale else 1.0

    x_plot: list[list[float]] = [[] for _ in range(nsolvers)]
    y_plot: list[list[float]] = [[] for _ in range(nsolvers)]

    for solver_idx in range(nsolvers):
        solver_ratios = sorted(row[solver_idx] for row in ratios)
        unique_ratios = sorted(set(solver_ratios))
        if not unique_ratios:
            continue

        if unique_ratios[0] > left_x:
            x_plot[solver_idx].append(left_x)
            y_plot[solver_idx].append(0.0)

        for ratio in unique_ratios:
            solved = bisect_right(solver_ratios, ratio)
            x_plot[solver_idx].append(ratio)
            y_plot[solver_idx].append(solved / nproblems)

    return x_plot, y_plot, max_ratio


def export_profile_data(
    rows: list[dict[str, str]],
    output_dir: Path,
    metric: str,
    *,
    solver_order: tuple[str, ...],
    logscale: bool,
    mean_over_seeds: bool = False,
) -> Path:
    if not rows:
        raise ValueError("No rows supplied")

    matrix = build_metric_matrix(rows, metric, solver_order=solver_order, mean_over_seeds=mean_over_seeds)
    x_values, y_values, max_ratio = performance_profile_data(matrix, solver_order=solver_order, logscale=logscale)

    output_dir.mkdir(parents=True, exist_ok=True)
    out_path = output_dir / f"benchmarkprofiles_{metric}_data.csv"
    with out_path.open("w", newline="") as io:
        writer = csv.writer(io)
        writer.writerow(["metric", "solver_label", "solver_key", "x", "y", "max_ratio", "logscale", "mean_over_seeds"])
        for solver_idx, solver_key in enumerate(solver_order):
            solver_label = SOLVER_LABELS[solver_key]
            for x, y in zip(x_values[solver_idx], y_values[solver_idx], strict=True):
                writer.writerow(
                    [
                        metric,
                        solver_label,
                        solver_key,
                        x,
                        y,
                        max_ratio,
                        str(logscale).lower(),
                        str(mean_over_seeds).lower(),
                    ]
                )
    return out_path


def plot_profile(data_csv: Path, output_png: Path) -> None:
    rows = list(csv.DictReader(data_csv.open()))
    if not rows:
        raise ValueError(f"No rows found in {data_csv}")

    metric = rows[0]["metric"]
    logscale = str(rows[0].get("logscale", "True")).strip().lower() == "true"
    grouped: dict[str, list[dict[str, str]]] = defaultdict(list)
    labels: dict[str, str] = {}
    for row in rows:
        grouped[row["solver_key"]].append(row)
        labels[row["solver_key"]] = row["solver_label"]

    solver_order = tuple(solver for solver in BASE_SOLVER_ORDER if solver in grouped)

    fig, ax = plt.subplots(figsize=(8, 5))
    max_x = 0.0
    for solver_key in solver_order:
        solver_rows = grouped.get(solver_key)
        if not solver_rows:
            continue
        xs = [float(row["x"]) for row in solver_rows]
        ys = [float(row["y"]) for row in solver_rows]
        max_x = max(max_x, max(xs))
        ax.step(
            xs,
            ys,
            where="post",
            linewidth=2,
            color=SOLVER_COLORS.get(solver_key),
            linestyle=SOLVER_LINESTYLES.get(solver_key, "-"),
            label=labels.get(solver_key, solver_key),
        )

    if logscale:
        ax.xaxis.set_major_formatter(FuncFormatter(powertick))
        ax.set_xlim(left=0.0, right=max_x * 1.05 if max_x > 0 else 1.0)
        ax.set_xlabel("Within this factor of the best (log scale)")
    else:
        ax.set_xlim(left=1.0, right=max_x * 1.05 if max_x > 0 else 2.0)
        ax.set_xlabel("Within this factor of the best")

    ax.set_ylim(0.0, 1.1)
    ax.set_ylabel("Proportion of problems")
    ax.set_title(f"{METRIC_LABELS.get(metric, metric)} performance profile")
    ax.grid(True, alpha=0.25)
    ax.legend(loc="lower right")
    fig.tight_layout()
    output_png.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(output_png, dpi=200)
    plt.close(fig)
