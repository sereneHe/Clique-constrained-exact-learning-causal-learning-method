#!/bin/sh
set -eu

cd /Users/xiaoyuhe/project-bestdagsolverintheworld
SCENARIO_KEYS_RAW="${EXDBN_SCENARIO_KEY:-cliquefree-er-5-0,cliquefree-sf-4-0,cliquefree-er-2-1}"
#,cliquefree-er-2-1
SCENARIO_KEYS="$(printf '%s' "${SCENARIO_KEYS_RAW}" | tr ',' ' ' | xargs)"
if [ -z "${SCENARIO_KEYS}" ]; then
  echo "EXDBN_SCENARIO_KEY is empty after parsing" >&2
  exit 2
fi

SCENARIO_TAG=""
PRIMARY_SCENARIO_KEY=""
SCENARIO_KEYS_CSV=""
SCENARIO_COUNT=0
for scenario_key in ${SCENARIO_KEYS}; do
  if [ -z "${PRIMARY_SCENARIO_KEY}" ]; then
    PRIMARY_SCENARIO_KEY="${scenario_key}"
  fi
  if [ -z "${SCENARIO_TAG}" ]; then
    SCENARIO_TAG="${scenario_key}"
  else
    SCENARIO_TAG="${SCENARIO_TAG}__${scenario_key}"
  fi
  if [ -z "${SCENARIO_KEYS_CSV}" ]; then
    SCENARIO_KEYS_CSV="${scenario_key}"
  else
    SCENARIO_KEYS_CSV="${SCENARIO_KEYS_CSV},${scenario_key}"
  fi
  SCENARIO_COUNT=$((SCENARIO_COUNT + 1))
done

ROOT_DIR="/Users/xiaoyuhe/project-bestdagsolverintheworld"
REPORTS_ROOT="${EXDBN_REPORTS_ROOT:-${ROOT_DIR}/dagsolvers/reports}"
RESULTS_ROOT="${EXDBN_RESULTS_ROOT:-${ROOT_DIR}/dagsolvers/results}"
EXDBN_RUN_DIR="${REPORTS_ROOT}/${SCENARIO_TAG}"
EXDBN_RESULTS_RUN_DIR="${RESULTS_ROOT}/${SCENARIO_TAG}"
REPORT_DIR="${EXDBN_REPORT_DIR:-${EXDBN_RUN_DIR}}"
PICS_DIR="${REPORT_DIR}"
RESULTS_REPORT_DIR="${EXDBN_RESULTS_REPORT_DIR:-${EXDBN_RESULTS_RUN_DIR}}"
TABLES_DIR="${RESULTS_REPORT_DIR}/tables"
MILP_TABLE_DIR="${EXDBN_MILP_TABLE_DIR:-}"
CLIQUE_TABLE_DIR="${EXDBN_CLIQUE_TABLE_DIR:-}"
LIMIT_TABLE_DIR="${EXDBN_LIMIT_TABLE_DIR:-}"
BENCHMARK_MEAN="${EXDBN_BENCHMARK_MEAN:-1}"
BENCHMARK_INCLUDE_EDGE_LIMIT="${EXDBN_BENCHMARK_INCLUDE_EDGE_LIMIT:-0}"
BENCHMARK_INCLUDE_EDGE_LIMIT_MEAN="${EXDBN_BENCHMARK_INCLUDE_EDGE_LIMIT_MEAN:-0}"
PLOT_TIME_LIMIT_TRENDS="${EXDBN_PLOT_TIME_LIMIT_TRENDS:-0}"
TIME_LIMIT_TREND_SAMPLE="${EXDBN_TIME_LIMIT_TREND_SAMPLE:-2000}"
TIME_LIMIT_TREND_D="${EXDBN_TIME_LIMIT_TREND_D:-25}"
REQUESTED_SAMPLES="${EXDBN_PLOT_SAMPLES:-both}"
case "${REQUESTED_SAMPLES}" in
  both)
    PLOT_SAMPLES="200 2000"
    ;;
  200|2000)
    PLOT_SAMPLES="${REQUESTED_SAMPLES}"
    ;;
  *)
    echo "EXDBN_PLOT_SAMPLES must be one of: both, 200, 2000" >&2
    exit 2
    ;;
esac

mkdir -p "${REPORT_DIR}" "${RESULTS_REPORT_DIR}" "${TABLES_DIR}"
rm -f "${REPORT_DIR}/benchmarkprofiles_lazy_count_allproblems.png"

TMP_TABLE_DIR=""
TMP_OUTPUT_DIR=""
cleanup() {
  if [ -n "${TMP_TABLE_DIR}" ] && [ -d "${TMP_TABLE_DIR}" ]; then
    rm -rf "${TMP_TABLE_DIR}"
  fi
  if [ -n "${TMP_OUTPUT_DIR}" ] && [ -d "${TMP_OUTPUT_DIR}" ]; then
    rm -rf "${TMP_OUTPUT_DIR}"
  fi
}
trap cleanup EXIT

TABLE_BASE_DIR=""
OUTPUT_PREFIX="exdbn_methods"
BENCHMARK_TABLE_DIR=""
BENCHMARK_OUTPUT_SUFFIX=""
BENCHMARK_MEAN_FLAG="--mean-over-seeds"
BENCHMARK_EDGE_LIMIT_FLAG="--include-edge-limit"
BENCHMARK_EDGE_LIMIT_MEAN_FLAG="--include-edge-limit-mean"
BENCHMARK_MEAN_FLAG="--no-mean-over-seeds"
BENCHMARK_EDGE_LIMIT_FLAG="--exclude-edge-limit"
BENCHMARK_EDGE_LIMIT_MEAN_FLAG="--exclude-edge-limit-mean"

TMP_TABLE_DIR="$(mktemp -d "${TMPDIR:-/tmp}/exdbn_plot_tables.XXXXXX")"
TMP_OUTPUT_DIR="$(mktemp -d "${TMPDIR:-/tmp}/exdbn_plot_outputs.XXXXXX")"
for sample in ${PLOT_SAMPLES}
do
  target_dir="${TMP_TABLE_DIR}/static_n${sample}"
  mkdir -p "${target_dir}"
  for scenario_key in ${SCENARIO_KEYS}
  do
    scenario_results_dir="${RESULTS_ROOT}/${scenario_key}"
    scenario_milp_dir="${MILP_TABLE_DIR:-${scenario_results_dir}}"
    scenario_clique_dir="${CLIQUE_TABLE_DIR:-${scenario_results_dir}}"
    scenario_limit_dir="${LIMIT_TABLE_DIR:-${scenario_results_dir}}"
    for csv_path in "${scenario_milp_dir}/static_n${sample}"/runtime_static_*.csv
    do
      [ -e "${csv_path}" ] || continue
      ln -s "${csv_path}" "${target_dir}/$(basename "${csv_path}")"
    done
    for csv_path in "${scenario_clique_dir}/static_n${sample}"/clique_runtime_static_*.csv
    do
      [ -e "${csv_path}" ] || continue
      ln -s "${csv_path}" "${target_dir}/$(basename "${csv_path}")"
    done
    for csv_path in "${scenario_limit_dir}/static_n${sample}"/limit_runtime_static_*.csv
    do
      [ -e "${csv_path}" ] || continue
      ln -s "${csv_path}" "${target_dir}/$(basename "${csv_path}")"
    done
  done
done
TABLE_BASE_DIR="${TMP_TABLE_DIR}"
BENCHMARK_TABLE_DIR="${TMP_TABLE_DIR}"

if [ "${PLOT_SAMPLES}" != "200 2000" ]; then
  OUTPUT_PREFIX="exdbn_methods_n${PLOT_SAMPLES}"
  BENCHMARK_OUTPUT_SUFFIX="_n${PLOT_SAMPLES}"
elif [ "${SCENARIO_COUNT}" -gt 1 ]; then
  OUTPUT_PREFIX="exdbn_methods_all"
fi

if [ "${SCENARIO_COUNT}" -gt 1 ]; then
  PLOT_LEGEND_STYLE="${EXDBN_LEGEND_STYLE:-half_running_time}"
  PLOT_SINGLE_SCENARIO_OUTPUT=0
else
  PLOT_LEGEND_STYLE="${EXDBN_LEGEND_STYLE:-single_data}"
  PLOT_SINGLE_SCENARIO_OUTPUT=1
fi

PLOT_EXDBN_CMD="EXDBN_LEGEND_STYLE=${PLOT_LEGEND_STYLE} EXDBN_SINGLE_SCENARIO_OUTPUT=${PLOT_SINGLE_SCENARIO_OUTPUT} EXDBN_TABLE_BASE_DIR=\"${TABLE_BASE_DIR}\" EXDBN_SCENARIO_KEYS=${SCENARIO_KEYS_CSV} EXDBN_PLOT_OUTPUT_DIR=\"${PICS_DIR}\" EXDBN_PLOT_OUTPUT_PREFIX=${OUTPUT_PREFIX} EXDBN_GENERATE_SUMMARY_TABLES=1 EXDBN_SUMMARY_MODES=static python3 dagsolvers/plot_utils_seperate.py"
eval "${PLOT_EXDBN_CMD}"

for summary_csv in "${TABLE_BASE_DIR}"/*.csv
do
  [ -e "${summary_csv}" ] || continue
  if [ -z "${BENCHMARK_OUTPUT_SUFFIX}" ]; then
    cp -f "${summary_csv}" "${TABLES_DIR}/$(basename "${summary_csv}")"
  else
    summary_name="$(basename "${summary_csv}" .csv)"
    cp -f "${summary_csv}" "${TABLES_DIR}/${summary_name}${BENCHMARK_OUTPUT_SUFFIX}.csv"
  fi
done

for sample in ${PLOT_SAMPLES}
do
  SAMPLE_OUTPUT_DIR="${TMP_OUTPUT_DIR}/n${sample}"
  SAMPLE_PLOT_DIR="${PICS_DIR}/n${sample}"
  mkdir -p "${SAMPLE_OUTPUT_DIR}" "${SAMPLE_PLOT_DIR}"
  python3 -u - "${TABLE_BASE_DIR}" "${SAMPLE_OUTPUT_DIR}" "${sample}" "${PRIMARY_SCENARIO_KEY}" "${REQUESTED_SAMPLES}" <<'PY'
from pathlib import Path
import sys

from dagsolvers.plot_benchmarkprofiles import plot_performance_from_exdbn_run_tables

table_base = Path(sys.argv[1])
output_base = Path(sys.argv[2])
sample = int(sys.argv[3])
plot_performance_from_exdbn_run_tables(
    table_dir=table_base / f"static_n{sample}",
    run_dir=output_base,
    scenario_key=sys.argv[4],
    samples=sample,
    metric="shd",
    output_suffix=f"n{sample}",
    dpi=200,
    write_plot=sys.argv[5] != "both",
)
PY
  mv -f "${SAMPLE_OUTPUT_DIR}/performance_summary_n${sample}.csv" "${TABLES_DIR}/performance_summary_n${sample}.csv"
  if [ "${REQUESTED_SAMPLES}" != "both" ]; then
    if [ "${SCENARIO_COUNT}" -eq 1 ]; then
      mv -f "${SAMPLE_OUTPUT_DIR}/performance_n${sample}.png" "${SAMPLE_PLOT_DIR}/performance_n${sample}.png"
    else
      rm -f "${SAMPLE_OUTPUT_DIR}/performance_n${sample}.png"
    fi
  fi
done

if [ "${PLOT_SAMPLES}" = "200 2000" ]; then
  python3 -u - "${TABLES_DIR}" "${PICS_DIR}" <<'PY'
from pathlib import Path
import sys

from dagsolvers.plot_benchmarkprofiles import plot_combined_performance_from_summaries

tables_dir = Path(sys.argv[1])
pics_dir = Path(sys.argv[2])
plot_combined_performance_from_summaries(
    summary_paths=[
        tables_dir / "performance_summary_n200.csv",
        tables_dir / "performance_summary_n2000.csv",
    ],
    output_plot=pics_dir / "performance.png",
    output_summary=tables_dir / "performance_summary.csv",
    dpi=200,
)
PY
  rm -f "${PICS_DIR}/n200/performance_n200.png" "${PICS_DIR}/n2000/performance_n2000.png"
  rmdir "${PICS_DIR}/n200" 2>/dev/null || true
  rmdir "${PICS_DIR}/n2000" 2>/dev/null || true
fi

for metric in best_shd runtime_seconds
do
  python3 dagsolvers/plot_benchmarkprofiles.py \
    --table-dir "${BENCHMARK_TABLE_DIR}" \
    --output-dir "${TMP_OUTPUT_DIR}" \
    "${BENCHMARK_MEAN_FLAG}" \
    "${BENCHMARK_EDGE_LIMIT_FLAG}" \
    "${BENCHMARK_EDGE_LIMIT_MEAN_FLAG}" \
    --metrics "${metric}" \
    --output-png "${PICS_DIR}/benchmarkprofiles_${metric}${BENCHMARK_OUTPUT_SUFFIX}.png"
  if [ -z "${BENCHMARK_OUTPUT_SUFFIX}" ]; then
    mv -f "${TMP_OUTPUT_DIR}/benchmarkprofiles_${metric}_data.csv" "${TABLES_DIR}/benchmarkprofiles_${metric}_data.csv"
  else
    mv -f "${TMP_OUTPUT_DIR}/benchmarkprofiles_${metric}_data.csv" "${TABLES_DIR}/benchmarkprofiles_${metric}_data${BENCHMARK_OUTPUT_SUFFIX}.csv"
  fi
done

if python3 - "${TABLE_BASE_DIR}" "${PLOT_SAMPLES}" <<'PY'
from pathlib import Path
import csv
import sys

report_dir = Path(sys.argv[1])
samples = sys.argv[2].split()
for sample in samples:
    static_dir = report_dir / f"static_n{sample}"
    for path in static_dir.glob("*.csv"):
        with path.open(newline="") as handle:
            reader = csv.DictReader(handle)
            if any((row.get("lazy_count") or "").strip() for row in reader):
                raise SystemExit(0)
raise SystemExit(1)
PY
then
  python3 dagsolvers/plot_benchmarkprofiles.py \
    --table-dir "${BENCHMARK_TABLE_DIR}" \
    --output-dir "${TMP_OUTPUT_DIR}" \
    "${BENCHMARK_MEAN_FLAG}" \
    "${BENCHMARK_EDGE_LIMIT_FLAG}" \
    "${BENCHMARK_EDGE_LIMIT_MEAN_FLAG}" \
    --metrics lazy_count \
    --output-png "${PICS_DIR}/benchmarkprofiles_lazy_count${BENCHMARK_OUTPUT_SUFFIX}.png"
  if [ -z "${BENCHMARK_OUTPUT_SUFFIX}" ]; then
    mv -f "${TMP_OUTPUT_DIR}/benchmarkprofiles_lazy_count_data.csv" "${TABLES_DIR}/benchmarkprofiles_lazy_count_data.csv"
  else
    mv -f "${TMP_OUTPUT_DIR}/benchmarkprofiles_lazy_count_data.csv" "${TABLES_DIR}/benchmarkprofiles_lazy_count_data${BENCHMARK_OUTPUT_SUFFIX}.csv"
  fi
fi

rm -f "${REPORT_DIR}/benchmarkprofiles_lazy_count_allproblems.png" "${PICS_DIR}/benchmarkprofiles_lazy_count_allproblems.png"

python3 dagsolvers/plot_time_limits.py \
      --report-dir "${REPORT_DIR}" \
      --sample-size "${TIME_LIMIT_TREND_SAMPLE}" \
      --d "${TIME_LIMIT_TREND_D}"
