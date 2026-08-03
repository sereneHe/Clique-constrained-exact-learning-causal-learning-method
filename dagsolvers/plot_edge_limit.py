from __future__ import annotations

import argparse
from pathlib import Path

try:
    from dagsolvers.plot_helpers import (
        build_edge_limit_summaries,
        generate_edge_limit_summaries,
        infer_edge_limit_source_label as _infer_source_label,
        plot_edge_limit_summary as plot_summary,
    )
except ModuleNotFoundError:
    from plot_helpers import (  # type: ignore
        build_edge_limit_summaries,
        generate_edge_limit_summaries,
        infer_edge_limit_source_label as _infer_source_label,
        plot_edge_limit_summary as plot_summary,
    )


DEFAULT_REPORT_DIR = Path(
    "/Users/xiaoyuhe/project-bestdagsolverintheworld/dagsolvers/reports/sf-5-0/SF-5-0-1800s"
)
DEFAULT_SUMMARY_CSV = Path(
    "/Users/xiaoyuhe/project-bestdagsolverintheworld/dagsolvers/results/sf-5-0/"
    "SF-5-0-1800s/tables/edge_limit_min_gap_summary.csv"
)
DEFAULT_OUTPUT_PNG = Path(
    "/Users/xiaoyuhe/project-bestdagsolverintheworld/dagsolvers/reports/sf-5-0/"
    "SF-5-0-1800s/edge_limit_stable_degree_gap.png"
)
DEFAULT_GAP_OUTPUT_PNG = Path(
    "/Users/xiaoyuhe/project-bestdagsolverintheworld/dagsolvers/reports/sf-5-0/"
    "SF-5-0-1800s/edge_limit_stable_gap.png"
)
DEFAULT_SHD_DEGREE_OUTPUT_PNG = Path(
    "/Users/xiaoyuhe/project-bestdagsolverintheworld/dagsolvers/reports/sf-5-0/"
    "SF-5-0-1800s/edge_limit_stable_degree_shd.png"
)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Generate edge-limit summary tables and plot stable degree/gap curves "
            "for n=200 and n=2000."
        )
    )
    parser.add_argument(
        "--report-dir",
        type=Path,
        default=DEFAULT_REPORT_DIR,
        help="Report run directory, used to locate static_n200/static_n2000 results.",
    )
    parser.add_argument(
        "--summary-csv",
        type=Path,
        default=None,
        help="Optional summary CSV path. If omitted, summaries are generated from --report-dir.",
    )
    parser.add_argument(
        "--summary-output-dir",
        type=Path,
        default=None,
        help="Where to write generated summary CSVs. Defaults to the matching results/.../tables dir.",
    )
    parser.add_argument(
        "--output-png",
        type=Path,
        default=None,
        help="Where to save the PNG plot.",
    )
    parser.add_argument(
        "--source",
        choices=("gap", "shd"),
        default="gap",
        help="Which summary source to use for degree plots when --summary-csv is omitted.",
    )
    parser.add_argument(
        "--metric",
        choices=("degree", "gap"),
        default="degree",
        help="Which quantity to plot from the summary table.",
    )
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    report_dir = args.report_dir.resolve()
    if args.summary_csv is None:
        shd_path, gap_path = generate_edge_limit_summaries(report_dir, args.summary_output_dir)
        summary_csv = shd_path if args.source == "shd" else gap_path
        print(shd_path)
        print(gap_path)
    else:
        summary_csv = args.summary_csv.resolve()

    if args.output_png is None:
        if args.metric == "gap":
            output_png = DEFAULT_GAP_OUTPUT_PNG
        else:
            output_png = (
                DEFAULT_SHD_DEGREE_OUTPUT_PNG
                if _infer_source_label(summary_csv) == "shd"
                else DEFAULT_OUTPUT_PNG
            )
    else:
        output_png = args.output_png.resolve()
    plot_summary(summary_csv, output_png, metric=args.metric)
    print(output_png)


if __name__ == "__main__":
    main()
