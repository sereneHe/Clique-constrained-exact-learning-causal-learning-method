#!/usr/bin/env python3
"""Backfill unified A--G result CSV columns from retained diagnostics and logs."""

import argparse
import ast
import csv
import json
import re
from pathlib import Path


def read_json(path):
    try:
        return json.loads(path.read_text())
    except (OSError, json.JSONDecodeError):
        return {}


def json_cell(value):
    return json.dumps(value, separators=(",", ":"), sort_keys=True)


def fill_from_run(row, run_path):
    diagnostics_paths = sorted(run_path.glob("*_summary_diagnostics.json"))
    method_paths = sorted(p for p in run_path.glob("*_summary.json")
                          if not p.name.endswith("_summary_diagnostics.json"))
    progress_paths = sorted(run_path.glob("*_progress_diagnostics.csv"))
    diagnostics = read_json(diagnostics_paths[0]) if diagnostics_paths else {}
    method = read_json(method_paths[0]) if method_paths else {}
    final = diagnostics.get("final", {})
    costs = diagnostics.get("callback_costs", {})
    attempts = diagnostics.get("separation_attempt_counts", {})
    progress = []
    if progress_paths:
        with progress_paths[0].open(newline="") as handle:
            progress = list(csv.DictReader(handle))

    values = {
        "mipnode_total": final.get("mipnode_total", method.get("mipnode_total")),
        "lp_iterations": final.get("simplex_iteration_count", method.get("lp_iterations")),
        "cycle_detection_s": costs.get("cycle_detection_time"),
        "cycle_submission_s": costs.get("cycle_submission_time"),
        "clique_detection_s": costs.get("clique_detection_time"),
        "clique_submission_s": costs.get("clique_submission_time"),
        "cycle_separation_attempts": attempts.get("cycle"),
        "clique_separation_attempts": attempts.get("clique"),
        "cycle_callback_count": attempts.get("cycle"),
        "clique_callback_count": attempts.get("clique"),
        "mip_progress_times": json_cell([r.get("runtime") for r in progress]) if progress else None,
        "checkpoint_explored_nodes": json_cell([r.get("explored_nodes") for r in progress]) if progress else None,
        "checkpoint_open_nodes": json_cell([r.get("open_nodes") for r in progress]) if progress else None,
        "checkpoint_best_bound": json_cell([r.get("best_bound") for r in progress]) if progress else None,
        "checkpoint_incumbent": json_cell([r.get("best_incumbent") for r in progress]) if progress else None,
        "checkpoint_gap": json_cell([r.get("gap") for r in progress]) if progress else None,
        "checkpoint_solution_count": json_cell([r.get("solution_count") for r in progress]) if progress else None,
    }
    snapshot = method.get("best_accepted_snapshot") or final.get("best_accepted_snapshot") or {}
    if snapshot:
        values.update({
            "best_incumbent_edges": json_cell(snapshot.get("edges")),
            "best_incumbent_weights": json_cell(snapshot.get("weights")),
        })
    for key, value in values.items():
        if value is not None and str(value) != "":
            row[key] = value


def log_segments(log_path):
    text = log_path.read_text(errors="replace")
    pattern = re.compile(
        r"\[HYDRA\].*?#\d+ : experiment=(?P<experiment>METHOD_[A-G][^ ]*)"
        r".*?(?:problem\.intra_edge_ratio|problem\.edge_ratio)=(?P<edge_ratio>[0-9.]+)"
        r".*?problem\.seed=(?P<seed>\d+)")
    matches = list(pattern.finditer(text))
    result = {}
    for index, match in enumerate(matches):
        end = matches[index + 1].start() if index + 1 < len(matches) else len(text)
        key = (match.group("experiment"), match.group("seed"), match.group("edge_ratio"))
        result.setdefault(key, []).append(text[match.end():end])
    return result


def fill_from_log(row, segment):
    callback = re.search(
        r"\[CALLBACK-SUMMARY\].*?cycle_filter_seconds=([0-9.eE+-]+).*?"
        r"cycle_add_seconds=([0-9.eE+-]+).*?clique_filter_seconds=([0-9.eE+-]+).*?"
        r"clique_add_seconds=([0-9.eE+-]+)", segment)
    if callback:
        for key, value in zip(
                ("cycle_detection_s", "cycle_submission_s",
                 "clique_detection_s", "clique_submission_s"), callback.groups()):
            row[key] = value
    explored = re.search(r"Explored\s+\d+\s+nodes\s+\(([0-9]+)\s+simplex iterations\)", segment)
    if explored:
        row["lp_iterations"] = explored.group(1)
    cycle_calls = len(re.findall(r"event=cycle_detection_start", segment))
    clique_calls = len(re.findall(r"event=clique_detection_start", segment))
    if cycle_calls or clique_calls:
        row["cycle_separation_attempts"] = cycle_calls
        row["clique_separation_attempts"] = clique_calls
        row["cycle_callback_count"] = cycle_calls
        row["clique_callback_count"] = clique_calls

    callback_summary = re.search(r"\[CALLBACK-SUMMARY\]\s+([^\n]+)", segment)
    if callback_summary:
        summary = dict(re.findall(r"([a-z_]+)=([^ ]+)", callback_summary.group(1)))
        aliases = {
            "mipsol_total": "mipsol_total",
            "mipsol_rejected": "mipsol_rejected",
            "mipsol_accepted": "mipsol_accepted",
            "cycle_constraints_added": "cycle_lazy_cuts",
            "clique_constraints_added": "clique_lazy_cuts",
        }
        for source, target in aliases.items():
            if source in summary:
                row[target] = summary[source]

    explored = re.search(
        r"Explored\s+(\d+)\s+nodes\s+\((\d+)\s+simplex iterations\)\s+in\s+([0-9.]+)\s+seconds",
        segment)
    if explored:
        row["explored_nodes"], row["lp_iterations"] = explored.group(1), explored.group(2)
        row["runtime_seconds"] = explored.group(3)
        runtime = float(explored.group(3))
        nodes = float(explored.group(1))
        iterations = float(explored.group(2))
        row["nodes_per_s"] = nodes / runtime if runtime else ""
        row["lp_iter_per_node"] = iterations / nodes if nodes else ""
        row["lp_iter_per_s"] = iterations / runtime if runtime else ""

    solution_count = re.search(r"Solution count\s+(\d+):", segment)
    if solution_count:
        row["solution_count"] = solution_count.group(1)
    optimum = re.search(
        r"Best objective\s+([0-9.eE+-]+),\s+best bound\s+([0-9.eE+-]+),\s+gap\s+([0-9.]+)%",
        segment)
    if optimum:
        row["best_incumbent"] = optimum.group(1)
        row["best_bound"] = optimum.group(2)
        row["gap"] = float(optimum.group(3)) / 100.0

    experiment_metrics = re.search(r"\[EXPERIMENT-METRICS\]\s+(\{[^\n]+\})", segment)
    if experiment_metrics:
        try:
            metrics = json.loads(experiment_metrics.group(1))
        except json.JSONDecodeError:
            metrics = {}
        metric_aliases = {
            "initial_bound": "root_bound",
            "bound_gain": "bound_gain",
            "bound_gain_per_1000_nodes": "bound_gain_per_1k_nodes",
            "callback_time": "callback_s",
            "cut_hit_rate": "cut_hit_pct",
            "dual_gain_per_cut": "dual_gain_per_cut",
            "dual_gain_per_second": "dual_gain_per_s",
            "lp_iterations_per_node": "lp_iter_per_node",
            "lp_iterations_per_second": "lp_iter_per_s",
            "mipsol_rejection_rate": "mipsol_rejection_pct",
            "violation_overlap_rate": "violation_overlap_pct",
        }
        percent_targets = {"cut_hit_pct", "mipsol_rejection_pct", "violation_overlap_pct"}
        for source, target in metric_aliases.items():
            if metrics.get(source) is not None:
                value = metrics[source]
                row[target] = 100.0 * value if target in percent_targets else value
        runtime = float(row["runtime_seconds"]) if row.get("runtime_seconds") else None
        callback_s = metrics.get("callback_time")
        if runtime and callback_s is not None:
            row["callback_pct"] = 100.0 * callback_s / runtime
            row["search_s"] = runtime - callback_s

    metadata_match = re.search(r"\[EXPERIMENT-METADATA\]\s+(\{[^\n]+\})", segment)
    if metadata_match:
        try:
            metadata = json.loads(metadata_match.group(1))
        except json.JSONDecodeError:
            metadata = {}
        if metadata.get("weights_bound") is not None:
            row["big_m"] = metadata["weights_bound"]

    if row.get("experiment", "").startswith("METHOD_A"):
        row["method_variant"] = "A"
    try:
        row["cycle_callback_s"] = (
            float(row["cycle_detection_s"]) + float(row["cycle_submission_s"]))
    except (KeyError, TypeError, ValueError):
        pass
    try:
        row["clique_callback_s"] = (
            float(row["clique_detection_s"]) + float(row["clique_submission_s"]))
    except (KeyError, TypeError, ValueError):
        pass

    # The final ``best`` accuracy dictionary follows the threshold diagnostics.
    best_match = re.search(r"\nbest\s*\n(\{[^\n]+\})", segment)
    if best_match:
        cleaned = re.sub(r"np\.float64\(([^)]+)\)", r"\1", best_match.group(1))
        try:
            accuracy = ast.literal_eval(cleaned)
        except (SyntaxError, ValueError):
            accuracy = {}
        for field in ("fdr", "tpr", "fpr", "nnz", "precision", "f1score", "g_score", "shd"):
            if accuracy.get(field) is not None:
                row[field] = accuracy[field]

    retained = re.search(r"\[SOLUTION\]\s+(\{[^\n]+\})", segment)
    if retained:
        try:
            solution = json.loads(retained.group(1))
        except json.JSONDecodeError:
            solution = {}
        edges = solution.get("edges")
        if edges:
            row["best_incumbent_edges"] = json_cell(
                [[edge.get("from"), edge.get("to")] for edge in edges])
            row["best_incumbent_weights"] = json_cell(
                [edge.get("weight") for edge in edges])


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--job-root", required=True, type=Path)
    parser.add_argument("--log", required=True, type=Path)
    parser.add_argument(
        "--only-method-variants", default="",
        help="Comma-separated variants to update, for example B1,B6.")
    parser.add_argument(
        "--overwrite-log", action="store_true",
        help="Allow parsed log values to replace existing non-empty cells.")
    args = parser.parse_args()
    selected_variants = {
        value.strip() for value in args.only_method_variants.split(",") if value.strip()
    }
    results = args.job_root / "dagsolvers" / "results"
    multirun = args.job_root / "dagsolvers" / "multirun"
    segments = log_segments(args.log)
    files = sorted(results.rglob("clique_runtime_*.csv"))
    tracked = [
        "mipnode_total", "lp_iterations", "cycle_detection_s", "cycle_submission_s",
        "clique_detection_s", "clique_submission_s",
        "cycle_separation_attempts", "clique_separation_attempts",
        "cycle_callback_count", "clique_callback_count", "mip_progress_times",
        "checkpoint_explored_nodes", "checkpoint_open_nodes", "checkpoint_best_bound",
        "checkpoint_incumbent", "checkpoint_gap",
        "checkpoint_status", "checkpoint_solution_count", "checkpoint_DAG",
        "checkpoint_SHD", "checkpoint_F1", "checkpoint_NNZ",
        "best_incumbent_edges", "best_incumbent_weights",
    ]
    all_rows = []
    for path in files:
        with path.open(newline="") as handle:
            reader = csv.DictReader(handle)
            fields = reader.fieldnames
            rows = list(reader)
        for row in rows:
            if selected_variants and row.get("method_variant") not in selected_variants:
                continue
            run_dir = row.get("run_dir", "")
            run_path = multirun / run_dir.removeprefix("multirun/")
            if run_path.is_dir():
                fill_from_run(row, run_path)
            ratio = str(row.get("edge_ratio", ""))
            if ratio.endswith(".0"):
                ratio = ratio[:-2]
            candidates = segments.get((row.get("experiment"), row.get("seed"), ratio), [])
            run_dir = row.get("run_dir", "")
            segment = next((candidate for candidate in candidates if run_dir and run_dir in candidate), None)
            if segment is None and len(candidates) == 1:
                segment = candidates[0]
            if segment:
                retained_values = {} if args.overwrite_log else {
                    key: value for key, value in row.items()
                    if value is not None and str(value).strip()
                }
                fill_from_log(row, segment)
                # Backfilling must not replace values already produced by the run's
                # result writer; the log is only a fallback for missing cells.
                row.update(retained_values)
        with path.open("w", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=fields)
            writer.writeheader()
            writer.writerows(rows)
        all_rows.extend(rows)
        print(f"updated {path}: {len(rows)} rows")
    print(f"total_rows={len(all_rows)}")
    for column in tracked:
        filled = sum(bool(str(row.get(column, "")).strip()) for row in all_rows)
        print(f"{column}: filled={filled} empty={len(all_rows)-filled}")


if __name__ == "__main__":
    main()
