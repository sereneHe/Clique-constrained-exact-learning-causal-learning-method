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

AG_OUTPUT_COLUMNS = [
    "dataset", "features", "samples", "p", "edge_ratio", "degree",
    "ori_graph_density", "after_cliquefree_density", "true_linear_r2",
    "big_m", "runtime_seconds", "gap", "shd", "f1score",
    "cycle_lazy_cuts", "clique_lazy_cuts", "clique_user_cuts",
    "cycle_unique_cuts", "clique_unique_cuts", "cycle_duplicate_cuts",
    "clique_duplicate_cuts", "unique_cuts", "duplicate_cuts", "cut_hit_pct",
    "status", "experiment", "method_family", "method_variant", "seed",
    "time_limit", "true_edges", "true_mean_abs_w", "best_incumbent",
    "best_bound", "root_bound", "bound_gain", "explored_nodes", "open_nodes",
    "nodes_per_s", "solution_count", "g_score", "nnz", "fdr", "tpr", "fpr",
    "precision", "mipsol_total", "mipsol_rejected", "mipsol_accepted",
    "mipsol_rejection_pct", "cycle_only_candidates", "clique_only_candidates",
    "both_candidates", "violation_overlap_pct", "cycle_callback_count",
    "clique_callback_count", "cycle_separation_attempts",
    "clique_separation_attempts", "root_fractional_edges",
    "root_fractional_x_bins", "root_small_x_large_w", "root_mean_big_m_ratio",
    "root_violated_cliques", "root_max_clique_violation",
    "bound_gain_per_1k_nodes", "dual_gain_per_cut", "dual_gain_per_s",
    "mipnode_total", "lp_iterations", "lp_iter_per_node", "lp_iter_per_s",
    "callback_s", "callback_pct", "search_s", "cycle_callback_s",
    "clique_callback_s", "cycle_detection_s", "cycle_submission_s",
    "clique_detection_s", "clique_submission_s", "mip_progress_times",
    "checkpoint_explored_nodes", "checkpoint_open_nodes",
    "checkpoint_best_bound", "checkpoint_incumbent", "checkpoint_gap",
    "checkpoint_status", "checkpoint_solution_count", "checkpoint_DAG",
    "checkpoint_SHD", "checkpoint_F1", "checkpoint_NNZ",
    "best_incumbent_edges", "best_incumbent_weights", "W_true_path", "run_dir",
]


def experiment_family(experiment: str) -> str | None:
    match = AG_EXPERIMENT_RE.match(experiment)
    if match:
        return match.group("family")
    # B/F now share the clique-separation implementation and are selected by
    # environment variables rather than legacy METHOD_B/METHOD_F aliases.
    if experiment.startswith("CLIQUE_SEPERATION_"):
        return "B/F"
    if experiment.startswith("CALLBACK_1800_"):
        return "CALLBACK"
    unified_names = {
        "CLIQUEWIDTH-original_control": "CONTROL",
        "CLIQUE": "BASE",
        "B1-first_min_k+1-F2-first_k+1_cut": "B/F",
        "B3-most_violated_k+1": "B",
        "C3-local_LS_QR_repair": "C",
        "C5-validated_auto_refit_retry": "C",
        "E2-big_M_20": "E",
    }
    if experiment in unified_names:
        return unified_names[experiment]
    return None


def callback_method_variant(experiment: str, config: dict[str, Any]) -> str | None:
    explicit = nested_get(config, "solver.method_variant")
    if explicit is not None:
        return str(explicit)
    names = {
        "CALLBACK_1800_CYCLE_ONLY": "cycle_only",
        "CALLBACK_1800_CLIQUE_ONLY": "clique_only",
        "CALLBACK_1800_CYCLE_FIRST": "cycle_early",
        "CALLBACK_1800_CLIQUE_FIRST": "clique_early",
        "CALLBACK_1800_CYCLE_EARLY": "cycle_early",
        "CALLBACK_1800_CLIQUE_EARLY": "clique_early",
        "CALLBACK_1800_CYCLE_THEN_CLIQUE": "cycle_then_clique",
        "CALLBACK_1800_CLIQUE_THEN_CYCLE": "clique_then_cycle",
    }
    return names.get(experiment)


def include_experiment(experiment: str, experiment_prefix: str | None) -> bool:
    if experiment_prefix is not None:
        return experiment.startswith(experiment_prefix)
    return experiment_family(experiment) is not None


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


def read_numeric_csv(path: Path) -> list[list[float]]:
    try:
        with path.open(newline="") as handle:
            return [
                [float(value) for value in row if value.strip()]
                for row in csv.reader(handle)
            ]
    except (OSError, ValueError):
        return []


def true_linear_r2_from_artifacts(run_dir: Path | None) -> float | None:
    if run_dir is None:
        return None
    x = read_numeric_csv(run_dir / "X.csv")
    w = read_numeric_csv(run_dir / "W_true.csv")
    if not x or not w or len(w) != len(w[0]) or any(len(row) != len(w) for row in w):
        return None
    d = len(w)
    if any(len(row) != d for row in x):
        return None
    scores: list[float] = []
    for node in range(d):
        if not any(abs(w[parent][node]) > 1e-12 for parent in range(d)):
            continue
        observed = [row[node] for row in x]
        predicted = [sum(row[parent] * w[parent][node] for parent in range(d)) for row in x]
        observed_mean = sum(observed) / len(observed)
        denominator = sum((value - observed_mean) ** 2 for value in observed)
        if denominator:
            scores.append(1.0 - sum((a - b) ** 2 for a, b in zip(observed, predicted)) / denominator)
    return sum(scores) / len(scores) if scores else None


def incumbent_snapshot_from_artifacts(run_dir: Path | None) -> tuple[str | None, str | None]:
    if run_dir is None:
        return None, None
    matrix = read_numeric_csv(run_dir / "W_est.csv")
    if not matrix:
        return None, None
    edges: list[list[int]] = []
    weights: list[float] = []
    for source, row in enumerate(matrix):
        for target, value in enumerate(row):
            if abs(value) > 1e-3:
                edges.append([source, target])
                weights.append(value)
    return json.dumps(edges, separators=(",", ":")), json.dumps(weights, separators=(",", ":"))


def accuracy_from_artifacts(run_dir: Path | None) -> dict[str, float]:
    if run_dir is None:
        return {}
    truth = read_numeric_csv(run_dir / "W_true.csv")
    estimate = read_numeric_csv(run_dir / "W_est.csv")
    if not truth or not estimate or len(truth) != len(estimate):
        return {}
    positive = {
        (i, j) for i, row in enumerate(truth) for j, value in enumerate(row)
        if abs(value) > 1e-12
    }
    predicted = {
        (i, j) for i, row in enumerate(estimate) for j, value in enumerate(row)
        if abs(value) > 1e-3
    }
    true_positive = len(positive & predicted)
    false_positive = len(predicted - positive)
    false_negative = len(positive - predicted)
    d = len(truth)
    precision = true_positive / max(len(predicted), 1)
    tpr = true_positive / max(len(positive), 1)
    return {
        "fdr": false_positive / max(len(predicted), 1),
        "tpr": tpr,
        "fpr": false_positive / max(d * d - len(positive), 1),
        "precision": precision,
        "f1": 2 * tpr * precision / max(tpr + precision, 1),
        "g_score": max(true_positive - false_positive, 0) / max(len(positive), 1),
        "nnz": float(len(predicted)),
        "shd": float(false_positive + false_negative),
    }


def parse_gurobi_progress(text: str) -> dict[str, Any]:
    """Recover fields printed by Gurobi even when diagnostics JSON is absent."""
    root_match = re.search(r"Root relaxation: objective ([0-9.eE+-]+)", text)
    records: list[dict[str, Any]] = []
    for line in text.splitlines():
        payload = line.rsplit(" - ", 1)[-1].strip()
        parts = payload.split()
        if parts and parts[0] in {"H", "*"}:
            parts = parts[1:]
        if len(parts) < 8 or not parts[-1].endswith("s") or not parts[-3].endswith("%"):
            continue
        try:
            explored = int(parts[0])
            opened = int(parts[1])
            incumbent = float(parts[-5])
            bound = float(parts[-4])
            gap = float(parts[-3][:-1]) / 100.0
            runtime = float(parts[-1][:-1])
        except ValueError:
            continue
        records.append({
            "runtime": runtime,
            "explored_nodes": explored,
            "open_nodes": opened,
            "best_incumbent": incumbent,
            "best_bound": bound,
            "gap": gap,
        })
    return {
        "root_bound": float(root_match.group(1)) if root_match else None,
        "records": records,
        "open_nodes": records[-1]["open_nodes"] if records else None,
    }


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
        # Legacy callback-order runs did not write summary diagnostics, but
        # Gurobi's final log still contains authoritative optimization values.
        # Recover those values instead of leaving otherwise recoverable CSV
        # columns blank.  Do not synthesize callback diagnostics that were not
        # printed by the original run.
        if not isinstance(summary.get("final"), dict):
            explored = re.findall(
                r"Explored (\d+) nodes \((\d+) simplex iterations\) in ([0-9.]+) seconds",
                text,
            )
            objective = re.findall(
                r"Best objective ([0-9.eE+-]+), best bound ([0-9.eE+-]+), gap ([0-9.]+)%",
                text,
            )
            solution_counts = re.findall(r"Solution count (\d+)", text)
            if explored and objective:
                nodes, iterations, runtime = explored[-1]
                incumbent, bound, gap_pct = objective[-1]
                runtime_value = float(runtime)
                node_value = float(nodes)
                iteration_value = float(iterations)
                summary["final"] = {
                    "runtime": runtime_value,
                    "objective": float(incumbent),
                    "best_bound": float(bound),
                    "gap": float(gap_pct) / 100.0,
                    "node_count": node_value,
                    "simplex_iteration_count": iteration_value,
                    "mipnode_total": int(node_value),
                    "nodes_per_second": node_value / runtime_value if runtime_value else None,
                    "solution_count": int(solution_counts[-1]) if solution_counts else None,
                }
                summary["derived_metrics"] = {
                    "lp_iterations_per_node": (
                        iteration_value / node_value if node_value else None
                    ),
                    "lp_iterations_per_second": (
                        iteration_value / runtime_value if runtime_value else None
                    ),
                }
        callback["solver_finished"] = "SOLVER FINISHED" in text
        summary["gurobi_log_recovery"] = parse_gurobi_progress(text)
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


def discover_hydra_runs(
    dagsolvers_root: Path, experiment_prefix: str | None = None
) -> list[HydraRun]:
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
        if not include_experiment(experiment, experiment_prefix):
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


def load_combined_callback_summaries(dagsolvers_root: Path) -> dict[str, dict[str, Any]]:
    """Recover callback totals printed only to the parent/nohup log.

    Hydra's per-run ``run_experiments.log`` contains Gurobi output, while the
    legacy callback summary was printed by the runner to the combined stdout
    log.  Match each summary to its preceding absolute run directory.
    """
    recovered: dict[str, dict[str, Any]] = {}
    pattern = re.compile(
        r"Starting experiment in (?P<run_dir>[^\r\n]+).*?"
        r"\[CALLBACK-SUMMARY\] "
        r"mipsol_total=(?P<total>\d+) "
        r"mipsol_rejected=(?P<rejected>\d+) "
        r"mipsol_accepted=(?P<accepted>\d+) "
        r"cycle_constraints_added=(?P<cycle>\d+) "
        r"clique_constraints_added=(?P<clique>\d+) "
        r"cycle_filter_seconds=(?P<cycle_filter>[0-9.eE+-]+) "
        r"cycle_add_seconds=(?P<cycle_add>[0-9.eE+-]+) "
        r"clique_filter_seconds=(?P<clique_filter>[0-9.eE+-]+) "
        r"clique_add_seconds=(?P<clique_add>[0-9.eE+-]+).*?"
        r"solve_after_last_constraint_seconds=(?P<after>[0-9.eE+-]+)",
        re.DOTALL,
    )
    for log_path in sorted((dagsolvers_root / "logs").glob("*.log")):
        text = read_scalar(log_path)
        for match in pattern.finditer(text):
            run_dir = str(Path(match.group("run_dir").strip()).resolve())
            total = int(match.group("total"))
            rejected = int(match.group("rejected"))
            accepted = int(match.group("accepted"))
            recovered[run_dir] = {
                "mipsol_count": total,
                "actual_mipsol_rejected_count": rejected,
                "actual_mipsol_accepted_count": accepted,
                "cut_attempt_counts": {
                    "cycle": int(match.group("cycle")),
                    "clique": int(match.group("clique")),
                },
                "callback_costs": {
                    "cycle_detection_time": float(match.group("cycle_filter")),
                    "cycle_submission_time": float(match.group("cycle_add")),
                    "clique_detection_time": float(match.group("clique_filter")),
                    "clique_submission_time": float(match.group("clique_add")),
                },
                "derived_metrics": {
                    "mipsol_rejection_rate": rejected / total if total else 0.0,
                },
            }
    return recovered


def build_rows(
    dagsolvers_root: Path, experiment_prefix: str | None = None
) -> tuple[list[dict[str, Any]], list[str]]:
    hydra_runs = discover_hydra_runs(dagsolvers_root, experiment_prefix)
    combined_callback = load_combined_callback_summaries(dagsolvers_root)
    warnings: list[str] = []
    rows: list[dict[str, Any]] = []
    mlruns = dagsolvers_root / "mlruns"

    experiments: list[tuple[str, Path]] = []
    for experiment_meta in mlruns.glob("*/meta.yaml"):
        experiment = read_yaml(experiment_meta).get("name")
        if isinstance(experiment, str) and include_experiment(
            experiment, experiment_prefix
        ):
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
        selected_run_dir = hydra_run_dir(hydra)
        recovered_callback = (
            combined_callback.get(str(selected_run_dir.resolve()))
            if selected_run_dir is not None else None
        )
        if recovered_callback:
            for key in (
                "mipsol_count", "actual_mipsol_rejected_count",
                "actual_mipsol_accepted_count",
            ):
                summary.setdefault(key, recovered_callback.get(key))
            for key in (
                "cut_attempt_counts", "callback_costs", "derived_metrics"
            ):
                current = summary.get(key)
                if not isinstance(current, dict):
                    current = {}
                    summary[key] = current
                for nested_key, nested_value in recovered_callback.get(key, {}).items():
                    current.setdefault(nested_key, nested_value)
        truth = graph_truth_summary(hydra, run_dir)
        artifact_dir = hydra_run_dir(hydra)
        true_linear_r2 = true_linear_r2_from_artifacts(artifact_dir)
        incumbent_edges, incumbent_weights = incumbent_snapshot_from_artifacts(artifact_dir)
        artifact_accuracy = accuracy_from_artifacts(artifact_dir)
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
        log_recovery = (
            summary.get("gurobi_log_recovery", {})
            if isinstance(summary.get("gurobi_log_recovery"), dict)
            else {}
        )
        log_progress = (
            log_recovery.get("records", [])
            if isinstance(log_recovery.get("records"), list)
            else []
        )

        family = experiment_family(experiment)
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
            "method_family": family,
            "dataset": first_present(
                nested_get(config, "problem.name"), params.get("problem.name")
            ),
            "p": first_present(nested_get(config, "problem.p"), params.get("problem.p")),
            "method_variant": first_present(
                identity["method_variant"], callback_method_variant(experiment, config)
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
            "true_linear_r2": true_linear_r2,
            "big_m": as_float(first_present(
                summary.get("big_m"), nested_get(config, "solver.weights_bound")
            )),
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
            "mipnode_total": as_float(final.get("mipnode_total")),
            "lp_iterations": as_float(final.get("simplex_iteration_count")),
            "lp_iter_per_node": as_float(derived.get("lp_iterations_per_node")),
            "lp_iter_per_s": as_float(derived.get("lp_iterations_per_second")),
            "root_bound": as_float(first_present(
                derived.get("initial_bound"), log_recovery.get("root_bound")
            )),
            "bound_gain": as_float(first_present(
                derived.get("bound_gain"),
                (
                    as_float(final.get("best_bound")) - as_float(log_recovery.get("root_bound"))
                    if as_float(final.get("best_bound")) is not None
                    and as_float(log_recovery.get("root_bound")) is not None
                    else None
                ),
            )),
            "bound_gain_per_1k_nodes": as_float(
                first_present(
                    derived.get("bound_gain_per_1000_nodes"),
                    (
                        1000.0 * (
                            as_float(final.get("best_bound")) - as_float(log_recovery.get("root_bound"))
                        ) / as_float(final.get("node_count"))
                        if as_float(final.get("best_bound")) is not None
                        and as_float(log_recovery.get("root_bound")) is not None
                        and as_float(final.get("node_count"))
                        else None
                    ),
                )
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
            "open_nodes": as_float(first_present(
                progress.get("open_nodes"), log_recovery.get("open_nodes")
            )),
            "solution_count": as_float(final.get("solution_count")),
            "shd": as_float(
                first_present(final.get("final_shd_at_solver_threshold"), metrics.get("best_shd"), artifact_accuracy.get("shd"))
            ),
            "f1": as_float(
                first_present(final.get("final_f1_at_solver_threshold"), metrics.get("best_f1score"), artifact_accuracy.get("f1"))
            ),
            "g_score": as_float(first_present(metrics.get("best_g_score"), artifact_accuracy.get("g_score"))),
            "nnz": as_float(first_present(metrics.get("best_nnz"), artifact_accuracy.get("nnz"))),
            "fdr": as_float(artifact_accuracy.get("fdr")),
            "tpr": as_float(artifact_accuracy.get("tpr")),
            "fpr": as_float(artifact_accuracy.get("fpr")),
            "precision": as_float(artifact_accuracy.get("precision")),
            "cycle_detection_s": as_float(
                callback_costs.get("cycle_detection_time")
            ),
            "cycle_submission_s": as_float(
                callback_costs.get("cycle_submission_time")
            ),
            "clique_detection_s": as_float(
                callback_costs.get("clique_detection_time")
            ),
            "clique_submission_s": as_float(
                callback_costs.get("clique_submission_time")
            ),
            "cycle_callback_count": as_float(
                (summary.get("callbacks_with_cuts") or {}).get("cycle")
            ),
            "clique_callback_count": as_float(
                (summary.get("callbacks_with_cuts") or {}).get("clique")
            ),
            "cycle_separation_attempts": as_float(
                (summary.get("separation_attempt_counts") or {}).get("cycle")
            ),
            "clique_separation_attempts": as_float(
                (summary.get("separation_attempt_counts") or {}).get("clique")
            ),
            "mip_progress_times": json.dumps(
                [record.get("runtime") for record in log_progress], separators=(",", ":")
            ) if log_progress else None,
            "checkpoint_explored_nodes": json.dumps(
                [record.get("explored_nodes") for record in log_progress], separators=(",", ":")
            ) if log_progress else None,
            "checkpoint_open_nodes": json.dumps(
                [record.get("open_nodes") for record in log_progress], separators=(",", ":")
            ) if log_progress else None,
            "checkpoint_best_bound": json.dumps(
                [record.get("best_bound") for record in log_progress], separators=(",", ":")
            ) if log_progress else None,
            "checkpoint_incumbent": json.dumps(
                [record.get("best_incumbent") for record in log_progress], separators=(",", ":")
            ) if log_progress else None,
            "checkpoint_gap": json.dumps(
                [record.get("gap") for record in log_progress], separators=(",", ":")
            ) if log_progress else None,
            "best_incumbent_edges": incumbent_edges,
            "best_incumbent_weights": incumbent_weights,
            "W_true_path": str(artifact_dir / "W_true.csv") if artifact_dir and (artifact_dir / "W_true.csv").is_file() else None,
            "run_dir": str(
                (hydra_run_dir(hydra) or run_dir).relative_to(dagsolvers_root)
                if (hydra_run_dir(hydra) or run_dir).is_relative_to(dagsolvers_root)
                else (hydra_run_dir(hydra) or run_dir)
            ),
        }
        if callback.get("solver_finished") and row["status"] == "RUNNING":
            row["status"] = "FINISHED"
        elif hydra is not None and not callback.get("solver_finished"):
            # MLflow can mark a runner process FINISHED even when the solver log
            # was truncated before a final Gurobi summary was written.  Keeping
            # that row as FINISHED makes the unrecoverable final fields look
            # like a parser failure and can mix partial Hydra data with MLflow.
            row["status"] = "INCOMPLETE"
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


def is_below(path: Path, parent: Path) -> bool:
    try:
        path.resolve().relative_to(parent.resolve())
        return True
    except (OSError, ValueError):
        return False


def write_csv(rows: list[dict[str, Any]], output: Path, allow_empty: bool = False) -> None:
    if not rows and not allow_empty:
        raise SystemExit("No A--G MLflow runs found")
    fields = AG_OUTPUT_COLUMNS
    aliases = {
        "features": "number_of_variables",
        "samples": "number_of_samples",
        "degree": "seed",
        "ori_graph_density": "ori_skeleton_density",
        "after_cliquefree_density": "after_cliquefree_skeleton_density",
        "runtime_seconds": "runtime_s",
        "explored_nodes": "nodes",
        "f1score": "f1",
        "cycle_lazy_cuts": "cycle_cuts",
        "clique_lazy_cuts": "clique_cuts",
        "clique_user_cuts": "user_cuts",
        "mipsol_rejection_pct": "rejection_pct",
        "root_fractional_x_bins": "root_x_bins",
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    integer_fields = {
        "seed", "degree", "features", "samples", "p", "true_edges",
        "mipsol_total", "mipsol_rejected", "mipsol_accepted",
        "cycle_only_candidates", "clique_only_candidates", "both_candidates",
        "root_fractional_edges", "root_small_x_large_w",
        "root_violated_cliques", "cycle_lazy_cuts", "clique_lazy_cuts",
        "clique_user_cuts", "unique_cuts", "duplicate_cuts", "shd", "nnz",
        "cycle_unique_cuts", "clique_unique_cuts",
        "cycle_duplicate_cuts", "clique_duplicate_cuts",
        "open_nodes", "solution_count",
    }
    three_decimal_fields = {
        "runtime_seconds", "callback_s", "callback_pct", "search_s",
        "nodes_per_s", "lp_iter_per_node", "rejection_pct", "cut_hit_pct",
        "lp_iter_per_s", "violation_overlap_pct",
        "ori_graph_density", "after_cliquefree_density",
        "cycle_callback_s", "clique_callback_s",
    }
    six_decimal_fields = {
        "best_incumbent", "best_bound", "gap", "gap_pct", "root_bound",
        "dual_gain_per_cut", "dual_gain_per_s", "f1score", "g_score",
        "true_mean_abs_w", "big_m", "bound_gain", "bound_gain_per_1k_nodes",
        "root_max_clique_violation",
        "root_mean_big_m_ratio",
    }
    formatted_rows: list[dict[str, Any]] = []
    for row in rows:
        formatted = {
            field: row.get(field, row.get(aliases.get(field, ""), ""))
            for field in fields
        }
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
        value = as_float(formatted.get("explored_nodes"))
        if value is not None:
            formatted["explored_nodes"] = str(int(round(value)))
        formatted_rows.append(formatted)
    temporary_output = output.with_suffix(output.suffix + ".tmp")
    with temporary_output.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(formatted_rows)
    temporary_output.replace(output)


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
    parser.add_argument("--output", default="A-G_experiments.csv")
    parser.add_argument(
        "--run-root",
        action="append",
        default=[],
        help="only retain rows whose Hydra run_dir is below this directory",
    )
    parser.add_argument(
        "--run-dirs-file",
        help="optional text file containing additional run-root directories",
    )
    parser.add_argument(
        "--allow-empty",
        action="store_true",
        help="write the standard header even when the active batch has no completed rows",
    )
    parser.add_argument(
        "--experiment-prefix",
        help="only include experiments whose names start with this prefix",
    )
    parser.add_argument(
        "--strict",
        action="store_true",
        help="return a non-zero exit code when matches/data are incomplete",
    )
    args = parser.parse_args()

    all_rows: list[dict[str, Any]] = []
    all_warnings: list[str] = []
    dagsolvers_roots: list[Path] = []
    for root_arg in args.roots:
        for dagsolvers_root in locate_dagsolvers_roots(Path(root_arg)):
            dagsolvers_roots.append(dagsolvers_root)
            rows, warnings = build_rows(dagsolvers_root, args.experiment_prefix)
            all_rows.extend(rows)
            all_warnings.extend(warnings)

    run_roots = [Path(value).expanduser().resolve() for value in args.run_root]
    if args.run_dirs_file:
        run_dirs_file = Path(args.run_dirs_file).expanduser().resolve()
        if run_dirs_file.exists():
            run_roots.extend(
                Path(line.strip()).expanduser().resolve()
                for line in run_dirs_file.read_text().splitlines()
                if line.strip()
            )
    if run_roots:
        filtered_rows = []
        for row in all_rows:
            value = str(row.get("run_dir") or "").strip()
            if not value:
                continue
            candidate = Path(value).expanduser()
            candidates = [candidate] if candidate.is_absolute() else [root / candidate for root in dagsolvers_roots]
            if any(is_below(path, run_root) for path in candidates for run_root in run_roots):
                filtered_rows.append(row)
        all_rows = filtered_rows

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
    write_csv(all_rows, output, allow_empty=args.allow_empty)

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
    main()
