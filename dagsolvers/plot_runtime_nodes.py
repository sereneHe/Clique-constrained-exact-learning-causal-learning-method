from __future__ import annotations

import os
import math
import re
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


ROOT = Path("/Users/xiaoyuhe/project-bestdagsolverintheworld/dagsolvers")
EXDBN_TABLE_BASE_DIR = Path(
    os.getenv("EXDBN_TABLE_BASE_DIR", str(ROOT / "results"))
).resolve()
EXDBN_PLOT_OUTPUT_DIR = Path(
    os.getenv("EXDBN_PLOT_OUTPUT_DIR", str(ROOT / "reports"))
).resolve()
EXDBN_PLOT_OUTPUT_PREFIX = os.getenv("EXDBN_PLOT_OUTPUT_PREFIX", "benchmarkprofiles")
EXDBN_GENERATE_SUMMARY_TABLES = os.getenv("EXDBN_GENERATE_SUMMARY_TABLES", "1")

DATA_NAME = EXDBN_TABLE_BASE_DIR.name
RESULTS_DIR = EXDBN_TABLE_BASE_DIR / "static_n200"
REPORT_DIR = EXDBN_PLOT_OUTPUT_DIR / DATA_NAME
OUTPUT_PNG = REPORT_DIR / f"{EXDBN_PLOT_OUTPUT_PREFIX}_{DATA_NAME}.png"
OUTPUT_CSV = RESULTS_DIR / "runtime_n200_cd_fit_summary.csv"

METHOD_SPECS = [
    ("EXDBN", f"runtime_static_{DATA_NAME}_gauss_d*_n200.csv", "#1f77b4"),
    ("Clique-width MILP", f"clique_runtime_static_{DATA_NAME}_gauss_d*_n200.csv", "#ff7f0e"),
]


def parse_d(path: Path) -> int:
    match = re.search(r"_d(\d+)_n200\.csv$", path.name)
    if match is None:
        raise ValueError(f"Cannot parse d from {path}")
    return int(match.group(1))


def read_method_points(pattern: str) -> pd.DataFrame:
    rows = []
    for csv_path in sorted(RESULTS_DIR.glob(pattern), key=parse_d):
        d = parse_d(csv_path)
        df = pd.read_csv(csv_path)
        runtimes = pd.to_numeric(df["runtime_seconds"], errors="coerce").dropna()
        if runtimes.empty:
            continue
        rows.append(
            {
                "d": d,
                "runtime_mean": float(runtimes.mean()),
                "runtime_sd": float(runtimes.std(ddof=1)) if len(runtimes) > 1 else 0.0,
                "n_rows": int(len(runtimes)),
            }
        )
    if not rows:
        return pd.DataFrame(columns=["d", "runtime_mean", "runtime_sd", "n_rows"])
    return pd.DataFrame(rows).sort_values("d").reset_index(drop=True)


def fit_scaled_power_d(d_values: np.ndarray, y_values: np.ndarray) -> tuple[float, float, np.ndarray]:
    """Fit runtime = a * c^d in log-space."""
    if len(d_values) == 0:
        return float("nan"), float("nan"), np.array([])
    log_y = np.log(y_values)
    design = np.column_stack([np.ones_like(d_values), d_values])
    log_a, log_c = np.linalg.lstsq(design, log_y, rcond=None)[0]
    a = math.exp(float(log_a))
    c = math.exp(log_c)
    return a, c, a * (c**d_values)


def main() -> None:
    REPORT_DIR.mkdir(parents=True, exist_ok=True)

    summary_rows = []
    fig, ax = plt.subplots(figsize=(7.0, 4.8), dpi=300)
    fit_specs: list[tuple[str, float, float, float, np.ndarray, np.ndarray, str]] = []

    for method, pattern, color in METHOD_SPECS:
        points = read_method_points(pattern)
        if points.empty:
            print(f"[SKIP] {method}: no runtime CSV matched {pattern}")
            continue

        d_values = points["d"].to_numpy(dtype=float)
        y_values = points["runtime_mean"].to_numpy(dtype=float)
        a, c, _ = fit_scaled_power_d(d_values, y_values)
        d_curve = np.linspace(d_values.min(), d_values.max(), 200)
        y_curve = a * (c**d_curve)
        fit_specs.append((method, a, c, d_values, d_curve, y_curve, color))

        for row in points.to_dict("records"):
            implied_c = row["runtime_mean"] ** (1.0 / row["d"])
            summary_rows.append(
                {
                    "method": method,
                    "d": row["d"],
                    "runtime_mean": row["runtime_mean"],
                    "runtime_sd": row["runtime_sd"],
                    "n_rows": row["n_rows"],
                    "point_implied_c": implied_c,
                    "fit_a": a,
                    "fit_c": c,
                }
            )

        ax.plot(
            d_curve,
            y_curve,
            linestyle="-",
            linewidth=2.8,
            color=color,
            label=method,
        )
        print(f"{method}: fitted runtime = a * c^d, a = {a:.6g}, c = {c:.6f}")

    ax.set_xlabel("Number of variables d")
    ax.set_ylabel("Runtime seconds")
    ax.set_title(f"{DATA_NAME}, n=200 runtime simulation")
    ax.set_xticks([7, 10, 13])
    ax.grid(True, which="both", linestyle=":", linewidth=0.7, alpha=0.55)
    ax.legend(frameon=False)

    x_min, x_max = ax.get_xlim()
    y_min, y_max = ax.get_ylim()
    y_span = y_max - y_min
    for method, a, c, d_values, d_curve, y_curve, color in fit_specs:
        if method == "EXDBN":
            x_pos = float(d_curve.min() + 0.15 * (d_curve.max() - d_curve.min()))
            ha = "left"
            y_offset = 0.06 * y_span
        else:
            x_pos = float(d_curve.max() - 0.10 * (d_curve.max() - d_curve.min()))
            ha = "right"
            y_offset = -0.05 * y_span

        y_pos = float(a * (c**x_pos) + y_offset)
        y_pos = min(max(y_pos, y_min + 0.03 * y_span), y_max - 0.03 * y_span)
        ax.text(
            x_pos,
            y_pos,
            rf"$y={a:.3g}\cdot{c:.3f}^d$",
            color=color,
            fontsize=11,
            ha=ha,
            va="center",
            bbox=dict(boxstyle="round,pad=0.2", fc="white", ec="none", alpha=0.75),
        )

    fig.tight_layout()
    fig.savefig(OUTPUT_PNG)
    plt.close(fig)

    summary = pd.DataFrame(summary_rows)
    summary.to_csv(OUTPUT_CSV, index=False)
    print(f"Wrote {OUTPUT_PNG}")
    print(f"Wrote {OUTPUT_CSV}")


if __name__ == "__main__":
    main()
