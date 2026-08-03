"""Plot paired SHD differences between Clique variants and an ExDBN baseline.

The entry point intentionally follows the environment-variable interface used
by ``scripts/plot1.sh``.  For every dataset, sample size, node count, and time
limit, it computes

    delta SHD = SHD(Clique variant) - SHD(ExDBN).

Negative values therefore favour the Clique variant.  ExDBN is represented by
the horizontal zero line instead of an additional series.
"""

from __future__ import annotations

import os
from pathlib import Path

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from plot_utils_seperate import (
    _env_bool,
    _env_number_list,
    _legend_method_labels,
    _runtime_method_specs,
    generate_all_runtime_summary_tables,
)


ROOT = Path(__file__).resolve().parent
RESULTS_DIR = Path(
    os.getenv("EXDBN_TABLE_BASE_DIR", str(ROOT / "results"))
).resolve()
OUTPUT_DIR = Path(
    os.getenv("EXDBN_PLOT_OUTPUT_DIR", str(ROOT / "reports"))
).resolve()
OUTPUT_PREFIX = os.getenv("EXDBN_PLOT_OUTPUT_PREFIX", "exdbn_baseline")


def _csv_list(name: str, default: str) -> list[str]:
    raw = os.getenv(name, default)
    return [item.strip() for item in raw.split(",") if item.strip()]


def _load_method_table(method_key: str, scenario: str) -> pd.DataFrame:
    spec = _runtime_method_specs([method_key])[method_key]
    path = RESULTS_DIR / spec["summary_name"](scenario)
    if not path.exists():
        return pd.DataFrame()

    frame = pd.read_csv(path)
    if frame.empty:
        return frame

    frame = frame.copy()
    frame["method_key"] = method_key
    frame["scenario"] = scenario
    for column in ("features", "samples", "timelimit", "shd", "shd_std"):
        if column in frame.columns:
            frame[column] = pd.to_numeric(frame[column], errors="coerce")
    return frame


def _prepare_delta_rows(
    scenarios: list[str],
    method_keys: list[str],
    baseline_key: str,
    timelimits: list[float] | None,
    features: list[int] | None,
) -> pd.DataFrame:
    key_columns = ["scenario", "features", "samples", "timelimit"]
    delta_frames: list[pd.DataFrame] = []

    for scenario in scenarios:
        baseline = _load_method_table(baseline_key, scenario)
        if baseline.empty:
            print(f"[DELTA-SHD] missing baseline={baseline_key} scenario={scenario}")
            continue

        baseline = baseline.dropna(subset=["features", "samples", "shd"]).copy()
        if timelimits:
            baseline = baseline[
                baseline["timelimit"].isin({float(value) for value in timelimits})
            ]
        if features:
            baseline = baseline[
                baseline["features"].isin({int(value) for value in features})
            ]

        # A summary should contain one row per experimental key.  Grouping also
        # makes the pairing deterministic if an older summary contains repeats.
        baseline = (
            baseline.groupby(key_columns, as_index=False)
            .agg(baseline_shd=("shd", "mean"), baseline_shd_std=("shd_std", "mean"))
        )

        for method_key in method_keys:
            if method_key == baseline_key:
                continue
            method = _load_method_table(method_key, scenario)
            if method.empty:
                print(f"[DELTA-SHD] missing method={method_key} scenario={scenario}")
                continue
            method = method.dropna(subset=["features", "samples", "shd"]).copy()
            if timelimits:
                method = method[
                    method["timelimit"].isin(
                        {float(value) for value in timelimits}
                    )
                ]
            if features:
                method = method[
                    method["features"].isin({int(value) for value in features})
                ]

            method = (
                method.groupby(key_columns, as_index=False)
                .agg(method_shd=("shd", "mean"), method_shd_std=("shd_std", "mean"))
            )
            paired = method.merge(
                baseline,
                on=key_columns,
                how="inner",
                validate="one_to_one",
            )
            if paired.empty:
                print(
                    f"[DELTA-SHD] no paired rows method={method_key} "
                    f"scenario={scenario}"
                )
                continue

            paired["method_key"] = method_key
            paired["delta_shd"] = (
                paired["method_shd"] - paired["baseline_shd"]
            )
            # The two estimates come from matched seeds but only aggregate
            # standard deviations are available in the legacy summary tables.
            # The root-sum-square band is therefore shown as descriptive
            # uncertainty rather than a paired confidence interval.
            paired["delta_shd_std"] = np.sqrt(
                paired["method_shd_std"].fillna(0.0) ** 2
                + paired["baseline_shd_std"].fillna(0.0) ** 2
            )
            delta_frames.append(paired)

    if not delta_frames:
        return pd.DataFrame()
    return pd.concat(delta_frames, ignore_index=True)


def _plot_delta_shd(
    delta: pd.DataFrame,
    scenarios: list[str],
    output_prefix: str,
) -> tuple[Path, Path]:
    sample_values = [
        int(value) for value in sorted(delta["samples"].dropna().unique())
    ]
    plotted_scenarios = [
        scenario
        for scenario in scenarios
        if (delta["scenario"] == scenario).any()
    ]
    if not sample_values or not plotted_scenarios:
        raise RuntimeError("No paired SHD rows remain after filtering.")

    nrows = len(plotted_scenarios)
    ncols = len(sample_values)
    fig, axes = plt.subplots(
        nrows,
        ncols,
        figsize=(5.0 * ncols, 2.8 * nrows),
        sharex=False,
        sharey=True,
        squeeze=False,
    )

    labels = _legend_method_labels("standard")
    method_order = list(dict.fromkeys(delta["method_key"].tolist()))
    colors = plt.get_cmap("tab10").colors
    color_map = {
        method: colors[index % len(colors)]
        for index, method in enumerate(method_order)
    }

    lower = (
        delta["delta_shd"] - delta["delta_shd_std"].fillna(0.0)
    ).min()
    upper = (
        delta["delta_shd"] + delta["delta_shd_std"].fillna(0.0)
    ).max()
    span = max(float(upper - lower), 1.0)
    y_min = min(float(lower - 0.08 * span), -1.0)
    y_max = max(float(upper + 0.08 * span), 1.0)

    for row, scenario in enumerate(plotted_scenarios):
        for column, sample_size in enumerate(sample_values):
            ax = axes[row][column]
            panel = delta[
                (delta["scenario"] == scenario)
                & (delta["samples"] == sample_size)
            ]

            ax.axhspan(y_min, 0.0, color="#e8f5e9", alpha=0.75, zorder=0)
            ax.axhline(
                0.0,
                color="#424242",
                linewidth=1.2,
                linestyle="--",
                zorder=2,
            )

            for method in method_order:
                series = panel[panel["method_key"] == method].sort_values(
                    "features"
                )
                if series.empty:
                    continue
                x = series["features"].to_numpy(dtype=float)
                y = series["delta_shd"].to_numpy(dtype=float)
                sd = series["delta_shd_std"].fillna(0.0).to_numpy(dtype=float)
                label = labels.get(
                    _runtime_method_specs([method])[method]["plot_method"],
                    method,
                )
                ax.plot(
                    x,
                    y,
                    marker="o",
                    markersize=3.4,
                    linewidth=1.4,
                    color=color_map[method],
                    label=label,
                    zorder=3,
                )
                ax.fill_between(
                    x,
                    y - sd,
                    y + sd,
                    color=color_map[method],
                    alpha=0.12,
                    linewidth=0,
                    zorder=1,
                )

            ax.set_ylim(y_min, y_max)
            ax.grid(axis="both", alpha=0.18)
            ax.set_title(f"{scenario} · n={sample_size}")
            ax.set_xlabel("Number of nodes (d)")
            if column == 0:
                ax.set_ylabel(
                    r"$\Delta$SHD = SHD$_{\mathrm{method}}$ "
                    r"$-$ SHD$_{\mathrm{ExDBN}}$"
                )
            ax.text(
                0.01,
                0.02,
                "Clique variant better",
                transform=ax.transAxes,
                fontsize=8,
                color="#2e7d32",
                va="bottom",
            )

    handles: list[object] = []
    legend_labels: list[str] = []
    for ax_row in axes:
        for ax in ax_row:
            for handle, label in zip(
                *ax.get_legend_handles_labels()
            ):
                if label not in legend_labels:
                    handles.append(handle)
                    legend_labels.append(label)
    if handles:
        fig.legend(
            handles,
            legend_labels,
            loc="upper center",
            bbox_to_anchor=(0.5, 1.01),
            ncol=min(len(handles), 4),
            frameon=False,
        )

    fig.suptitle(
        "SHD difference relative to ExDBN",
        y=1.045,
        fontsize=13,
    )
    fig.tight_layout()

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    png_path = OUTPUT_DIR / f"{output_prefix}_delta_shd.png"
    pdf_path = OUTPUT_DIR / f"{output_prefix}_delta_shd.pdf"
    fig.savefig(png_path, dpi=300, bbox_inches="tight")
    fig.savefig(pdf_path, bbox_inches="tight")
    plt.close(fig)
    return png_path, pdf_path


def main() -> None:
    scenarios = _csv_list(
        "EXDBN_SCENARIO_KEYS",
        "cliquefree-er-4-0,cliquefree-er-5-0,cliquefree-sf-5-0",
    )
    method_keys = _csv_list(
        "EXDBN_METHOD_KEYS",
        "clique,clique_B3,clique_C3",
    )
    baseline_keys = _csv_list("EXDBN_BASELINE_METHOD_KEYS", "milp")
    if len(baseline_keys) != 1:
        raise ValueError(
            "EXDBN_BASELINE_METHOD_KEYS must contain exactly one baseline."
        )
    baseline_key = baseline_keys[0]
    timelimits = _env_number_list("EXDBN_TIMELIMITS", float)
    features = _env_number_list("EXDBN_FEATURES", int)
    modes = tuple(
        _csv_list("EXDBN_SUMMARY_MODES", "static")
    )

    all_methods = list(dict.fromkeys([baseline_key, *method_keys]))
    if _env_bool("EXDBN_GENERATE_SUMMARY_TABLES", default=True):
        generated = generate_all_runtime_summary_tables(
            base_dir=str(RESULTS_DIR),
            modes=modes,
            method_keys=",".join(all_methods),
        )
        print(f"[DELTA-SHD] generated {len(generated)} summary tables")

    delta = _prepare_delta_rows(
        scenarios=scenarios,
        method_keys=method_keys,
        baseline_key=baseline_key,
        timelimits=timelimits,
        features=features,
    )
    if delta.empty:
        raise RuntimeError(
            "No matched ExDBN/Clique SHD observations were found. "
            "Check EXDBN_SCENARIO_KEYS, EXDBN_METHOD_KEYS, and "
            "EXDBN_TIMELIMITS."
        )

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    summary_path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_delta_shd.csv"
    delta.sort_values(
        ["scenario", "samples", "features", "method_key"]
    ).to_csv(summary_path, index=False)
    png_path, pdf_path = _plot_delta_shd(
        delta=delta,
        scenarios=scenarios,
        output_prefix=OUTPUT_PREFIX,
    )
    print(f"[DELTA-SHD] paired rows: {len(delta)}")
    print(f"[DELTA-SHD] summary: {summary_path}")
    print(f"[DELTA-SHD] figure: {png_path}")
    print(f"[DELTA-SHD] figure: {pdf_path}")


if __name__ == "__main__":
    main()
