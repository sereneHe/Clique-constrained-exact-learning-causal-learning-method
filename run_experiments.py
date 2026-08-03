import csv
import atexit
import json
import os
import re
import subprocess
import sys
import threading
import time
import logging
from os.path import join
from pathlib import Path

CURRENT_DIR = Path(__file__).resolve().parent
PARENT_DIR = CURRENT_DIR.parent
if str(PARENT_DIR) not in sys.path:
    sys.path.insert(0, str(PARENT_DIR))

import hydra
import numpy as np
from hydra.core.hydra_config import HydraConfig
from mlflow import log_metric, log_text

from dagsolvers.ploting_utils import make_plots
from dagsolvers.solve_causal_learn import solve_fci

from dagsolvers.solvers.IPBMandHforCGL.solver_ipbm import solve_ipbm
from dagsolvers.sortnregress import sortnregress
from dagsolvers.varsortability import varsortability

logger = logging.getLogger(__name__)

from omegaconf import DictConfig, OmegaConf, open_dict

from dagsolvers.dagsolver_utils import plot, \
    find_optimal_multiple_thresholds, ExDagDataException, plot_heatmap
from dagsolvers.data_generation_loading_utils import load_problem, normalize_data
from dagsolvers.experiments_utils import log_params_from_omegaconf_dict, log_system_info
from dagsolvers.metrics_utils import calculate_metrics, calculate_metrics_pag, count_accuracy, compute_norm_distance, \
    least_square_cost, apply_threshold, find_optimal_threshold_for_shd
from dagsolvers.utils import log_exceptions
from dagsolvers import (
    solve_exmag,
    solve_gobnilp,
    solve_milp,
    solve_milp_clique,
    solve_milp_cliquewidth,
    solve_milp_edge_limit,
)
import dagsolvers.tracking_utils as tu
from notears import utils, linear
from structure.dynotears import from_numpy_dynamic


PROJECT_DIR = Path(__file__).resolve().parent
REPO_ROOT = PROJECT_DIR.parent
DEFAULT_RESULTS_ROOT = PROJECT_DIR / 'results'
DEFAULT_MULTIRUN_ROOT = PROJECT_DIR / 'multirun'

_SUMMARY_REFRESHER_STARTED = False
_SUMMARY_REFRESH_LOCK = threading.Lock()


STATIC_RUNTIME_COLUMNS = [
    'method_variant', 'experiment',
    'dataset', 'features', 'samples', 'p', 'edge_ratio', 'degree',
    'ori_graph_density', 'after_cliquefree_density', 'true_linear_r2',
    'big_m', 'runtime_seconds', 'gap', 'shd', 'f1score',
    'cycle_lazy_cuts', 'clique_lazy_cuts', 'clique_user_cuts',
    'cycle_unique_cuts', 'clique_unique_cuts', 'cycle_duplicate_cuts',
    'clique_duplicate_cuts', 'unique_cuts', 'duplicate_cuts', 'cut_hit_pct',
    'status', 'method_family', 'seed',
    'time_limit', 'true_edges', 'true_mean_abs_w', 'best_incumbent',
    'best_bound', 'root_bound', 'bound_gain', 'explored_nodes', 'open_nodes',
    'nodes_per_s', 'solution_count', 'g_score', 'nnz', 'fdr', 'tpr', 'fpr',
    'precision', 'mipsol_total', 'mipsol_rejected', 'mipsol_accepted',
    'mipsol_rejection_pct', 'cycle_only_candidates', 'clique_only_candidates',
    'both_candidates', 'violation_overlap_pct', 'cycle_callback_count',
    'clique_callback_count', 'cycle_separation_attempts',
    'clique_separation_attempts', 'root_fractional_edges',
    'root_fractional_x_bins', 'root_small_x_large_w', 'root_mean_big_m_ratio',
    'root_violated_cliques', 'root_max_clique_violation',
    'bound_gain_per_1k_nodes', 'dual_gain_per_cut', 'dual_gain_per_s',
    'mipnode_total', 'lp_iterations', 'lp_iter_per_node', 'lp_iter_per_s',
    'callback_s', 'callback_pct', 'search_s', 'cycle_callback_s',
    'clique_callback_s', 'cycle_detection_s', 'cycle_submission_s',
    'clique_detection_s', 'clique_submission_s', 'mip_progress_times',
    'checkpoint_explored_nodes', 'checkpoint_open_nodes',
    'checkpoint_best_bound', 'checkpoint_incumbent', 'checkpoint_gap',
    'checkpoint_status', 'checkpoint_solution_count', 'checkpoint_DAG',
    'checkpoint_SHD', 'checkpoint_F1', 'checkpoint_NNZ',
    'best_incumbent_edges', 'best_incumbent_weights', 'W_true_path', 'run_dir',
]

COMPACT_STATIC_RUNTIME_COLUMNS = [
    'method', 'dataset', 'features', 'samples', 'p', 'edge_ratio', 'degree',
    'ori_graph_density', 'after_cliquefree_density', 'true_linear_r2', 'big_m',
    'runtime_seconds', 'gap', 'fdr', 'tpr', 'fpr', 'shd', 'nnz',
    'precision', 'f1score', 'g_score', 'lazy_count', 'cycle_lazy_count',
    'clique_lazy_count', 'clique_user_count',
]

CLIQUE_FAMILY_SOLVERS = {
    'milp_clique',
    'milp_cliquewidth',
}


def _env_flag(name):
    return os.getenv(name, '').strip().lower() in {'1', 'true', 'yes', 'on'}


def _refresh_batch_summary():
    """Atomically rebuild the active batch's standard 25-column summary."""
    output = os.getenv('EXDBN_BATCH_SUMMARY_OUTPUT', '').strip()
    static_root = os.getenv('EXDBN_STATIC_CSV_BASE_DIR', '').strip()
    if not output or not static_root or not _SUMMARY_REFRESH_LOCK.acquire(blocking=False):
        return
    try:
        rows = []
        for path in sorted(Path(static_root).glob('**/*.csv')):
            try:
                with path.open(newline='') as handle:
                    reader = csv.DictReader(handle)
                    if not reader.fieldnames:
                        continue
                    for source in reader:
                        row = {
                            column: source.get(column, '')
                            for column in COMPACT_STATIC_RUNTIME_COLUMNS
                        }
                        if not row.get('method'):
                            name = path.name
                            if name.startswith('runtime_'):
                                row['method'] = 'exdbn'
                            elif name.startswith('clique_'):
                                match = re.match(r'clique_([^_]+)_runtime_', name)
                                row['method'] = (
                                    f'clique-{match.group(1)}'
                                    if match else 'clique'
                                )
                        rows.append(row)
            except OSError:
                continue
        output_path = Path(output)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        temporary = output_path.with_name(
            f'.{output_path.name}.{os.getpid()}.tmp'
        )
        with temporary.open('w', newline='') as handle:
            writer = csv.DictWriter(
                handle,
                fieldnames=COMPACT_STATIC_RUNTIME_COLUMNS,
            )
            writer.writeheader()
            writer.writerows(rows)
        os.replace(temporary, output_path)
        print(f'[BATCH SUMMARY] Wrote {len(rows)} rows to {output_path}')
    finally:
        _SUMMARY_REFRESH_LOCK.release()


def _start_batch_summary_refresher():
    global _SUMMARY_REFRESHER_STARTED
    if _SUMMARY_REFRESHER_STARTED or not os.getenv('EXDBN_BATCH_SUMMARY_OUTPUT'):
        return
    _SUMMARY_REFRESHER_STARTED = True
    interval = max(10.0, float(os.getenv('EXDBN_SUMMARY_REFRESH_SECONDS', '300')))

    def refresh_loop():
        while True:
            time.sleep(interval)
            _refresh_batch_summary()

    threading.Thread(target=refresh_loop, name='batch-summary-refresher', daemon=True).start()
    atexit.register(_refresh_batch_summary)


def _static_clique_case_label(experiment):
    """Return the stable filename label for an A--G clique experiment."""
    experiment = str(experiment or '')
    labels = (
        ('B1-first_min_k+1-F2-first_k+1_cut', 'B1-F2'),
        ('B3-most_violated_k+1', 'B3'),
        ('C3-local_LS_QR_repair', 'C3'),
        ('C5-validated_auto_refit_retry', 'C5'),
        ('E2-big_M_20', 'E2'),
    )
    for prefix, label in labels:
        if experiment.startswith(prefix):
            return label
    return None


def _static_method_label(solver_name, experiment=None):
    """Return the stable method name written to compact 25-column tables."""
    if solver_name == 'milp':
        return 'exdbn'
    if solver_name in CLIQUE_FAMILY_SOLVERS:
        case_label = _static_clique_case_label(experiment)
        return f'clique-{case_label}' if case_label else 'clique'
    if solver_name == 'dagma':
        return 'dagma'
    if solver_name == 'edge_limit':
        return 'edge-limit'
    return str(solver_name)


def _static_runtime_prefix(solver_name, experiment=None):
    if solver_name == 'milp':
        return 'runtime_'
    if solver_name == 'dagma':
        return 'dagma_runtime_'
    if solver_name in CLIQUE_FAMILY_SOLVERS:
        case_label = _static_clique_case_label(experiment)
        if case_label:
            return f'clique_{case_label}_runtime_'
        return 'clique_runtime_'
    if solver_name == 'edge_limit':
        return 'limit_runtime_'
    return None


def _normalize_problem_ratio_overrides(cfg):
    problem_name = str(cfg.problem.name).strip().lower().replace('-', '_')
    if problem_name not in {'dynamic', 'er', 'sf', 'cliquefree_er', 'cliquefree_sf'}:
        return

    intra_edge_ratio = cfg.problem.get('intra_edge_ratio')
    inter_edge_ratio = cfg.problem.get('inter_edge_ratio')

    if intra_edge_ratio is None and inter_edge_ratio is not None:
        intra_edge_ratio = inter_edge_ratio
    if inter_edge_ratio is None and intra_edge_ratio is not None:
        inter_edge_ratio = intra_edge_ratio

    with open_dict(cfg.problem):
        if intra_edge_ratio is not None:
            cfg.problem.intra_edge_ratio = intra_edge_ratio
        if inter_edge_ratio is not None:
            cfg.problem.inter_edge_ratio = inter_edge_ratio


def _static_scenario_key(cfg):
    problem_name = str(cfg.problem.name).strip().lower().replace('_', '-')
    intra_edge_ratio = cfg.problem.get('intra_edge_ratio')
    if intra_edge_ratio is None:
        return None
    problem_p = _static_problem_p_value(cfg)
    return f'{problem_name}-{int(intra_edge_ratio)}-{problem_p}'


def _static_results_root(cfg):
    scenario_key = _static_scenario_key(cfg)
    if scenario_key is None:
        return None
    base_dir = Path(os.getenv('EXDBN_STATIC_CSV_BASE_DIR', DEFAULT_RESULTS_ROOT))
    return base_dir / scenario_key


def _static_solver_suffix(cfg):
    time_limit = int(float(cfg.solver.time_limit))
    max_clique_size = cfg.solver.get(
        'max_clique_size',
        cfg.problem.get('clique_limit', 'na'),
    )
    try:
        max_clique_size = int(float(max_clique_size))
    except (TypeError, ValueError):
        max_clique_size = str(max_clique_size)
    return f'{time_limit}s_{max_clique_size}clique'


def _ensure_static_runtime_columns(path, target_columns):
    if not path.exists():
        return
    with path.open(newline='') as handle:
        reader = csv.DictReader(handle)
        fieldnames = reader.fieldnames or []
        rows = list(reader)
    if fieldnames == target_columns:
        return
    legacy_aliases = {
        'dataset': 'experiment', 'degree': 'seed', 'features': 'number_of_variables',
        'samples': 'number_of_samples', 'runtime_seconds': 'runtime_s',
        'f1score': 'f1', 'cycle_lazy_cuts': 'cycle_cuts',
        'clique_lazy_cuts': 'clique_cuts', 'clique_user_cuts': 'user_cuts',
        'explored_nodes': 'nodes', 'mipsol_rejection_pct': 'rejection_pct',
        'root_fractional_x_bins': 'root_x_bins',
        'ori_graph_density': 'ori_skeleton_density',
        'after_cliquefree_density': 'after_cliquefree_skeleton_density',
        'cycle_lazy_count': 'cycle_lazy_cuts',
        'clique_lazy_count': 'clique_lazy_cuts',
        'clique_user_count': 'clique_user_cuts',
    }
    migrated_rows = []
    for old_row in rows:
        row = {column: old_row.get(column, '') for column in target_columns}
        for new_column, old_column in legacy_aliases.items():
            if new_column in target_columns and not row.get(new_column):
                row[new_column] = old_row.get(old_column, '')
        if 'lazy_count' in target_columns and not row.get('lazy_count'):
            try:
                row['lazy_count'] = str(sum(
                    float(row.get(column) or 0)
                    for column in (
                        'cycle_lazy_count',
                        'clique_lazy_count',
                        'clique_user_count',
                    )
                ))
            except (TypeError, ValueError):
                row['lazy_count'] = ''
        migrated_rows.append(row)
    with path.open('w', newline='') as handle:
        writer = csv.DictWriter(handle, fieldnames=target_columns)
        writer.writeheader()
        writer.writerows(migrated_rows)


def _next_static_repeat_index(path):
    if not path.exists():
        return 1
    with path.open(newline='') as handle:
        reader = csv.DictReader(handle)
        values = []
        for row in reader:
            try:
                values.append(int(float(row.get('degree', ''))))
            except (TypeError, ValueError):
                pass
    return max(values, default=0) + 1


def _static_degree_value(cfg, output_path):
    if cfg.solver.name == 'edge_limit':
        seed = cfg.problem.get('seed')
        if seed is not None:
            return int(seed)
        if 'max_in_degree' in cfg.solver:
            return int(cfg.solver.max_in_degree)
        if 'max_out_degree' in cfg.solver:
            return int(cfg.solver.max_out_degree)
    seed = cfg.problem.get('seed')
    if seed is not None:
        return int(seed)
    repeat_index = os.getenv('EXDBN_REPEAT_INDEX')
    if repeat_index:
        return int(repeat_index)
    return _next_static_repeat_index(output_path)


def _static_problem_p_value(cfg):
    problem_p = cfg.problem.get('p')
    if problem_p is None:
        return 0
    if isinstance(problem_p, (list, tuple)):
        problem_p = problem_p[0] if problem_p else 0
    problem_p_str = str(problem_p).strip()
    if not problem_p_str:
        return 0
    return int(float(problem_p_str.split(',')[0]))


def _edge_limit_degree_value(cfg):
    seed = cfg.problem.get('seed')
    if seed is not None:
        return int(seed)
    if 'max_in_degree' in cfg.solver:
        return int(cfg.solver.max_in_degree)
    if 'max_out_degree' in cfg.solver:
        return int(cfg.solver.max_out_degree)
    return None


def _read_ag_diagnostics(output_dir):
    paths = sorted(Path(output_dir).glob('*_summary_diagnostics.json'))
    if not paths:
        return {}
    try:
        with paths[0].open() as handle:
            return json.load(handle)
    except (OSError, json.JSONDecodeError):
        return {}


def _json_cell(value):
    return json.dumps(value, separators=(',', ':'), sort_keys=True)


def _read_progress_rows(output_dir):
    paths = sorted(Path(output_dir).glob('*_progress_diagnostics.csv'))
    if not paths:
        return []
    try:
        with paths[0].open(newline='') as handle:
            return list(csv.DictReader(handle))
    except OSError:
        return []


def _true_linear_r2(X, W_true):
    X = np.asarray(X)
    W_true = np.asarray(W_true)
    non_root_nodes = np.flatnonzero(np.any(W_true != 0, axis=0))
    scores = []
    for node in non_root_nodes:
        observed = X[:, node]
        predicted = X @ W_true[:, node]
        denominator = np.sum((observed - np.mean(observed)) ** 2)
        if denominator > 0:
            scores.append(1.0 - np.sum((observed - predicted) ** 2) / denominator)
    return float(np.mean(scores)) if scores else None


def _append_static_runtime_csv(cfg, runtime_seconds, gap, lazy_count, acc,
                               X, W_true, output_dir, lazy_breakdown=None):
    if _env_flag('EXDBN_PRE_CE6829A_LEGACY') or _env_flag('EXDBN_DISABLE_STATIC_RUNTIME_CSV'):
        return

    run_output_dir = Path(output_dir)
    prefix = _static_runtime_prefix(cfg.solver.name, cfg.get('experiment'))
    scenario_key = _static_scenario_key(cfg)
    if prefix is None or scenario_key is None:
        return

    samples = int(cfg.problem.number_of_samples)
    features = int(cfg.problem.number_of_variables)
    sem_type = str(cfg.problem.sem_type)
    dataset = f'static_{scenario_key}_{sem_type}_d{features}_n{samples}'
    results_root = _static_results_root(cfg)
    if results_root is None:
        return
    output_dir = results_root / f'static_n{samples}'
    output_dir.mkdir(parents=True, exist_ok=True)
    solver_suffix = _static_solver_suffix(cfg)
    output_path = output_dir / f'{prefix}{dataset}_{solver_suffix}.csv'

    diagnostics_enabled = bool(cfg.solver.get(
        'experiment_diagnostics',
        cfg.solver.get('optimization_diagnostics', False),
    ))
    output_columns = (
        STATIC_RUNTIME_COLUMNS
        if diagnostics_enabled
        else COMPACT_STATIC_RUNTIME_COLUMNS
    )
    _ensure_static_runtime_columns(output_path, output_columns)
    diagnostics = _read_ag_diagnostics(run_output_dir)
    final = diagnostics.get('final', {})
    derived = diagnostics.get('derived_metrics', {})
    callback_costs = diagnostics.get('callback_costs', {})
    violation_counts = diagnostics.get('violation_counts', {})
    cut_unique = diagnostics.get('cut_unique_counts', {})
    cut_duplicates = diagnostics.get('cut_duplicate_counts', {})
    root_records = diagnostics.get('root_records', [])
    root = root_records[0] if root_records else {}
    progress_rows = _read_progress_rows(run_output_dir)
    last_progress = progress_rows[-1] if progress_rows else {}
    separation_attempts = diagnostics.get('separation_attempt_counts', {})
    callbacks_with_cuts = diagnostics.get('callbacks_with_cuts', {})
    method_details = final.get('method_details', {})
    checkpoints = method_details.get('checkpoints', []) if isinstance(method_details, dict) else []
    checkpoint_rows = checkpoints or progress_rows
    best_snapshot = final.get('best_accepted_snapshot') or {}
    cycle_cuts = (lazy_breakdown or {}).get('cycle_lazy_count')
    clique_cuts = (lazy_breakdown or {}).get('clique_lazy_count')
    user_cuts = (lazy_breakdown or {}).get('clique_user_count', 0)
    callback_s = derived.get('callback_time')
    callback_pct = (100.0 * callback_s / runtime_seconds
                    if callback_s is not None and runtime_seconds else None)
    weights = np.abs(np.asarray(W_true if W_true is not None else []))
    true_edges = int(np.count_nonzero(weights))
    d = int(cfg.problem.number_of_variables)
    experiment = str(cfg.experiment)
    method_match = re.match(r'^METHOD_([A-G])', experiment)
    row = {
        'method': _static_method_label(cfg.solver.name, cfg.get('experiment')),
        'dataset': dataset,
        'features': features,
        'samples': samples,
        'p': _static_problem_p_value(cfg),
        'status': 'FINISHED',
        'method_family': method_match.group(1) if method_match else '',
        'method_variant': cfg.solver.get(
            'experiment_variant', cfg.solver.get('method_variant', '')),
        'experiment': experiment,
        'edge_ratio': cfg.problem.get('intra_edge_ratio', cfg.problem.get('edge_ratio')),
        'seed': cfg.problem.get('seed'),
        'degree': cfg.problem.get('seed'),
        'true_edges': true_edges,
        'ori_graph_density': (
            2.0 * float(cfg.problem.get('intra_edge_ratio', cfg.problem.get('edge_ratio'))) / (d - 1)
            if d > 1 and cfg.problem.get('intra_edge_ratio', cfg.problem.get('edge_ratio')) is not None
            else None
        ),
        'after_cliquefree_density': (
            2.0 * true_edges / (d * (d - 1)) if d > 1 else None
        ),
        'true_mean_abs_w': float(weights[weights != 0].mean()) if true_edges else 0.0,
        'true_linear_r2': _true_linear_r2(X, W_true),
        'big_m': cfg.solver.get('weights_bound'),
        'time_limit': cfg.solver.get('time_limit'),
        'runtime_seconds': runtime_seconds,
        'best_incumbent': final.get('objective'),
        'best_bound': final.get('best_bound'),
        'gap': gap,
        'explored_nodes': final.get('node_count'),
        'nodes_per_s': final.get('nodes_per_second'),
        'lp_iter_per_node': derived.get('lp_iterations_per_node'),
        'lp_iter_per_s': derived.get('lp_iterations_per_second'),
        'root_bound': root.get('root_bound'),
        'bound_gain': derived.get('bound_gain'),
        'bound_gain_per_1k_nodes': derived.get('bound_gain_per_1000_nodes'),
        'root_fractional_edges': root.get('fractional_edge_count'),
        'root_fractional_x_bins': (
            '|'.join(str(int(root.get(key, 0) or 0)) for key in (
                'x_le_001_count', 'x_001_01_count', 'x_01_05_count',
                'x_05_099_count', 'x_ge_099_count',
            )) if root else None
        ),
        'root_small_x_large_w': root.get('small_x_large_w_001_01'),
        'root_mean_big_m_ratio': root.get('mean_big_m_ratio'),
        'root_violated_cliques': root.get('violated_clique_count'),
        'root_max_clique_violation': root.get(
            'max_fractional_clique_violation'),
        'callback_s': callback_s,
        'callback_pct': callback_pct,
        'search_s': runtime_seconds - callback_s if callback_s is not None else None,
        'mipsol_total': diagnostics.get('mipsol_count'),
        'mipsol_rejected': diagnostics.get('actual_mipsol_rejected_count'),
        'mipsol_accepted': diagnostics.get('actual_mipsol_accepted_count'),
        'mipnode_total': final.get('mipnode_total'),
        'lp_iterations': final.get('simplex_iteration_count', final.get('lp_iterations')),
        'mipsol_rejection_pct': (100.0 * derived['mipsol_rejection_rate']
                          if derived.get('mipsol_rejection_rate') is not None else None),
        'violation_overlap_pct': (100.0 * derived['violation_overlap_rate']
                                  if derived.get('violation_overlap_rate') is not None else None),
        'cycle_only_candidates': violation_counts.get('cycle_only'),
        'clique_only_candidates': violation_counts.get('clique_only'),
        'both_candidates': violation_counts.get('both'),
        'cycle_lazy_cuts': cycle_cuts,
        'clique_lazy_cuts': clique_cuts,
        'clique_user_cuts': user_cuts,
        'lazy_count': lazy_count,
        'cycle_lazy_count': cycle_cuts,
        'clique_lazy_count': clique_cuts,
        'clique_user_count': user_cuts,
        'unique_cuts': sum(cut_unique.get(kind, 0) for kind in ('cycle', 'clique')),
        'duplicate_cuts': sum(cut_duplicates.get(kind, 0) for kind in ('cycle', 'clique')),
        'cycle_unique_cuts': cut_unique.get('cycle'),
        'clique_unique_cuts': cut_unique.get('clique'),
        'cycle_duplicate_cuts': cut_duplicates.get('cycle'),
        'clique_duplicate_cuts': cut_duplicates.get('clique'),
        'cut_hit_pct': (100.0 * derived['cut_hit_rate']
                        if derived.get('cut_hit_rate') is not None else None),
        'dual_gain_per_cut': derived.get('dual_gain_per_cut'),
        'dual_gain_per_s': derived.get('dual_gain_per_second'),
        'cycle_callback_s': sum(callback_costs.get(key, 0) for key in
                                ('cycle_detection_time', 'cycle_submission_time')),
        'clique_callback_s': sum(callback_costs.get(key, 0) for key in
                                 ('clique_detection_time', 'clique_submission_time')),
        'open_nodes': (
            final.get('open_nodes')
            if final.get('open_nodes') is not None
            else last_progress.get('open_nodes')
        ),
        'solution_count': final.get('solution_count'),
        'shd': acc.get('shd'),
        'nnz': acc.get('nnz'),
        'f1score': acc.get('f1score'),
        'g_score': acc.get('g_score'),
        'fdr': acc.get('fdr'),
        'tpr': acc.get('tpr'),
        'fpr': acc.get('fpr'),
        'precision': acc.get('precision'),
        'cycle_detection_s': callback_costs.get('cycle_detection_time'),
        'cycle_submission_s': callback_costs.get('cycle_submission_time'),
        'clique_detection_s': callback_costs.get('clique_detection_time'),
        'clique_submission_s': callback_costs.get('clique_submission_time'),
        'cycle_separation_attempts': separation_attempts.get('cycle'),
        'clique_separation_attempts': separation_attempts.get('clique'),
        'cycle_callback_count': separation_attempts.get('cycle'),
        'clique_callback_count': separation_attempts.get('clique'),
        'mip_progress_times': _json_cell([r.get('runtime') for r in progress_rows]),
        'checkpoint_explored_nodes': _json_cell([r.get('explored_nodes') for r in checkpoint_rows]),
        'checkpoint_open_nodes': _json_cell([r.get('open_nodes') for r in checkpoint_rows]),
        'checkpoint_best_bound': _json_cell([r.get('best_bound') for r in checkpoint_rows]),
        'checkpoint_incumbent': _json_cell([r.get('best_incumbent') for r in checkpoint_rows]),
        'checkpoint_gap': _json_cell([r.get('gap') for r in checkpoint_rows]),
        'checkpoint_status': _json_cell([r.get('status') for r in checkpoints]),
        'checkpoint_solution_count': _json_cell([r.get('solution_count') for r in checkpoint_rows]),
        'checkpoint_DAG': _json_cell([r.get('best_accepted_dag') for r in checkpoints]),
        'checkpoint_SHD': _json_cell([r.get('best_accepted_shd') for r in checkpoints]),
        'checkpoint_F1': _json_cell([r.get('best_accepted_f1') for r in checkpoints]),
        'checkpoint_NNZ': _json_cell([r.get('best_accepted_nnz') for r in checkpoints]),
        'best_incumbent_edges': _json_cell(best_snapshot.get('edges')),
        'best_incumbent_weights': _json_cell(best_snapshot.get('weights')),
        'W_true_path': str(run_output_dir / 'W_true.csv'),
        'run_dir': str(run_output_dir),
    }
    write_header = not output_path.exists()
    with output_path.open('a', newline='') as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=output_columns,
            extrasaction='ignore',
        )
        if write_header:
            writer.writeheader()
        writer.writerow(row)


@hydra.main(version_base=None,  config_path="./experiments_conf", config_name="config")
@log_exceptions
def start_experiment(cfg: DictConfig) -> None:
    hydra_config = hydra.core.hydra_config.HydraConfig.get()
    if 'num' in hydra_config.job and 'skip_first' in cfg and hydra_config.job.num < cfg.skip_first:
        return
    _normalize_problem_ratio_overrides(cfg)
    _start_batch_summary_refresher()
    tu.set_tracking(cfg.tracking, cfg.experiment) #mlflow.set_experiment(experiment_name=cfg.experiment)
    conf_yaml = OmegaConf.to_yaml(cfg)
    print(conf_yaml)
    app_config = OmegaConf.to_container(cfg)
    try:
        seed = int(cfg.problem.seed)
        number_of_variables = int(cfg.problem.number_of_variables)
        number_of_samples = int(cfg.problem.number_of_samples)
        intra_edge_ratio = float(cfg.problem.intra_edge_ratio)
    except (TypeError, ValueError) as exc:
        raise ValueError(
            'Invalid problem configuration: seed, number_of_variables, '
            'number_of_samples, and intra_edge_ratio must be numeric; '
            f'got seed={cfg.problem.seed!r}, '
            f'number_of_variables={cfg.problem.number_of_variables!r}, '
            f'number_of_samples={cfg.problem.number_of_samples!r}, '
            f'intra_edge_ratio={cfg.problem.intra_edge_ratio!r}'
        ) from exc
    if number_of_variables <= 0 or number_of_samples <= 0 or intra_edge_ratio <= 0:
        raise ValueError(
            'Invalid problem configuration: number_of_variables, '
            'number_of_samples, and intra_edge_ratio must be positive; '
            f'got number_of_variables={number_of_variables}, '
            f'number_of_samples={number_of_samples}, '
            f'intra_edge_ratio={intra_edge_ratio}'
        )

    utils.set_random_seed(seed)
    with (tu.start_run() as run):
        #log_params_from_omegaconf_dict(cfg)
        log_params_from_omegaconf_dict(cfg, {'solver', 'problem'})
        log_system_info(HydraConfig.get())
        note = cfg.get('note','')
        run.log_param('note', note)
        output_dir = hydra.core.hydra_config.HydraConfig.get().runtime.output_dir
        run.log_text(output_dir, 'work_dir.txt')
        logger.info(f'Starting experiment in {output_dir}')
        with open(join(output_dir, 'config.yaml'), 'w') as f:
            f.write(conf_yaml)
        run.log_artifact(join(output_dir, 'config.yaml'))

        try:
            W_true, W_bi_true, B_true, B_bi_true, W_lags_true, B_lags_true, X, Y, tabu_edges, intra_nodes, inter_nodes = load_problem(cfg, run)
            if X.shape[0] > 1:
                varsort = varsortability(X, B_true)
            else:
                varsort = 0
            print(f'VARSORT: {varsort}')
            run.log_metric('varsortability', varsort)
            variances = np.var(X, axis=0)
            means = np.mean(X, axis=0)
            logger.info(f'DATA MEANS: {means}')
            logger.info(f'DATA VARIANCES: {variances}')
            if cfg.problem.normalize:
                #run.log_param('normalize', cfg.problem.normalize)
                X, Y = normalize_data(X,Y)
                print(f'varsort: {varsortability(X, B_true)}')
                # variances = np.var(X, axis=0)
                # means = np.mean(X, axis=0)
                logger.info(f'DATA NORMALIZED:')
                # print(means)
                # print(variances)
        except ExDagDataException as e:
            logging.critical(e, exc_info=True)
            return

        n, d = X.shape
        p = len(W_lags_true) if W_lags_true is not None else 0
        B_true = B_true.astype(int)
        if B_bi_true is not None:
            B_bi_true = B_bi_true.astype(int)

        np.savetxt(join(output_dir,'W_true.csv'), W_true, delimiter=',')
        run.log_artifact(join(output_dir,'W_true.csv'))
        for i, A_i_true in enumerate(W_lags_true):
            np.savetxt(join(output_dir,f'A{i}_true.csv'), A_i_true, delimiter=',')
            run.log_artifact(join(output_dir,f'A{i}_true.csv'))
        if W_bi_true is not None:
            np.savetxt(join(output_dir,'W_bi_true.csv'), W_bi_true, delimiter=',')
            run.log_artifact(join(output_dir,'W_bi_true.csv'))

        np.savetxt(join(output_dir,'X.csv'), X, delimiter=',')
        run.log_artifact(join(output_dir,'X.csv'))

        for i, Y_i in enumerate(Y):
            np.savetxt(join(output_dir,f'Y{i+1}.csv'), Y_i, delimiter=',')
            run.log_artifact(join(output_dir,f'Y{i+1}.csv'))

        run.log_metric('n', n)
        run.log_metric('d', d)
        run.log_metric('p', p)
        #run.log_param('algo', cfg.solver.name)

        #run.log_param('seed', seed)

        logger.info(f'DATA GENERATED')

        # if lambda1 is not None:
        #     run.log_param('lambda1', lambda1)
        # if lambda2 is not None:
        #     run.log_param('lambda2', lambda2)
        # run.log_param('loss_type', loss_type)

        logger.info(f'STARTING SOLVER')
        if bool(cfg.solver.get('experiment_diagnostics',
                               cfg.solver.get('optimization_diagnostics', False))):
            # Attach resolved, JSON-serializable run metadata to the solver
            # config without changing the solver formulation.
            with open_dict(cfg.solver):
                cfg.solver.experiment_metadata = {
                    'solver': str(cfg.solver.name),
                    'problem': str(cfg.problem.name),
                    'seed': int(cfg.problem.seed),
                    'number_of_variables': int(d),
                    'number_of_samples': int(n),
                    'p': int(p),
                    'sem_type': str(cfg.problem.get('sem_type', 'unknown')),
                    'generator': str(cfg.problem.get('generator', 'unknown')),
                    'graph_type': str(cfg.problem.get(
                        'graph_type', cfg.problem.get('graph_type_inter', 'unknown'))),
                    'normalize': bool(cfg.problem.get('normalize', False)),
                    'intra_edge_ratio': cfg.problem.get('intra_edge_ratio'),
                    'inter_edge_ratio': cfg.problem.get('inter_edge_ratio'),
                    'time_limit': float(cfg.solver.time_limit),
                    'target_mip_gap': float(cfg.solver.target_mip_gap),
                    'weights_bound': float(cfg.solver.weights_bound),
                    'lambda1': float(cfg.solver.get('lambda1', 0.0)),
                    'lambda2': float(cfg.solver.get('lambda2', 0.0)),
                    'loss_type': str(cfg.solver.get('loss_type', '')),
                    'constraints_mode': str(cfg.solver.get('constraints_mode', '')),
                    'nonzero_threshold': float(
                        cfg.solver.get('nonzero_threshold', 0.0)),
                    'max_clique_size': int(cfg.solver.get('max_clique_size', 0)),
                    'callback_mode': str(cfg.solver.get('callback_mode', '')),
                    'clique_callback_mode': str(
                        cfg.solver.get('clique_callback_mode', '')),
                    'enable_cycle_constraints': bool(
                        cfg.solver.get('enable_cycle_constraints', True)),
                    'enable_clique_constraints': bool(
                        cfg.solver.get('enable_clique_constraints', True)),
                    'separation_order': str(
                        cfg.solver.get('separation_order', 'cycle_first')),
                    'delayed_second_separation': bool(
                        cfg.solver.get('delayed_second_separation', False)),
                    'cycle_top_k': int(cfg.solver.get('cycle_top_k', 0)),
                    'clique_top_k': int(cfg.solver.get('clique_top_k', 0)),
                    'max_cycle_cuts_per_callback': int(
                        cfg.solver.get('max_cycle_cuts_per_callback', 0)),
                    'max_clique_cuts_per_callback': int(
                        cfg.solver.get('max_clique_cuts_per_callback', 0)),
                    'deduplicate_cycle_cuts': bool(
                        cfg.solver.get('deduplicate_cycle_cuts', False)),
                    'deduplicate_clique_cuts': bool(
                        cfg.solver.get('deduplicate_clique_cuts', False)),
                    'enable_fractional_clique_cuts': bool(
                        cfg.solver.get('enable_fractional_clique_cuts', False)),
                    'fractional_root_only': bool(
                        cfg.solver.get('fractional_root_only', True)),
                    'gurobi_seed': int(cfg.solver.get('gurobi_seed', 0)),
                    'gurobi_threads': int(cfg.solver.get('gurobi_threads', 0)),
                    'greedy_node_frequency': int(
                        cfg.solver.get('greedy_node_frequency', 0)),
                    'greedy_max_cuts_per_node': int(
                        cfg.solver.get('greedy_max_cuts_per_node', 0)),
                }
        start_time = time.time()
        W_est = None
        W_bi_est = None
        B_est, B_bi_est = None, None
        gap = None
        lazy_count = None
        solver_runtime = None
        solver_iterations = None
        solver_outer_iterations = None
        solver_hit_time_limit = None
        lazy_breakdown = None
        clique_family_solvers = CLIQUE_FAMILY_SOLVERS
        if cfg.solver.name in {'milp', 'edge_limit'} | clique_family_solvers:
            solve_fn = solve_milp.solve
            solve_kwargs = {
                "X": X,
                "cfg": cfg.solver,
                "w_threshold": cfg.solver.nonzero_threshold,
                "Y": Y,
                "B_ref": B_true,
                "tabu_edges": tabu_edges if cfg.solver.tabu_edges else None,
            }
            if cfg.solver.name == 'edge_limit':
                solve_fn = solve_milp_edge_limit.solve
                degree_value = _edge_limit_degree_value(cfg)
                if degree_value is not None:
                    solve_kwargs["max_in_degree"] = degree_value
                    solve_kwargs["max_out_degree"] = degree_value
            elif cfg.solver.name == 'milp_clique':
                solve_fn = solve_milp_clique.solve
                with open_dict(cfg.solver):
                    cfg.solver.diagnostics_output_dir = output_dir
            elif cfg.solver.name == 'milp_cliquewidth':
                solve_fn = solve_milp_cliquewidth.solve

            solve_result = solve_fn(**solve_kwargs)
            if cfg.solver.name in clique_family_solvers:
                W_est, A_est, gap, lazy_count, stats, lazy_breakdown = solve_result
            else:
                W_est, A_est, gap, lazy_count, stats = solve_result
            if W_est is None:
                run.log_text(f'Error: Gurobi has not found a solution', 'error.txt')
                run.log_metric('infeasible', True)
                if lazy_breakdown:
                    run.log_metric('cycle_lazy_added', lazy_breakdown.get('cycle_lazy_count', 0))
                    run.log_metric('clique_lazy_added', lazy_breakdown.get('clique_lazy_count', 0))
                return
            B_est = (W_est != 0).astype(int)
            if stats:
                table_data = {}
                table_data['Time'] = [s[0] for s in stats]
                table_data['Def_thresh_SHD'] = [s[1] for s in stats]
                table_data['Best_SHD'] = [s[2] for s in stats]
                table_data['Best_threshold'] = [s[3] for s in stats]
                table_data['Objective_val'] = [s[4] for s in stats]
                table_data['Dag_t'] = [s[5] for s in stats]
                run.log_table(table_data, 'solving_progress.json')
            run.log_metric('mipgap', gap)
            run.log_metric('lazy_added', lazy_count)
            if lazy_breakdown:
                run.log_metric('cycle_lazy_added', lazy_breakdown.get('cycle_lazy_count', 0))
                run.log_metric('clique_lazy_added', lazy_breakdown.get('clique_lazy_count', 0))
                run.log_metric('clique_user_added', lazy_breakdown.get('clique_user_count', 0))
        elif cfg.solver.name == "exmag":
            callback_mode = cfg.solver.callback_mode
            robust = cfg.solver.robust
            weights_bound = cfg.solver.weights_bound
            reg_type = cfg.solver.reg_type
            run.log_param('reg_type', reg_type)
            a_reg_type = cfg.solver.a_reg_type
            run.log_param('a_reg_type', a_reg_type)
            target_mip_gap = cfg.solver.target_mip_gap
            run.log_param('target_mip_gap', target_mip_gap)
            run.log_param('robust', robust)
            run.log_param('callback_mode', callback_mode)
            run.log_param('weights_bound', weights_bound)

            exmag_version = cfg.solver.get('exmag_version', 'version0')

            if exmag_version == 'version0':
                W_est, W_bi_est, gap, lazy_count, stats = solve_exmag.solve(X, cfg.solver.lambda1, cfg.solver.loss_type, reg_type,
                                                                       cfg.solver.nonzero_threshold, tabu_edges=tabu_edges if cfg.solver.tabu_edges else {},
                                                                       B_ref=B_true, mode=callback_mode,
                                                                       time_limit=cfg.solver.time_limit,
                                                                       robust=robust, weights_bound=weights_bound)
            elif exmag_version == 'version2':
                from dagsolvers import solve_exmag_2
                W_est, W_bi_est, gap, lazy_count, stats = solve_exmag_2.solve(X, cfg.solver.lambda1, cfg.solver.loss_type,
                                                                            reg_type,
                                                                            cfg.solver.nonzero_threshold,
                                                                            tabu_edges=tabu_edges if cfg.solver.tabu_edges else {},
                                                                            B_ref=B_true, mode=callback_mode,
                                                                            time_limit=cfg.solver.time_limit,
                                                                            robust=robust, weights_bound=weights_bound)

            B_est = (W_est != 0).astype(int)
            B_bi_est = (W_bi_est != 0).astype(int)
            A_est = []
            # (X, lambda1, loss_type, reg_type, w_threshold, tabu_edges={}, B_ref=None, mode='shortest_cycle',
            #           time_limit=300, robust=False, weights_bound=100.0, constraints_mode='weights')
            if W_est is None:
                run.log_text(f'Error: Gurobi has not found a solution', 'error.txt')
                run.log_metric('infeasible', True)
                return
            if stats:
                table_data = {}
                table_data['Time'] = [s[0] for s in stats]
                table_data['Def_thresh_SHD'] = [s[1] for s in stats]
                table_data['Best_SHD'] = [s[2] for s in stats]
                table_data['Best_threshold'] = [s[3] for s in stats]
                table_data['Objective_val'] = [s[4] for s in stats]
                table_data['Dag_t'] = [s[5] for s in stats]
                run.log_table(table_data, 'solving_progress.json')
            run.log_metric('mipgap', gap)
            run.log_metric('lazy_added', lazy_count)
        elif cfg.solver.name == 'gobnilp':
            palim = cfg.solver.get('palim')
            run.log_param('palim', palim)
            print('palim')
            print(palim)
            W_est = solve_gobnilp.solve(X, cfg.solver)
            A_est = []
        elif cfg.solver.name == 'ip4ancadmg':
            from dagsolvers.solvers.IP4AncADMG.solver_ip4ancadmg import solve_ip4ancadmg
            B_est, B_bi_est = solve_ip4ancadmg(X, cfg.solver)
            W_est = B_est
            W_bi_est = B_bi_est
            A_est = []
        elif cfg.solver.name == 'ipbm':
            B_est, B_bi_est = solve_ipbm(X, cfg.solver)
            W_est = B_est
            W_bi_est = B_bi_est
            A_est = []
        elif cfg.solver.name == 'micodag':
            # pip install micodag
            import dagsolvers.solvers.micpnid as mic
            moral = [(i+1,j+1) for i in range(d) for j in range(d) if i!=j]
            RGAP, W_est, _, obj, _ = mic.optimize(X, moral, cfg.solver.lambda1, timelimit = cfg.solver.time_limit / d)
            run.log_metric('objective_value', obj)
            run.log_metric('mipgap', RGAP)
            A_est = []
        elif cfg.solver.name == 'notears':
            W_est = linear.notears_linear(X, cfg.solver.lambda1, cfg.solver.loss_type, w_threshold=cfg.solver.nonzero_threshold) # Does not work well with 0.
            B_est = (W_est != 0).astype(int)
            A_est = []
        elif cfg.solver.name == 'sortnregress':
            W_est = sortnregress(X)
            A_est = []
        elif cfg.solver.name == 'dagma':
            from solve_dagma import solve_dagma
            W_est, solver_runtime, solver_iterations, solver_outer_iterations, solver_hit_time_limit = solve_dagma(X, cfg.solver)
            A_est = []
        elif cfg.solver.name == 'fci':
            B_est, B_bi_est = solve_fci(X)
            W_est = None
            W_bi_est = None
            A_est = []
        elif cfg.solver.name == 'boss':
            from solve_boss import solve_boss
            W_est = solve_boss(X, output_dir, cfg.solver.cmd)
            A_est = []
        elif cfg.solver.name == 'lingam':
            from solve_lingam import solve_lingam
            W_est, A_est = solve_lingam(X, Y, p)
        elif cfg.solver.name == 'nts_notears':
            from solve_nts_notears import solve_nts_notears
            W_est, A_est = solve_nts_notears(X, Y, p, cfg.solver)
        elif cfg.solver.name == 'dynotears':
            X_lag = np.concatenate(Y, axis=1)
            _, W_est, A_est_concated = from_numpy_dynamic(X,X_lag, w_threshold=cfg.solver.nonzero_threshold, lambda_w=cfg.solver.lambda1, lambda_a=cfg.solver.lambda2)
            A_est = []
            for lag in range(p): # range(1, p + 1):
                #idxs = [f'_lag{lag}' in c for c in inter_nodes]
                idxs = list(range(d*lag, d*(lag+1)))
                A_est_lag = A_est_concated[idxs,:]
                A_est.append(A_est_lag)
            #print(A_est)
        else:
            assert False
        solving_duration = time.time() - start_time
        logger.info(f'SOLVER FINISHED')
        if W_est is not None and not utils.is_dag(W_est):
            run.log_text('Error: Graph found is not DAG', 'error.txt')
            run.log_metric('infeasible', True)
            return
        run.log_metric('runtime', solving_duration)
        if solver_runtime is not None:
            run.log_metric('solver_runtime', solver_runtime)
            if cfg.solver.name == 'dagma':
                run.log_metric('dagma_fit_runtime', solver_runtime)
        if solver_iterations is not None:
            run.log_metric('solver_iterations', solver_iterations)
            if cfg.solver.name == 'dagma':
                run.log_metric('dagma_iterations', solver_iterations)
        if solver_outer_iterations is not None and cfg.solver.name == 'dagma':
            run.log_metric('dagma_outer_iterations', solver_outer_iterations)
        if solver_hit_time_limit is not None and cfg.solver.name == 'dagma':
            run.log_metric('dagma_hit_time_limit', int(bool(solver_hit_time_limit)))
        #assert utils.is_dag(W_est)
        if W_est is not None:
            np.savetxt(join(output_dir,'W_est.csv'), W_est, delimiter=',')
            run.log_artifact(join(output_dir,'W_est.csv'))

        with open(join(output_dir,'intra_nodes.txt'), "w") as f:
            s = "[" + ",".join(f'"{n}"' for n in intra_nodes) + "]"
            f.write(s)
        run.log_artifact(join(output_dir,'intra_nodes.txt'))
        with open(join(output_dir,'inter_nodes.txt'), "w") as f:
            s = "[" + ",".join(f'"{n}"' for n in inter_nodes) + "]"
            f.write(s)
        run.log_artifact(join(output_dir,'inter_nodes.txt'))

        if W_bi_est is not None:
            np.savetxt(join(output_dir,'W_bi_est.csv'), W_bi_est, delimiter=',')
            run.log_artifact(join(output_dir,'W_bi_est.csv'))
        for i, A_est_i in enumerate(A_est):
            np.savetxt(join(output_dir,f'A_est_{i}_no_t.csv'), W_est, delimiter=',')
            run.log_artifact(join(output_dir,f'A_est_{i}_no_t.csv'))


        # B and B_bi
        # B[i,j] = 1 :::: i --> j :::: direct cause
        # B[i,j] = 2 ::::  i o-> j :::: direct cause or common confounder
        # B_bi[i,j] = 1 :::: i <-> j :::: common confounder
        # B_bi[i,j] = 2 :::: i --- j :::: selection bias - common effect
        # B_bi[i,j] = 3 :::: i o-o j :::: direct cause either direction or common confounder or common effect

        if W_est is None:
            assert B_est is not None
            calculate_metrics_pag(B_true, B_bi_true, B_est, B_bi_est, run, cfg)

        else:
            if B_est is not None:
                assert not (B_est == 2).any() or (B_bi_est == 3).any() or (B_bi_est == 2).any(), 'PAG with weights - Not correctly implemented yet'
            best_W, best_Wbi, best_A = calculate_metrics(X, Y, W_true, B_true, W_lags_true, B_lags_true, W_est, A_est, W_bi_true, B_bi_true, W_bi_est, run, cfg)
            if cfg.solver.name in {'milp', 'edge_limit', 'dagma'} | CLIQUE_FAMILY_SOLVERS and _static_scenario_key(cfg) is not None:
                best_acc = count_accuracy(
                    B_true,
                    (best_W != 0).astype(int),
                    B_lags_true,
                    [(a != 0).astype(int) for a in best_A],
                )
                _append_static_runtime_csv(
                    cfg, solving_duration, gap, lazy_count, best_acc,
                    X, W_true, output_dir, lazy_breakdown)

            if cfg.plot:
                make_plots(run, W_true, W_est, best_W, W_bi_true, W_bi_est, best_Wbi, intra_nodes, W_lags_true, A_est, best_A, inter_nodes, output_dir, cfg.plot_dpi)
        _refresh_batch_summary()

if __name__ == "__main__":
    start_experiment()
