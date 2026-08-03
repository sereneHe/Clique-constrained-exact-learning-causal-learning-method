from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd

try:
    from dagsolvers.plot_helpers import (
        TIME_LIMIT_SOLVER_LABELS as SOLVER_LABELS,
        available_time_limit_d_values,
        collect_time_limit_summary,
        plot_time_limit_f1_summary as plot_f1_summary,
        plot_time_limit_shd_summary as plot_summary,
        results_base_dir_for_report_dir as _results_base_dir_for_report_dir,
        scenario_prefix_and_base_dir as _scenario_prefix_and_base_dir,
    )
except ModuleNotFoundError:
    from plot_helpers import (  # type: ignore
        TIME_LIMIT_SOLVER_LABELS as SOLVER_LABELS,
        available_time_limit_d_values,
        collect_time_limit_summary,
        plot_time_limit_f1_summary as plot_f1_summary,
        plot_time_limit_shd_summary as plot_summary,
        results_base_dir_for_report_dir as _results_base_dir_for_report_dir,
        scenario_prefix_and_base_dir as _scenario_prefix_and_base_dir,
    )


DEFAULT_REPORT_DIR = Path(
    "/Users/xiaoyuhe/project-bestdagsolverintheworld/dagsolvers/reports/sf-5-0/SF-5-0-1800s"
)
DEFAULT_RESULTS_BASE_DIR = Path(
    "/Users/xiaoyuhe/project-bestdagsolverintheworld/dagsolvers/results/sf-5-0"
)


def collect_summary(report_dir: Path, sample_size: int = 200, d: int = 35) -> pd.DataFrame:
    return collect_time_limit_summary(
        report_dir,
        solver_labels=SOLVER_LABELS,
        default_results_base_dir=DEFAULT_RESULTS_BASE_DIR,
        sample_size=sample_size,
        d=d,
    )


def available_d_values(report_dir: Path, sample_size: int = 200) -> list[int]:
    return available_time_limit_d_values(
        report_dir,
        default_results_base_dir=DEFAULT_RESULTS_BASE_DIR,
        sample_size=sample_size,
    )


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--report-dir",
        type=Path,
        default=DEFAULT_REPORT_DIR,
        help="Reference run directory, e.g. .../SF-5-0-1800s. Used to infer scenario prefix and output root.",
    )
    parser.add_argument("--sample-size", type=int, default=200)
    parser.add_argument("--d", type=int, nargs="*", default=None)
    parser.add_argument("--summary-csv", type=str, default=None)
    parser.add_argument("--output-png", type=str, default=None)
    parser.add_argument(
        "--solvers",
        nargs="*",
        choices=["milp", "clique", "edge_limit"],
        default=["milp", "clique", "edge_limit"],
    )
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    report_dir = args.report_dir.resolve()
    _, base_dir = _scenario_prefix_and_base_dir(report_dir)
    results_base_dir = _results_base_dir_for_report_dir(report_dir, DEFAULT_RESULTS_BASE_DIR)
    results_base_dir.mkdir(parents=True, exist_ok=True)

    if args.summary_csv:
        summary_path = Path(args.summary_csv)
        summary = pd.read_csv(summary_path)
        summary = summary[summary["solver_key"].isin(args.solvers)].copy()
        if summary.empty:
            raise SystemExit("No requested solvers present in summary CSV.")
        sample_size = int(summary["sample_size"].iloc[0])
        d = int(summary["d"].iloc[0])
        output_png = Path(args.output_png) if args.output_png else base_dir / f"sf5_d{d}_n{sample_size}_shd_vs_time_limit.png"
        output_f1_png = output_png.with_name(output_png.name.replace("_shd_vs_time_limit", "_f1_vs_time_limit"))
        plot_summary(summary, output_png, sample_size=sample_size, d=d, solvers=args.solvers)
        plot_f1_summary(summary, output_f1_png, sample_size=sample_size, d=d, solvers=args.solvers)
        print(output_png)
        print(output_f1_png)
        return

    d_values = args.d if args.d else available_d_values(report_dir=report_dir, sample_size=args.sample_size)
    if not d_values:
        raise SystemExit(f"No SF-5-0 d values found for n={args.sample_size}.")

    generated = 0
    for d in d_values:
        output_png = base_dir / f"sf5_d{d}_n{args.sample_size}_shd_vs_time_limit.png"
        output_f1_png = base_dir / f"sf5_d{d}_n{args.sample_size}_f1_vs_time_limit.png"
        output_csv = results_base_dir / f"sf5_d{d}_n{args.sample_size}_shd_vs_time_limit_summary.csv"
        summary = collect_summary(report_dir=report_dir, sample_size=args.sample_size, d=d)
        if summary.empty:
            continue
        summary = summary[summary["solver_key"].isin(args.solvers)].copy()
        if summary.empty:
            continue
        summary.to_csv(output_csv, index=False)
        plot_summary(summary, output_png, sample_size=args.sample_size, d=d, solvers=args.solvers)
        plot_f1_summary(summary, output_f1_png, sample_size=args.sample_size, d=d, solvers=args.solvers)
        print(output_png)
        print(output_f1_png)
        print(output_csv)
        generated += 1

    if generated == 0:
        raise SystemExit(f"No SF-5-0 SHD tables found for requested d values at n={args.sample_size}.")


if __name__ == "__main__":
    main()
