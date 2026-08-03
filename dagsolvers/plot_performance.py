from __future__ import annotations

import argparse
import os
import shutil
import tempfile
from pathlib import Path

try:
    from dagsolvers.plot_helpers import (
        plot_combined_performance_from_summaries,
        plot_performance_from_exdbn_run_tables,
    )
except ModuleNotFoundError:
    from plot_helpers import (  # type: ignore
        plot_combined_performance_from_summaries,
        plot_performance_from_exdbn_run_tables,
    )


DEFAULT_REPORT_DIR = Path(
    "/Users/xiaoyuhe/project-bestdagsolverintheworld/dagsolvers/reports/cliquefree-er-5-0"
)
DEFAULT_RESULTS_ROOT = Path("/Users/xiaoyuhe/project-bestdagsolverintheworld/dagsolvers/results")


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate EXDBN performance plots from static result tables.")
    parser.add_argument(
        "--report-dir",
        type=Path,
        default=Path(os.environ.get("EXDBN_REPORT_DIR", DEFAULT_REPORT_DIR)),
        help="Output report directory, for example .../reports/cliquefree-er-5-0.",
    )
    parser.add_argument(
        "--sample-size",
        type=int,
        nargs="*",
        default=None,
        help="Sample sizes to plot, for example 200 2000. Defaults to both.",
    )
    parser.add_argument(
        "--d",
        type=int,
        nargs="*",
        default=None,
        help="Optional d values to keep in the performance summaries and plots.",
    )
    parser.add_argument(
        "--scenario-key",
        nargs="*",
        default=None,
        help="Optional scenario keys. Defaults to EXDBN_SCENARIO_KEY or the report directory name.",
    )
    return parser.parse_args()


def _scenario_keys(args: argparse.Namespace) -> list[str]:
    if args.scenario_key:
        keys = [key.strip() for key in args.scenario_key if key.strip()]
        if keys:
            return keys

    env_value = os.environ.get("EXDBN_SCENARIO_KEY", "").strip()
    if env_value:
        keys = [key.strip() for key in env_value.replace(",", " ").split() if key.strip()]
        if keys:
            return keys

    return [key for key in args.report_dir.name.split("__") if key]


def _sample_sizes(args: argparse.Namespace) -> list[int]:
    if args.sample_size is None:
        env_value = os.environ.get("EXDBN_PLOT_SAMPLES", "both").strip()
        if env_value == "both":
            return [200, 2000]
        return [int(env_value)]
    if not args.sample_size:
        raise SystemExit("--sample-size requires at least one integer or should be omitted.")
    return sorted(set(int(value) for value in args.sample_size))


def _results_root(report_dir: Path) -> Path:
    env_root = os.environ.get("EXDBN_RESULTS_ROOT")
    if env_root:
        return Path(env_root)
    return report_dir.parent.parent / "results"


def _scenario_results_dir(report_dir: Path, scenario_key: str) -> Path:
    return _results_root(report_dir) / scenario_key


def _override_dir(env_name: str, fallback: Path) -> Path:
    override = os.environ.get(env_name, "").strip()
    return Path(override) if override else fallback


def _symlink_csvs(src_dir: Path, dst_dir: Path, pattern: str) -> None:
    if not src_dir.exists():
        return
    for csv_path in sorted(src_dir.glob(pattern)):
        if not csv_path.exists():
            continue
        target = dst_dir / csv_path.name
        if target.exists() or target.is_symlink():
            target.unlink()
        target.symlink_to(csv_path)


def main() -> None:
    args = _parse_args()
    report_dir = args.report_dir.resolve()
    report_dir.mkdir(parents=True, exist_ok=True)

    scenario_keys = _scenario_keys(args)
    if not scenario_keys:
        raise SystemExit("No scenario keys could be resolved.")
    primary_scenario_key = scenario_keys[0]
    sample_sizes = _sample_sizes(args)
    allowed_d_values = set(int(value) for value in args.d) if args.d else None

    results_root = _results_root(report_dir)
    results_report_dir = results_root / report_dir.name
    tables_dir = results_report_dir / "tables"
    tables_dir.mkdir(parents=True, exist_ok=True)

    tmp_tables_root = Path(tempfile.mkdtemp(prefix="exdbn_performance_tables_"))
    try:
        summary_paths: list[Path] = []
        for sample_size in sample_sizes:
            table_dir = tmp_tables_root / f"static_n{sample_size}"
            table_dir.mkdir(parents=True, exist_ok=True)

            for scenario_key in scenario_keys:
                scenario_results_dir = _scenario_results_dir(report_dir, scenario_key)
                scenario_milp_dir = _override_dir("EXDBN_MILP_TABLE_DIR", scenario_results_dir)
                scenario_clique_dir = _override_dir("EXDBN_CLIQUE_TABLE_DIR", scenario_results_dir)
                scenario_limit_dir = _override_dir("EXDBN_LIMIT_TABLE_DIR", scenario_results_dir)

                _symlink_csvs(scenario_milp_dir / f"static_n{sample_size}", table_dir, "runtime_static_*.csv")
                _symlink_csvs(scenario_clique_dir / f"static_n{sample_size}", table_dir, "clique_runtime_static_*.csv")
                _symlink_csvs(scenario_limit_dir / f"static_n{sample_size}", table_dir, "limit_runtime_static_*.csv")

            sample_run_dir = report_dir / f"n{sample_size}"
            sample_run_dir.mkdir(parents=True, exist_ok=True)
            result = plot_performance_from_exdbn_run_tables(
                table_dir=table_dir,
                run_dir=sample_run_dir,
                scenario_key=primary_scenario_key,
                samples=sample_size,
                metric="shd",
                output_suffix=f"n{sample_size}",
                dpi=200,
                write_plot=True,
                allowed_d_values=allowed_d_values,
            )
            summary_path = Path(result["summary"])
            summary_paths.append(summary_path)
            shutil.copy2(summary_path, tables_dir / summary_path.name)

        if len(sample_sizes) > 1:
            plot_combined_performance_from_summaries(
                summary_paths=summary_paths,
                output_plot=report_dir / "performance.png",
                output_summary=tables_dir / "performance_summary.csv",
                dpi=200,
            )
    finally:
        shutil.rmtree(tmp_tables_root, ignore_errors=True)


if __name__ == "__main__":
    main()
