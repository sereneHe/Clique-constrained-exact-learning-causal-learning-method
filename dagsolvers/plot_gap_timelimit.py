from __future__ import annotations

import csv
import os
import re
from pathlib import Path

import matplotlib.pyplot as plt
from matplotlib.ticker import FormatStrFormatter
import pandas as pd
import yaml


ROOT = Path("/Users/xiaoyuhe/project-bestdagsolverintheworld/dagsolvers")
EXDBN_TABLE_BASE_DIR = Path(os.getenv("EXDBN_TABLE_BASE_DIR", str(ROOT / "results"))).resolve()
EXDBN_PLOT_OUTPUT_DIR = Path(os.getenv("EXDBN_PLOT_OUTPUT_DIR", str(ROOT / "reports"))).resolve()
EXDBN_PLOT_OUTPUT_PREFIX = os.getenv("EXDBN_PLOT_OUTPUT_PREFIX", "gap_timelimit")
EXDBN_GENERATE_SUMMARY_TABLES = os.getenv("EXDBN_GENERATE_SUMMARY_TABLES", "1")
EXDBN_MULTIRUN_DIR = Path(os.getenv("EXDBN_MULTIRUN_DIR", str(ROOT / "multirun"))).resolve()
GAP_D = int(os.getenv("EXDBN_GAP_D", "13"))
GAP_N = int(os.getenv("EXDBN_GAP_N", "200"))
GAP_SEM_TYPE = os.getenv("EXDBN_GAP_SEM_TYPE", "gauss")

DATA_NAME = EXDBN_TABLE_BASE_DIR.name
RESULTS_DIR = EXDBN_TABLE_BASE_DIR / f"static_n{GAP_N}"
REPORT_DIR = EXDBN_PLOT_OUTPUT_DIR / DATA_NAME
OUTPUT_PNG = REPORT_DIR / f"{EXDBN_PLOT_OUTPUT_PREFIX}_{DATA_NAME}.png"
Y_MIN_GAP_FRACTION = 0.0
Y_MAX_GAP_FRACTION = 0.3

MILP_CSV_NAME = f"log_milp_{DATA_NAME}_{GAP_SEM_TYPE}_d{GAP_D}_n{GAP_N}.csv"
CLIQUE_CSV_NAME = f"log_clique_{DATA_NAME}_{GAP_SEM_TYPE}_d{GAP_D}_n{GAP_N}.csv"
METHODS = {
    MILP_CSV_NAME: ("MILP", "#1f77b4"),
    CLIQUE_CSV_NAME: ("Clique-width MILP", "#ff7f0e"),
}

GUROBI_COLUMNS = [
    "Expl",
    "Unexpl",
    "Obj",
    "Depth",
    "IntInf",
    "Incumbent",
    "BestBd",
    "Gap",
    "It/Node",
    "Time",
]
LOG_SOURCES = {
    MILP_CSV_NAME: os.getenv("EXDBN_MILP_LOG"),
    CLIQUE_CSV_NAME: os.getenv("EXDBN_CLIQUE_LOG"),
}
LOG_PREFIX_RE = re.compile(r"\]\s+-\s?(.*)$")
INCUMBENT_ROW_RE = re.compile(
    r"^[H*]\s+(\d+)\s+(\d+)\s+(\S+)\s+(\S+)\s+"
    r"(\S+)%\s+(\S+)\s+(\S+)s$"
)
NODE_ROW_RE = re.compile(
    r"^(\d+)\s+(\d+)\s+(\S+)\s+(\d+)\s+(?:(\d+)\s+)?"
    r"(\S+)\s+(\S+)\s+(\S+)%\s+(\S+)\s+(\S+)s$"
)
DATA_NAME_RE = re.compile(r"^cliquefree-(er|sf)-(\d+)-(\d+)$")


def _empty_if_dash(value: str | None) -> str:
    return "" if value in {None, "-"} else value


def parse_gurobi_progress_line(line: str) -> list[str] | None:
    prefix_match = LOG_PREFIX_RE.search(line)
    message = (prefix_match.group(1) if prefix_match else line).strip()

    incumbent_match = INCUMBENT_ROW_RE.fullmatch(message)
    if incumbent_match:
        expl, unexpl, incumbent, best_bd, gap, it_per_node, time = incumbent_match.groups()
        return [
            expl,
            unexpl,
            "",
            "",
            "",
            _empty_if_dash(incumbent),
            _empty_if_dash(best_bd),
            _empty_if_dash(gap),
            _empty_if_dash(it_per_node),
            _empty_if_dash(time),
        ]

    node_match = NODE_ROW_RE.fullmatch(message)
    if not node_match:
        return None

    return [_empty_if_dash(value) for value in node_match.groups()]


def convert_gurobi_log_to_csv(log_path: Path, csv_path: Path) -> int:
    rows = []
    with log_path.open(encoding="utf-8", errors="replace") as log_file:
        for line in log_file:
            row = parse_gurobi_progress_line(line)
            if row is not None:
                rows.append(row)

    if not rows:
        raise ValueError(f"No Gurobi progress rows found in {log_path}")

    csv_path.parent.mkdir(parents=True, exist_ok=True)
    with csv_path.open("w", newline="", encoding="utf-8") as csv_file:
        writer = csv.writer(csv_file)
        writer.writerow(GUROBI_COLUMNS)
        writer.writerows(rows)

    return len(rows)


def _expected_problem_config() -> dict[str, object]:
    match = DATA_NAME_RE.fullmatch(DATA_NAME)
    if not match:
        raise ValueError(
            f"Cannot infer problem settings from EXDBN_TABLE_BASE_DIR name {DATA_NAME!r}; "
            "set EXDBN_MILP_LOG and EXDBN_CLIQUE_LOG explicitly."
        )
    graph_type, edge_ratio, lag = match.groups()
    return {
        "name": f"cliquefree_{graph_type}",
        "intra_edge_ratio": int(edge_ratio),
        "inter_edge_ratio": int(edge_ratio),
        "p": int(lag),
        "number_of_variables": GAP_D,
        "number_of_samples": GAP_N,
        "sem_type": GAP_SEM_TYPE,
    }


def _config_matches(config: dict, solver_names: set[str], expected_problem: dict) -> bool:
    solver = config.get("solver") or {}
    problem = config.get("problem") or {}
    if solver.get("name") not in solver_names:
        return False
    return all(problem.get(key) == value for key, value in expected_problem.items())


def find_matching_gurobi_log(solver_names: set[str]) -> Path | None:
    expected_problem = _expected_problem_config()
    candidates = []
    for config_path in EXDBN_MULTIRUN_DIR.glob("*/*/*/config.yaml"):
        log_path = config_path.with_name("run_experiments.log")
        if not log_path.is_file():
            continue
        try:
            with config_path.open(encoding="utf-8") as config_file:
                config = yaml.safe_load(config_file) or {}
        except (OSError, yaml.YAMLError):
            continue
        if not _config_matches(config, solver_names, expected_problem):
            continue
        if "Expl Unexpl" not in log_path.read_text(encoding="utf-8", errors="replace"):
            continue
        time_limit = float((config.get("solver") or {}).get("time_limit") or 0)
        candidates.append((time_limit, log_path.stat().st_mtime, log_path))

    if not candidates:
        return None
    return max(candidates, key=lambda candidate: candidate[:2])[2]


def generate_progress_csvs() -> None:
    solver_names = {
        MILP_CSV_NAME: {"milp"},
        CLIQUE_CSV_NAME: {"milp_clique", "clique"},
    }
    for filename, explicit_source in LOG_SOURCES.items():
        log_path = (
            Path(explicit_source).expanduser().resolve()
            if explicit_source
            else find_matching_gurobi_log(solver_names[filename])
        )
        if log_path is None:
            print(
                f"[SKIP] no matching {next(iter(solver_names[filename]))} log under "
                f"{EXDBN_MULTIRUN_DIR} for {DATA_NAME}, d={GAP_D}, n={GAP_N}"
            )
            continue
        if not log_path.is_file():
            raise FileNotFoundError(f"Gurobi log not found: {log_path}")
        csv_path = RESULTS_DIR / filename
        row_count = convert_gurobi_log_to_csv(log_path, csv_path)
        print(f"Wrote {csv_path} from {log_path} ({row_count} Gurobi progress rows)")


def read_gap_time(path: Path) -> pd.DataFrame:
    df = pd.read_csv(path)
    out = pd.DataFrame(
        {
            "time_seconds": pd.to_numeric(df["Time"], errors="coerce"),
            # Gurobi logs store gap in percent, convert to a decimal fraction.
            "gap_fraction": pd.to_numeric(df["Gap"], errors="coerce") / 100.0,
        }
    ).dropna()
    return out


def main() -> None:
    generate_progress_csvs()
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    fig, ax = plt.subplots(figsize=(8.0, 5.0), dpi=300)

    for filename, (label, color) in METHODS.items():
        path = RESULTS_DIR / filename
        if not path.exists():
            print(f"[SKIP] missing {path}")
            continue
        data = read_gap_time(path)
        if data.empty:
            print(f"[SKIP] no gap/time rows in {path}")
            continue
        ax.plot(
            data["time_seconds"],
            data["gap_fraction"],
            linewidth=2.2,
            color=color,
            label=label,
        )
        print(
            f"{label}: {len(data)} points, "
            f"last time={data['time_seconds'].iloc[-1]:.0f}s, "
            f"last gap={data['gap_fraction'].iloc[-1]:.3f}"
        )

    ax.set_xlabel("Time (seconds)")
    ax.set_ylabel("MIP gap")
    ax.set_title(f"{DATA_NAME}, d={GAP_D}, n={GAP_N}: Gap vs Time")
    ax.grid(True, linestyle=":", linewidth=0.7, alpha=0.6)
    ax.legend(frameon=False)
    ax.set_ylim(Y_MIN_GAP_FRACTION, Y_MAX_GAP_FRACTION)
    ax.set_yticks([0.0, 0.1, 0.2, 0.3])
    ax.yaxis.set_major_formatter(FormatStrFormatter("%.2f"))
    fig.tight_layout()
    fig.savefig(OUTPUT_PNG)
    plt.close(fig)
    print(f"Wrote {OUTPUT_PNG}")


if __name__ == "__main__":
    main()
