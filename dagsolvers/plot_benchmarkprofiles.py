from __future__ import annotations

import argparse
import csv
import os
from pathlib import Path

try:
    from dagsolvers.plot_helpers import (
        BASE_SOLVER_ORDER,
        METRIC_LABELS,
        SOLVER_COLORS,
        SOLVER_LABELS,
        SOLVER_LINESTYLES,
        active_solver_order,
        collect_rows_from_table_dir,
        export_profile_data,
        plot_combined_performance_from_summaries,
        plot_performance_from_exdbn_run_tables,
        plot_profile,
    )
except ModuleNotFoundError:
    from plot_helpers import (  # type: ignore
        BASE_SOLVER_ORDER,
        METRIC_LABELS,
        SOLVER_COLORS,
        SOLVER_LABELS,
        SOLVER_LINESTYLES,
        active_solver_order,
        collect_rows_from_table_dir,
        export_profile_data,
        plot_combined_performance_from_summaries,
        plot_performance_from_exdbn_run_tables,
        plot_profile,
    )


# Static solver tables are now written directly below the scenario directory
# (for example ``results/cliquefree-sf-5-0/static_n200``), rather than in the
# legacy ``results/sf-5-0/SF-5-0-1800s`` layout.
DEFAULT_TABLE_DIR = Path(__file__).resolve().parent / "results" / "cliquefree-sf-5-0"
DEFAULT_RESULTS_DIR = DEFAULT_TABLE_DIR.parent
DEFAULT_REPORTS_DIR = Path(__file__).resolve().parent / "reports"


def _metrics_from_environment() -> list[str]:
    """Read slash- or comma-separated profile metrics from EXDBN_Y_AXIS."""
    value = os.getenv("EXDBN_Y_AXIS", "runtime_seconds")
    metrics = [item.strip() for item in value.replace(",", "/").split("/") if item.strip()]
    return metrics or ["runtime_seconds"]


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate BenchmarkProfiles-style profile data from raw solver CSVs or per-scenario tables and plot it."
    )
    parser.add_argument("--raw-results", help="Raw solver results CSV.")
    parser.add_argument(
        "--table-dir",
        help="Directory containing solver tables such as static_n200 and static_n2000.",
    )
    parser.add_argument(
        "--scenario-key",
        default=None,
        help="Optional scenario key filter when using --table-dir, for example SF-5-0.",
    )
    parser.add_argument("--output-png", help="Optional output PNG path for single-metric raw results mode.")
    parser.add_argument(
        "--output-dir",
        help="Directory for generated profile data/plots in --raw-results mode. Defaults to raw CSV directory.",
    )
    parser.add_argument(
        "--metrics",
        nargs="+",
        default=None,
        help=(
            "Metrics to export or plot, for example runtime_seconds lazy_count best_shd. "
            "Defaults to slash-separated EXDBN_Y_AXIS or runtime_seconds."
        ),
    )
    parser.add_argument(
        "--no-semilog",
        action="store_true",
        help="Use a linear x-axis profile instead of the default semilog profile data.",
    )
    mean_group = parser.add_mutually_exclusive_group()
    mean_group.add_argument(
        "--mean-over-seeds",
        dest="mean_over_seeds",
        action="store_true",
        default=True,
        help=(
            "Average repeated seed rows for each (scenario, sample size, number of nodes, solver) "
            "before building the profile. This is the default."
        ),
    )
    mean_group.add_argument(
        "--no-mean-over-seeds",
        dest="mean_over_seeds",
        action="store_false",
        help="Use the original per-seed rows as separate profile problems.",
    )
    edge_group = parser.add_mutually_exclusive_group()
    edge_group.add_argument(
        "--include-edge-limit",
        dest="include_edge_limit",
        action="store_true",
        default=True,
        help="Include the edge-limit final-row summary in the benchmark profile.",
    )
    edge_group.add_argument(
        "--exclude-edge-limit",
        dest="include_edge_limit",
        action="store_false",
        help="Exclude the edge-limit final-row summary from the benchmark profile.",
    )
    edge_mean_group = parser.add_mutually_exclusive_group()
    edge_mean_group.add_argument(
        "--include-edge-limit-mean",
        dest="include_edge_limit_mean",
        action="store_true",
        default=True,
        help="Include the edge-limit mean-over-table summary in the benchmark profile.",
    )
    edge_mean_group.add_argument(
        "--exclude-edge-limit-mean",
        dest="include_edge_limit_mean",
        action="store_false",
        help="Exclude the edge-limit mean-over-table summary from the benchmark profile.",
    )
    parser.add_argument(
        "--methods",
        help="Comma-separated method keys; defaults to EXDBN_METHOD_KEYS.",
    )
    parser.add_argument(
        "--all-methods",
        action="store_true",
        help="Include every available static-runtime method table.",
    )
    return parser.parse_args()


def _raw_results_mode(
    raw_results_csv: Path,
    output_dir: Path,
    metrics: list[str],
    *,
    solver_order: tuple[str, ...],
    logscale: bool,
    output_png: Path | None,
    mean_over_seeds: bool,
) -> None:
    single_png = output_png is not None
    if single_png and len(metrics) != 1:
        raise ValueError("--output-png can only be used with a single metric in --raw-results mode")

    for metric in metrics:
        rows = list(csv.DictReader(raw_results_csv.open()))
        if not rows:
            raise ValueError(f"No rows found in {raw_results_csv}")
        data_csv = export_profile_data(
            rows,
            output_dir.resolve(),
            metric,
            solver_order=solver_order,
            logscale=logscale,
            mean_over_seeds=mean_over_seeds,
        )
        if single_png:
            plot_profile(data_csv, output_png.resolve())
        else:
            plot_profile(data_csv, output_dir.resolve() / f"benchmarkprofiles_{metric}.png")


def _table_dir_mode(
    table_dirs: list[Path],
    output_dir: Path,
    metrics: list[str],
    *,
    solver_order: tuple[str, ...],
    logscale: bool,
    scenario_key: str | None,
    output_png: Path | None,
    mean_over_seeds: bool,
    include_edge_limit: bool,
    include_edge_limit_mean: bool,
    selected_solvers: set[str] | None,
    all_methods: bool,
    output_prefix: str,
) -> None:
    single_png = output_png is not None
    if single_png and len(metrics) != 1:
        raise ValueError("--output-png can only be used with a single metric in --table-dir mode")
    rows = []
    for table_dir in table_dirs:
        rows.extend(collect_rows_from_table_dir(
            table_dir,
            scenario_key=scenario_key,
            include_edge_limit=include_edge_limit,
            include_edge_limit_mean=include_edge_limit_mean,
            selected_solvers=selected_solvers,
        ))
    # Some scenario directories contain only a subset of the optional solver
    # tables.  A profile requires common problems across every solver passed
    # to it, so do not retain optional solvers that have no rows at all.
    available_solvers = {
        str(row.get("solver", "")).strip().lower() for row in rows
    }
    if all_methods:
        solver_order = tuple(
            solver for solver in BASE_SOLVER_ORDER if solver in available_solvers
        ) + tuple(
            solver for solver in sorted(available_solvers)
            if solver not in BASE_SOLVER_ORDER
        )
    solver_order = tuple(
        solver for solver in solver_order if solver in available_solvers
    )
    if len(solver_order) < 2:
        raise ValueError(
            f"Need at least two solver tables under {table_dirs}; found "
            f"{sorted(available_solvers)}"
        )
    for metric in metrics:
        data_csv = export_profile_data(
            rows,
            output_dir.resolve(),
            metric,
            solver_order=solver_order,
            logscale=logscale,
            mean_over_seeds=mean_over_seeds,
        )
        if single_png:
            plot_profile(data_csv, output_png.resolve())
        else:
            plot_profile(data_csv, output_dir.resolve() / f"{output_prefix}_{metric}.png")
            plot_profile(data_csv, output_dir.resolve() / f"{output_prefix}_{metric}.pdf")


def main() -> None:
    args = _parse_args()
    # Benchmark profiles are publication-ready outputs: always keep a vector
    # PDF alongside the PNG unless the caller explicitly overrides formats.
    os.environ.setdefault("EXDBN_PLOT_FORMATS", "png,pdf")
    os.environ.setdefault("EXDBN_PLOT_DPI", "300")
    metrics = args.metrics or _metrics_from_environment()
    raw_results_csv = Path(args.raw_results).resolve() if args.raw_results else None
    table_dir = Path(args.table_dir).resolve() if args.table_dir else None
    output_png = Path(args.output_png).resolve() if args.output_png else None
    output_dir = Path(args.output_dir).resolve() if args.output_dir else None
    output_prefix = os.getenv("EXDBN_PLOT_OUTPUT_PREFIX", "benchmarkprofiles")
    table_base_dir = Path(
        os.getenv("EXDBN_TABLE_BASE_DIR", str(DEFAULT_RESULTS_DIR))
    ).resolve()
    scenario_keys = [
        key.strip() for key in os.getenv("EXDBN_SCENARIO_KEYS", "").split(",")
        if key.strip() and key.strip().lower() != "all"
    ]
    method_text = args.methods or os.getenv("EXDBN_METHOD_KEYS", "")
    method_aliases = {"clique": "milp_clique", "edge-limit": "edge_limit"}
    all_methods = args.all_methods or os.getenv(
        "EXDBN_BENCHMARK_ALL_METHODS", "0"
    ).strip().lower() in {"1", "true", "yes", "on"}
    selected_solvers = None if all_methods else {
        method_aliases.get(key.strip().lower(), key.strip().lower())
        for key in method_text.split(",") if key.strip()
    } or None

    if raw_results_csv is not None and table_dir is not None:
        raise ValueError("Use only one of --raw-results or --table-dir")
    if raw_results_csv is None and table_dir is None:
        table_dirs = (
            [(table_base_dir / key).resolve() for key in scenario_keys]
            if scenario_keys else [DEFAULT_TABLE_DIR.resolve()]
        )
    else:
        table_dirs = [table_dir] if table_dir is not None else []

    if output_dir is None:
        output_dir = (
            raw_results_csv.parent if raw_results_csv is not None
            else Path(os.getenv("EXDBN_PLOT_OUTPUT_DIR", str(DEFAULT_REPORTS_DIR))).resolve()
        )

    solver_order = (
        tuple(selected_solvers) if selected_solvers is not None
        else active_solver_order(
            include_edge_limit=args.include_edge_limit,
            include_edge_limit_mean=args.include_edge_limit_mean,
        )
    )

    if raw_results_csv is not None:
        _raw_results_mode(
            raw_results_csv,
            output_dir,
            metrics,
            solver_order=solver_order,
            logscale=not args.no_semilog,
            output_png=output_png,
            mean_over_seeds=args.mean_over_seeds,
        )
    else:
        missing_dirs = [path for path in table_dirs if not path.exists()]
        if missing_dirs:
            raise ValueError(f"Table directories not found: {missing_dirs}")
        _table_dir_mode(
            table_dirs,
            output_dir,
            metrics,
            solver_order=solver_order,
            logscale=not args.no_semilog,
            scenario_key=args.scenario_key,
            output_png=output_png,
            mean_over_seeds=args.mean_over_seeds,
            include_edge_limit=args.include_edge_limit,
            include_edge_limit_mean=args.include_edge_limit_mean,
            selected_solvers=selected_solvers,
            all_methods=all_methods,
            output_prefix=output_prefix,
        )


if __name__ == "__main__":
    main()
