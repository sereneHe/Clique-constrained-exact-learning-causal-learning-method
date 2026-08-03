#!/usr/bin/env python3
"""Build a compact, readable run-level summary for experiments A--G.

The former version expanded every MLflow metric and parameter into the CSV,
which produced hundreds of sparse columns.  This version keeps only the
identity, optimization, callback, constraint, and graph-quality quantities
used by the A--G comparisons.  Detailed diagnostics remain in their original
JSON/CSV files and are referenced by ``run_dir``.
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import os
import re
import sys
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

import yaml


STATUS_NAMES = {
    1: "RUNNING",
    2: "SCHEDULED",
    3: "FINISHED",
    4: "FAILED",
    5: "KILLED",
}
AG_EXPERIMENT_RE = re.compile(r"^METHOD_(?P<family>[A-G])(?:\d+)?(?:_|$)")


def read_yaml(path: Path) -> dict[str, Any]:
    try:
        data = yaml.safe_load(path.read_text())
    except (OSError, yaml.YAMLError) as exc:
        raise RuntimeError(f"Cannot read YAML {path}: {exc}") from exc
    return data if isinstance(data, dict) else {}


def read_scalar(path: Path) -> str:
    try:
        return path.read_text().strip()
    except OSError:
        return ""


def nested_get(data: dict[str, Any], dotted_key: str) -> Any:
    value: Any = data
    for part in dotted_key.split("."):
        if not isinstance(value, dict) or part not in value:
            return None
        value = value[part]
    return value


def first_present(*values: Any) -> Any:
    for value in values:
        if value is not None and str(value).strip() != "":
            return value
    return None


def normalized_number(value: Any) -> str | None:
    if value is None or str(value).strip() == "":
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return str(value)
    return str(int(number)) if number.is_integer() else str(number)


def as_float(value: Any) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def read_json(path: Path) -> dict[str, Any]:
    try:
        data = json.loads(path.read_text())
    except (OSError, json.JSONDecodeError):
        return {}
    return data if isinstance(data, dict) else {}


def hydra_run_dir(run: "HydraRun | None") -> Path | None:
    if run is None:
        return None
    return run.path.parent.parent if run.path.parent.name == ".hydra" else run.path.parent


def load_run_diagnostics(run: "HydraRun | None") -> tuple[dict[str, Any], dict[str, Any]]:
    """Load compact summary JSON and Gurobi callback totals for a Hydra run."""
    run_dir = hydra_run_dir(run)
    if run_dir is None:
        return {}, {}
    summaries = sorted(run_dir.glob("*_summary_diagnostics.json"))
    summary = read_json(summaries[0]) if summaries else {}
    callback: dict[str, Any] = {}
    log_path = run_dir / "run_experiments.log"
    if log_path.is_file():
        text = read_scalar(log_path)
        match = re.search(
            r"User-callback calls\s+(\d+),\s+time in user-callback\s+([0-9.]+) sec",
            text,
        )
        if match:
            callback = {
                "calls": int(match.group(1)),
                "seconds": float(match.group(2)),
            }
    return summary, callback


def graph_truth_summary(run: "HydraRun | None", mlflow_run_dir: Path | None = None) -> dict[str, Any]:
    """Summarize the *realized* synthetic graph, never the requested ratio.

    Clique-free generation may delete many edges, so ``edge_ratio`` is not a
    valid proxy for density.  W_true is the authoritative post-processing
    artifact.  Missing artifacts deliberately produce blank cells.
    """
    search_dirs = [path for path in (mlflow_run_dir, hydra_run_dir(run)) if path is not None]
    if not search_dirs:
        return {}
    candidates: list[Path] = []
    for run_dir in search_dirs:
        candidates += list(run_dir.glob("W_true.csv"))
        candidates += list(run_dir.glob("artifacts/W_true.csv"))
        candidates += list(run_dir.glob("output/W_true.csv"))
        candidates += list(run_dir.glob("outputs/W_true.csv"))
    if not candidates:
        for run_dir in search_dirs:
            candidates += list(run_dir.rglob("W_true.csv"))
    if not candidates:
        return {}
    matrix: list[list[float]] = []
    try:
        with candidates[0].open(newline="") as handle:
            for row in csv.reader(handle):
                matrix.append([float(value) for value in row if value.strip()])
    except (OSError, ValueError):
        return {}
    d = len(matrix)
    weights = [abs(value) for row in matrix for value in row if abs(value) > 1e-12]
    edges = len(weights)
    return {
        "true_edges": edges,
        # A DAG can contain at most one directed edge per unordered node pair;
        # use C(d,2), matching the density convention used in the PPT.
        "true_density_pct": 100.0 * edges / (d * (d - 1) / 2) if d > 1 else None,
        "true_mean_abs_w": sum(weights) / edges if edges else 0.0,
        "true_max_abs_w": max(weights, default=0.0),
    }


def latest_metric(path: Path) -> str:
    """Return the value from the latest timestamp/step in an MLflow metric file."""
    best: tuple[int, int, str] | None = None
    for line in read_scalar(path).splitlines():
        parts = line.split()
        if len(parts) < 2:
            continue
        try:
            timestamp = int(parts[0])
            step = int(parts[2]) if len(parts) >= 3 else 0
        except ValueError:
            continue
        candidate = (timestamp, step, parts[1])
        if best is None or candidate[:2] >= best[:2]:
            best = candidate
    return best[2] if best else ""


def locate_dagsolvers_roots(root: Path) -> list[Path]:
    """Find one or more ``dagsolvers`` directories below a supplied path.

    Besides an individual job directory, MetaCentrum results are commonly
    passed as a collection such as ``metacentrum_runs/`` containing many job
    directories.  Accept both forms so users do not need to enumerate jobs.
    """
    root = root.expanduser().resolve()
    candidates = [root, root / "dagsolvers"]
    for candidate in candidates:
        if (candidate / "mlruns").is_dir():
            return [candidate]

    if root.is_dir():
        # ``*/dagsolvers`` is the normal downloaded/remote job layout.  The
        # recursive search also covers an extra archive-directory level.
        found = {path.parent for path in root.glob("*/dagsolvers/mlruns")}
        if not found:
            found = {path.parent for path in root.rglob("dagsolvers/mlruns")}
        if found:
            return sorted(found)

    raise FileNotFoundError(
        f"No dagsolvers directory containing mlruns/ was found below {root}"
    )


def hydra_time_from_path(config_path: Path) -> float:
    match = re.search(
        r"multirun/(\d{4}-\d{2}-\d{2})/(\d{2}-\d{2}-\d{2})/(\d+)",
        config_path.as_posix(),
    )
    if not match:
        return config_path.stat().st_mtime
    date, clock, run_index = match.groups()
    try:
        timestamp = datetime.strptime(f"{date} {clock}", "%Y-%m-%d %H-%M-%S").timestamp()
    except ValueError:
        return config_path.stat().st_mtime
    return timestamp + int(run_index) * 1e-3


@dataclass
class HydraRun:
    path: Path
    config: dict[str, Any]
    experiment: str
    method_variant: str | None
    edge_ratio: str | None
    seed: str | None
    number_of_variables: str | None
    number_of_samples: str | None
    sort_time: float
    used: bool = False


def discover_hydra_runs(dagsolvers_root: Path) -> list[HydraRun]:
    discovered = set(dagsolvers_root.glob("multirun/**/.hydra/config.yaml"))
    discovered.update(dagsolvers_root.glob("multirun/**/[0-9]*/config.yaml"))
    # Synced runs may contain both Hydra's original .hydra/config.yaml and a
    # copied top-level config.yaml.  They describe the same logical run.
    by_run_dir: dict[Path, Path] = {}
    for path in discovered:
        run_dir = path.parent.parent if path.parent.name == ".hydra" else path.parent
        current = by_run_dir.get(run_dir)
        if current is None or path.parent.name == ".hydra":
            by_run_dir[run_dir] = path
    paths = set(by_run_dir.values())
    runs: list[HydraRun] = []
    for path in sorted(paths):
        config = read_yaml(path)
        experiment = str(config.get("experiment", ""))
        if not AG_EXPERIMENT_RE.match(experiment):
            continue
        runs.append(
            HydraRun(
                path=path,
                config=config,
                experiment=experiment,
                method_variant=(
                    str(nested_get(config, "solver.method_variant"))
                    if nested_get(config, "solver.method_variant") is not None
                    else None
                ),
                edge_ratio=normalized_number(
                    first_present(
                        nested_get(config, "problem.intra_edge_ratio"),
                        nested_get(config, "problem.edge_ratio"),
                    )
                ),
                seed=normalized_number(nested_get(config, "problem.seed")),
                number_of_variables=normalized_number(
                    nested_get(config, "problem.number_of_variables")
                ),
                number_of_samples=normalized_number(
                    nested_get(config, "problem.number_of_samples")
                ),
                sort_time=hydra_time_from_path(path),
            )
        )
    return runs


def candidate_matches(run: HydraRun, identity: dict[str, str | None]) -> bool:
    if run.used or run.experiment != identity["experiment"]:
        return False
    for field in (
        "method_variant",
        "edge_ratio",
        "seed",
        "number_of_variables",
        "number_of_samples",
    ):
        expected = identity.get(field)
        actual = getattr(run, field)
        if expected is not None and actual is not None and expected != actual:
            return False
    return True


def select_hydra_run(
    hydra_runs: list[HydraRun], identity: dict[str, str | None], start_time_ms: Any
) -> tuple[HydraRun | None, str]:
    candidates = [run for run in hydra_runs if candidate_matches(run, identity)]
    if not candidates:
        return None, "unmatched"
    try:
        start_seconds = float(start_time_ms) / 1000.0
    except (TypeError, ValueError):
        start_seconds = math.inf
    candidates.sort(key=lambda run: (abs(run.sort_time - start_seconds), run.sort_time))
    selected = candidates[0]
    selected.used = True
    return selected, "exact" if len(candidates) == 1 else "closest_time"


def load_file_store_run(run_dir: Path) -> tuple[dict[str, Any], dict[str, str], dict[str, str]]:
    meta = read_yaml(run_dir / "meta.yaml")
    params = {
        path.name: read_scalar(path)
        for path in sorted((run_dir / "params").glob("*"))
        if path.is_file()
    }
    metrics = {
        path.name: latest_metric(path)
        for path in sorted((run_dir / "metrics").glob("*"))
        if path.is_file()
    }
    return meta, params, metrics


def build_rows(dagsolvers_root: Path) -> tuple[list[dict[str, Any]], list[str]]:
    hydra_runs = discover_hydra_runs(dagsolvers_root)
    warnings: list[str] = []
    rows: list[dict[str, Any]] = []
    mlruns = dagsolvers_root / "mlruns"

    experiments: list[tuple[str, Path]] = []
    for experiment_meta in mlruns.glob("*/meta.yaml"):
        experiment = read_yaml(experiment_meta).get("name")
        if isinstance(experiment, str) and AG_EXPERIMENT_RE.match(experiment):
            experiments.append((experiment, experiment_meta.parent))

    raw_runs: list[tuple[int, str, Path, dict[str, Any], dict[str, str], dict[str, str]]] = []
    for experiment, experiment_dir in experiments:
        for run_meta_path in experiment_dir.glob("*/meta.yaml"):
            run_dir = run_meta_path.parent
            meta, params, metrics = load_file_store_run(run_dir)
            raw_runs.append(
                (
                    int(meta.get("start_time") or 0),
                    experiment,
                    run_dir,
                    meta,
                    params,
                    metrics,
                )
            )

    # Chronological matching makes fallback deterministic when params are absent.
    for _, experiment, run_dir, meta, params, metrics in sorted(raw_runs):
        identity = {
            "experiment": experiment,
            "method_variant": first_present(params.get("solver.method_variant")),
            "edge_ratio": normalized_number(
                first_present(
                    params.get("problem.intra_edge_ratio"),
                    params.get("effective_edge_ratio"),
                    params.get("problem.edge_ratio"),
                )
            ),
            "seed": normalized_number(params.get("problem.seed")),
            "number_of_variables": normalized_number(
                params.get("problem.number_of_variables")
            ),
            "number_of_samples": normalized_number(
                params.get("problem.number_of_samples")
            ),
        }
        hydra, match_type = select_hydra_run(hydra_runs, identity, meta.get("start_time"))
        config = hydra.config if hydra else {}
        summary, callback = load_run_diagnostics(hydra)
        truth = graph_truth_summary(hydra, run_dir)
        final = summary.get("final", {}) if isinstance(summary.get("final"), dict) else {}
        derived = (
            summary.get("derived_metrics", {})
            if isinstance(summary.get("derived_metrics"), dict)
            else {}
        )
        cut_attempts = (
            summary.get("cut_attempt_counts", {})
            if isinstance(summary.get("cut_attempt_counts"), dict)
            else {}
        )
        cut_unique = (
            summary.get("cut_unique_counts", {})
            if isinstance(summary.get("cut_unique_counts"), dict)
            else {}
        )
        cut_duplicates = (
            summary.get("cut_duplicate_counts", {})
            if isinstance(summary.get("cut_duplicate_counts"), dict)
            else {}
        )
        runtime = as_float(first_present(final.get("runtime"), metrics.get("runtime")))
        callback_seconds = as_float(callback.get("seconds"))
        callback_pct = (
            100.0 * callback_seconds / runtime
            if callback_seconds is not None and runtime and runtime > 0
            else None
        )
        search_seconds = (
            runtime - callback_seconds
            if runtime is not None and callback_seconds is not None
            else None
        )
        cycle_added = as_float(
            first_present(final.get("cycle_lazy_count"), metrics.get("cycle_lazy_added"))
        )
        clique_added = as_float(
            first_present(final.get("clique_lazy_count"), metrics.get("clique_lazy_added"))
        )
        user_cuts = as_float(
            first_present(final.get("clique_user_count"), metrics.get("clique_user_added"))
        )
        gap = as_float(first_present(final.get("gap"), metrics.get("mipgap")))
        root_records = summary.get("root_records", [])
        root = root_records[0] if isinstance(root_records, list) and root_records else {}
        progress: dict[str, Any] = {}
        hdir = hydra_run_dir(hydra)
        if hdir is not None:
            progress_files = sorted(hdir.glob("*_progress_diagnostics.csv"))
            if progress_files:
                try:
                    with progress_files[0].open(newline="") as handle:
                        progress_rows = list(csv.DictReader(handle))
                    if progress_rows:
                        progress = progress_rows[-1]
                except OSError:
                    pass
        violation_counts = (
            summary.get("violation_counts", {})
            if isinstance(summary.get("violation_counts"), dict)
            else {}
        )
        callback_costs = (
            summary.get("callback_costs", {})
            if isinstance(summary.get("callback_costs"), dict)
            else {}
        )

        family_match = AG_EXPERIMENT_RE.match(experiment)
        status_code = int(meta.get("status")) if meta.get("status") is not None else None
        edge_ratio = first_present(
            identity["edge_ratio"],
            normalized_number(nested_get(config, "problem.intra_edge_ratio")),
        )
        number_of_variables = first_present(
            identity["number_of_variables"],
            normalized_number(nested_get(config, "problem.number_of_variables")),
        )
        row: dict[str, Any] = {
            "status": STATUS_NAMES.get(status_code, str(status_code or "")),
            "method_family": family_match.group("family") if family_match else None,
            "method_variant": first_present(
                identity["method_variant"], nested_get(config, "solver.method_variant")
            ),
            "experiment": experiment,
            "edge_ratio": edge_ratio,
            "seed": first_present(
                identity["seed"], normalized_number(nested_get(config, "problem.seed"))
            ),
            "number_of_variables": number_of_variables,
            "number_of_samples": first_present(
                identity["number_of_samples"],
                normalized_number(nested_get(config, "problem.number_of_samples")),
            ),
            "true_edges": truth.get("true_edges"),
            "ori_skeleton_density": (
                2.0 * as_float(edge_ratio) / (as_float(number_of_variables) - 1)
                if as_float(edge_ratio) is not None
                and as_float(number_of_variables) is not None
                and as_float(number_of_variables) > 1 else None
            ),
            "after_cliquefree_skeleton_density": (
                2.0 * as_float(truth.get("true_edges")) /
                (as_float(number_of_variables) * (as_float(number_of_variables) - 1))
                if as_float(truth.get("true_edges")) is not None
                and as_float(number_of_variables) is not None
                and as_float(number_of_variables) > 1 else None
            ),
            "true_mean_abs_w": truth.get("true_mean_abs_w"),
            "big_m": as_float(summary.get("big_m")),
            "time_limit": first_present(
                nested_get(config, "solver.time_limit"), params.get("solver.time_limit")
            ),
            "runtime_s": runtime,
            # Final ObjVal is the global best accepted incumbent, not the last
            # candidate objective observed inside MIPSOL.
            "best_incumbent": as_float(final.get("objective")),
            "best_bound": as_float(final.get("best_bound")),
            "gap": gap,
            "gap_pct": 100.0 * gap if gap is not None else None,
            "nodes": as_float(final.get("node_count")),
            "nodes_per_s": as_float(final.get("nodes_per_second")),
            "lp_iter_per_node": as_float(derived.get("lp_iterations_per_node")),
            "lp_iter_per_s": as_float(derived.get("lp_iterations_per_second")),
            "root_bound": as_float(derived.get("initial_bound")),
            "bound_gain": as_float(derived.get("bound_gain")),
            "bound_gain_per_1k_nodes": as_float(
                derived.get("bound_gain_per_1000_nodes")
            ),
            "root_fractional_edges": as_float(root.get("fractional_edge_count")),
            "root_x_bins": (
                "|".join(str(int(as_float(root.get(key)) or 0)) for key in (
                    "x_le_001_count", "x_001_01_count", "x_01_05_count",
                    "x_05_099_count", "x_ge_099_count"))
                if root else None
            ),
            "root_small_x_large_w": as_float(root.get("small_x_large_w_001_01")),
            "root_mean_big_m_ratio": as_float(root.get("mean_big_m_ratio")),
            "root_violated_cliques": as_float(root.get("violated_clique_count")),
            "root_max_clique_violation": as_float(
                root.get("max_fractional_clique_violation")
            ),
            "callback_s": callback_seconds,
            "callback_pct": callback_pct,
            "search_s": search_seconds,
            "search_pct": 100.0 - callback_pct if callback_pct is not None else None,
            "mipsol_total": as_float(summary.get("mipsol_count")),
            "mipsol_rejected": as_float(summary.get("actual_mipsol_rejected_count")),
            "mipsol_accepted": as_float(summary.get("actual_mipsol_accepted_count")),
            "rejection_pct": (
                100.0 * as_float(derived.get("mipsol_rejection_rate"))
                if as_float(derived.get("mipsol_rejection_rate")) is not None
                else None
            ),
            "violation_overlap_pct": (
                100.0 * as_float(derived.get("violation_overlap_rate"))
                if as_float(derived.get("violation_overlap_rate")) is not None
                else None
            ),
            "cycle_only_candidates": as_float(violation_counts.get("cycle_only")),
            "clique_only_candidates": as_float(violation_counts.get("clique_only")),
            "both_candidates": as_float(violation_counts.get("both")),
            "cycle_cuts": cycle_added,
            "clique_cuts": clique_added,
            "user_cuts": user_cuts,
            "clique_user_count": user_cuts,
            "total_cuts": sum(
                value for value in (cycle_added, clique_added, user_cuts)
                if value is not None
            ),
            "unique_cuts": sum(
                as_float(cut_unique.get(kind)) or 0.0 for kind in ("cycle", "clique")
            ),
            "cycle_unique_cuts": as_float(cut_unique.get("cycle")),
            "clique_unique_cuts": as_float(cut_unique.get("clique")),
            "cycle_duplicate_cuts": as_float(cut_duplicates.get("cycle")),
            "clique_duplicate_cuts": as_float(cut_duplicates.get("clique")),
            "duplicate_cuts": sum(
                as_float(cut_duplicates.get(kind)) or 0.0
                for kind in ("cycle", "clique")
            ),
            "cut_hit_pct": (
                100.0 * as_float(derived.get("cut_hit_rate"))
                if as_float(derived.get("cut_hit_rate")) is not None
                else None
            ),
            "dual_gain_per_cut": as_float(derived.get("dual_gain_per_cut")),
            "dual_gain_per_s": as_float(derived.get("dual_gain_per_second")),
            "cycle_callback_s": (
                sum(as_float(callback_costs.get(key)) or 0.0 for key in
                    ("cycle_detection_time", "cycle_submission_time"))
                if callback_costs else None
            ),
            "clique_callback_s": (
                sum(as_float(callback_costs.get(key)) or 0.0 for key in
                    ("clique_detection_time", "clique_submission_time"))
                if callback_costs else None
            ),
            "open_nodes": as_float(progress.get("open_nodes")),
            "solution_count": as_float(final.get("solution_count")),
            "shd": as_float(
                first_present(final.get("final_shd_at_solver_threshold"), metrics.get("best_shd"))
            ),
            "f1": as_float(
                first_present(final.get("final_f1_at_solver_threshold"), metrics.get("best_f1score"))
            ),
            "g_score": as_float(metrics.get("best_g_score")),
            "nnz": as_float(metrics.get("best_nnz")),
            "run_dir": str(
                (hydra_run_dir(hydra) or run_dir).relative_to(dagsolvers_root)
                if (hydra_run_dir(hydra) or run_dir).is_relative_to(dagsolvers_root)
                else (hydra_run_dir(hydra) or run_dir)
            ),
        }
        rows.append(row)

        if hydra is None:
            warnings.append(f"No Hydra match for {experiment} run {run_dir.name}")
        if not metrics:
            warnings.append(f"No MLflow metrics downloaded for {experiment} run {run_dir.name}")
        if not params:
            warnings.append(f"No MLflow params downloaded for {experiment} run {run_dir.name}")

    for run in hydra_runs:
        if not run.used:
            warnings.append(f"No MLflow match for Hydra run {run.path}")
    return rows, warnings


def write_csv(rows: list[dict[str, Any]], output: Path) -> None:
    if not rows:
        raise SystemExit("No METHOD_A ... METHOD_G MLflow runs found")
    fields = [
        "status",
        "method_family",
        "method_variant",
        "experiment",
        "edge_ratio",
        "seed",
        "number_of_variables",
        "number_of_samples",
        "true_edges",
        "ori_skeleton_density",
        "after_cliquefree_skeleton_density",
        "true_mean_abs_w",
        "big_m",
        "time_limit",
        "runtime_s",
        "best_incumbent",
        "best_bound",
        "gap",
        "gap_pct",
        "nodes",
        "nodes_per_s",
        "lp_iter_per_node",
        "lp_iter_per_s",
        "root_bound",
        "bound_gain",
        "bound_gain_per_1k_nodes",
        "root_fractional_edges",
        "root_x_bins",
        "root_small_x_large_w",
        "root_mean_big_m_ratio",
        "root_violated_cliques",
        "root_max_clique_violation",
        "callback_s",
        "callback_pct",
        "search_s",
        "search_pct",
        "mipsol_total",
        "mipsol_rejected",
        "mipsol_accepted",
        "rejection_pct",
        "violation_overlap_pct",
        "cycle_only_candidates",
        "clique_only_candidates",
        "both_candidates",
        "cycle_cuts",
        "clique_cuts",
        "user_cuts",
        "clique_user_count",
        "total_cuts",
        "unique_cuts",
        "duplicate_cuts",
        "cycle_unique_cuts",
        "clique_unique_cuts",
        "cycle_duplicate_cuts",
        "clique_duplicate_cuts",
        "cut_hit_pct",
        "dual_gain_per_cut",
        "dual_gain_per_s",
        "cycle_callback_s",
        "clique_callback_s",
        "open_nodes",
        "solution_count",
        "shd",
        "f1",
        "g_score",
        "nnz",
        "run_dir",
    ]
    output.parent.mkdir(parents=True, exist_ok=True)
    integer_fields = {
        "seed", "number_of_variables", "number_of_samples", "true_edges",
        "mipsol_total", "mipsol_rejected", "mipsol_accepted",
        "cycle_only_candidates", "clique_only_candidates", "both_candidates",
        "root_fractional_edges", "root_small_x_large_w",
        "root_violated_cliques", "cycle_cuts", "clique_cuts", "user_cuts",
        "clique_user_count",
        "total_cuts", "unique_cuts", "duplicate_cuts", "shd", "nnz",
        "cycle_unique_cuts", "clique_unique_cuts",
        "cycle_duplicate_cuts", "clique_duplicate_cuts",
        "open_nodes", "solution_count",
    }
    three_decimal_fields = {
        "runtime_s", "callback_s", "callback_pct", "search_s", "search_pct",
        "nodes_per_s", "lp_iter_per_node", "rejection_pct", "cut_hit_pct",
        "lp_iter_per_s", "violation_overlap_pct",
        "ori_skeleton_density", "after_cliquefree_skeleton_density",
        "cycle_callback_s", "clique_callback_s",
    }
    six_decimal_fields = {
        "best_incumbent", "best_bound", "gap", "gap_pct", "root_bound",
        "dual_gain_per_cut", "dual_gain_per_s", "f1", "g_score",
        "true_mean_abs_w", "big_m", "bound_gain", "bound_gain_per_1k_nodes",
        "root_max_clique_violation",
        "root_mean_big_m_ratio",
    }
    formatted_rows: list[dict[str, Any]] = []
    for row in rows:
        formatted = dict(row)
        for field in integer_fields:
            value = as_float(formatted.get(field))
            if value is not None:
                formatted[field] = str(int(round(value)))
        for field in three_decimal_fields:
            value = as_float(formatted.get(field))
            if value is not None:
                formatted[field] = f"{value:.3f}"
        for field in six_decimal_fields:
            value = as_float(formatted.get(field))
            if value is not None:
                formatted[field] = f"{value:.6f}"
        value = as_float(formatted.get("nodes"))
        if value is not None:
            formatted["nodes"] = str(int(round(value)))
        formatted_rows.append(formatted)
    with output.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(formatted_rows)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Summarize METHOD_A ... METHOD_G runs from MLflow and Hydra"
    )
    parser.add_argument(
        "roots",
        nargs="+",
        help=(
            "dagsolvers directories, job directories, or a metacentrum_runs/ "
            "collection containing job directories"
        ),
    )
    parser.add_argument("--output", default="ag_runs_summary.csv")
    parser.add_argument(
        "--strict",
        action="store_true",
        help="return a non-zero exit code when matches/data are incomplete",
    )
    args = parser.parse_args()

    all_rows: list[dict[str, Any]] = []
    all_warnings: list[str] = []
    for root_arg in args.roots:
        for dagsolvers_root in locate_dagsolvers_roots(Path(root_arg)):
            rows, warnings = build_rows(dagsolvers_root)
            all_rows.extend(rows)
            all_warnings.extend(warnings)

    all_rows.sort(
        key=lambda row: (
            str(row.get("edge_ratio") or ""),
            str(row.get("method_family") or ""),
            str(row.get("method_variant") or ""),
            str(row.get("experiment") or ""),
            float(row.get("seed") or 0),
            int(row.get("start_time_ms") or 0),
        )
    )
    output = Path(args.output).expanduser().resolve()
    write_csv(all_rows, output)

    status_counts: dict[str, int] = defaultdict(int)
    for row in all_rows:
        status_counts[str(row.get("status"))] += 1
    print(f"Wrote {len(all_rows)} A--G runs to {output}")
    print("Statuses: " + ", ".join(f"{k}={v}" for k, v in sorted(status_counts.items())))
    print(f"Warnings: {len(all_warnings)}")
    for warning in all_warnings:
        print(f"WARNING: {warning}", file=sys.stderr)
    if args.strict and all_warnings:
        raise SystemExit(2)


if __name__ == "__main__":
    raise SystemExit(
        "Standalone ag_runs_summary.csv generation is disabled; "
        "A--G rows are written directly to results/.../clique_runtime_*.csv."
    )
