#!/usr/bin/env python3
"""Summarize H1--H4 diagnostic artifacts below one or more run directories."""

import argparse
import csv
import glob
import json
import os
from collections import Counter


def read_csv(path):
    with open(path, newline="") as handle:
        return list(csv.DictReader(handle))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("roots", nargs="+", help="Hydra run/multirun directories")
    parser.add_argument("--output", default="optimization_diagnostics_summary.csv")
    args = parser.parse_args()

    summaries = []
    for root in args.roots:
        pattern = os.path.join(os.path.abspath(root), "**", "*_summary_diagnostics.json")
        for summary_path in glob.glob(pattern, recursive=True):
            with open(summary_path) as handle:
                summary = json.load(handle)
            prefix = summary_path.removesuffix("_summary_diagnostics.json")
            mipsol_path = prefix + "_mipsol_diagnostics.csv"
            root_path = prefix + "_root_diagnostics.csv"
            mipsols = read_csv(mipsol_path) if os.path.exists(mipsol_path) else []
            roots = read_csv(root_path) if os.path.exists(root_path) else []
            counts = Counter(row["violation_class"] for row in mipsols)
            cyclic = counts["cycle_only"] + counts["both"]
            clique_given_cycle = counts["both"] / cyclic if cyclic else None
            first_dag = min((float(r["runtime"]) for r in mipsols
                             if r["is_dag"] == "True"), default=None)
            first_valid = min((float(r["runtime"]) for r in mipsols
                               if r["combined_structure_valid"] == "True"), default=None)
            final = summary.get("final", {})
            callback_costs = summary.get("callback_costs", {})
            cut_attempts = summary.get("cut_attempt_counts", {})
            cut_unique = summary.get("cut_unique_counts", {})
            cut_duplicates = summary.get("cut_duplicate_counts", {})
            metadata = summary.get("experiment_metadata", {})
            derived = summary.get("derived_metrics", {})
            summaries.append({
                "run_dir": os.path.dirname(summary_path),
                "method": summary["method"],
                "solver": metadata.get("solver"),
                "problem": metadata.get("problem"),
                "seed": metadata.get("seed"),
                "number_of_variables": metadata.get("number_of_variables"),
                "number_of_samples": metadata.get("number_of_samples"),
                "p": metadata.get("p"),
                "sem_type": metadata.get("sem_type"),
                "generator": metadata.get("generator"),
                "graph_type": metadata.get("graph_type"),
                "normalize": metadata.get("normalize"),
                "intra_edge_ratio": metadata.get("intra_edge_ratio"),
                "inter_edge_ratio": metadata.get("inter_edge_ratio"),
                "time_limit": metadata.get("time_limit"),
                "target_mip_gap": metadata.get("target_mip_gap"),
                "lambda1": metadata.get("lambda1"),
                "lambda2": metadata.get("lambda2"),
                "loss_type": metadata.get("loss_type"),
                "constraints_mode": metadata.get("constraints_mode"),
                "nonzero_threshold": metadata.get("nonzero_threshold"),
                "max_clique_size": metadata.get("max_clique_size"),
                "callback_mode": metadata.get("callback_mode"),
                "clique_callback_mode": metadata.get("clique_callback_mode"),
                "enable_cycle_constraints": metadata.get("enable_cycle_constraints"),
                "enable_clique_constraints": metadata.get("enable_clique_constraints"),
                "separation_order": metadata.get("separation_order"),
                "delayed_second_separation": metadata.get(
                    "delayed_second_separation"),
                "cycle_top_k": metadata.get("cycle_top_k"),
                "clique_top_k": metadata.get("clique_top_k"),
                "max_cycle_cuts_per_callback": metadata.get(
                    "max_cycle_cuts_per_callback"),
                "max_clique_cuts_per_callback": metadata.get(
                    "max_clique_cuts_per_callback"),
                "deduplicate_cycle_cuts": metadata.get("deduplicate_cycle_cuts"),
                "deduplicate_clique_cuts": metadata.get("deduplicate_clique_cuts"),
                "enable_fractional_clique_cuts": metadata.get(
                    "enable_fractional_clique_cuts"),
                "fractional_root_only": metadata.get("fractional_root_only"),
                "gurobi_seed": metadata.get("gurobi_seed"),
                "gurobi_threads": metadata.get("gurobi_threads"),
                "greedy_node_frequency": metadata.get("greedy_node_frequency"),
                "greedy_max_cuts_per_node": metadata.get(
                    "greedy_max_cuts_per_node"),
                "big_m": summary["big_m"],
                "root_bound": roots[-1]["root_bound"] if roots else None,
                "root_fractional_edges": roots[-1]["fractional_edge_count"] if roots else None,
                "root_small_x_large_w": roots[-1]["small_x_large_w_005_05"] if roots else None,
                "root_violated_cliques": roots[-1]["violated_clique_count"] if roots else None,
                "mipsol_count": len(mipsols),
                "accepted_mipsol_count": summary.get("accepted_mipsol_count"),
                "accepted_incumbent_improvements": summary.get(
                    "accepted_incumbent_improvement_count"),
                "cycle_only": counts["cycle_only"],
                "clique_only": counts["clique_only"],
                "both": counts["both"],
                "neither": counts["neither"],
                "p_clique_given_cycle": clique_given_cycle,
                "dense_dag_count": summary.get("dense_dag_count"),
                "best_dense_dag_objective": summary.get("best_dense_dag_objective"),
                "first_dense_dag_time": summary.get("first_dense_dag_time"),
                "first_dag_time": first_dag,
                "first_combined_valid_time": first_valid,
                "final_objective": final.get("objective"),
                "final_bound": final.get("best_bound"),
                "final_gap": final.get("gap"),
                "final_runtime": final.get("runtime"),
                "final_nodes": final.get("node_count"),
                "nodes_per_second": final.get("nodes_per_second"),
                "simplex_iterations": final.get("simplex_iteration_count"),
                "work": final.get("work"),
                "final_shd_at_solver_threshold": final.get(
                    "final_shd_at_solver_threshold"),
                "final_f1_at_solver_threshold": final.get(
                    "final_f1_at_solver_threshold"),
                "lazy_count": final.get("lazy_count"),
                "cycle_detection_time": callback_costs.get("cycle_detection_time", 0),
                "cycle_submission_time": callback_costs.get("cycle_submission_time", 0),
                "clique_detection_time": callback_costs.get("clique_detection_time", 0),
                "clique_submission_time": callback_costs.get("clique_submission_time", 0),
                "diagnostics_classification_time": callback_costs.get(
                    "diagnostics_classification_time", 0),
                "cycle_cut_attempts": cut_attempts.get("cycle", 0),
                "cycle_unique_cuts": cut_unique.get("cycle", 0),
                "cycle_duplicate_cuts": cut_duplicates.get("cycle", 0),
                "clique_cut_attempts": cut_attempts.get("clique", 0),
                "clique_unique_cuts": cut_unique.get("clique", 0),
                "clique_duplicate_cuts": cut_duplicates.get("clique", 0),
                "mipsol_rejection_rate": derived.get("mipsol_rejection_rate"),
                "violation_overlap_rate": derived.get("violation_overlap_rate"),
                "cut_hit_rate": derived.get("cut_hit_rate"),
                "initial_bound": derived.get("initial_bound"),
                "bound_gain": derived.get("bound_gain"),
                "dual_gain_per_cut": derived.get("dual_gain_per_cut"),
                "dual_gain_per_second": derived.get("dual_gain_per_second"),
                "bound_gain_per_1000_nodes": derived.get(
                    "bound_gain_per_1000_nodes"),
                "lp_iterations_per_node": derived.get("lp_iterations_per_node"),
                "lp_iterations_per_second": derived.get(
                    "lp_iterations_per_second"),
                "callback_time": derived.get("callback_time"),
                "callback_time_over_total_runtime": derived.get(
                    "callback_time_over_total_runtime"),
            })

    if not summaries:
        raise SystemExit("No *_summary_diagnostics.json files found")
    fields = list(summaries[0])
    with open(args.output, "w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(summaries)
    print(f"Wrote {len(summaries)} rows to {args.output}")


if __name__ == "__main__":
    main()
