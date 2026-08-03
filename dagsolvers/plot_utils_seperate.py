import os
import re
from os.path import join

import pandas as pd
import seaborn as sns
from matplotlib import pyplot as plt

try:
    from data_load_utils import print_solver_params, get_solver_columns_names
except ModuleNotFoundError:
    # Fallback for local plotting when optional experiment-tracking deps are absent.
    def get_solver_columns_names(df):
        return [c for c in df.columns.tolist() if c.startswith('params.solver')]

    def print_solver_params(df, solver_columns):
        cols = [c for c in solver_columns if c in df.columns]
        if not cols:
            return
        print(df[cols].drop_duplicates().to_string())


# ============================================================
# 自动补充 num_vars
# ============================================================
def add_num_vars_column(df, filename=None):
    """
    num_vars 来源优先级：
    1. 已存在 num_vars
    2. features
    3. params.problem.number_of_variables
    4. 从文件名中解析 _dXX_
    """
    if 'num_vars' in df.columns:
        return df

    if 'features' in df.columns:
        df['num_vars'] = df['features']
        return df

    if 'params.problem.number_of_variables' in df.columns:
        df['num_vars'] = df['params.problem.number_of_variables']
        return df

    if filename is not None:
        m = re.search(r'_d(\d+)_', filename)
        if m:
            df['num_vars'] = int(m.group(1))
            return df

    df['num_vars'] = None
    return df


# ============================================================
# 批量读取 exdbn_test 下所有 CSV
# ============================================================
def load_all_exdbn_test_csvs(base_dir='results/exdbn/exdbn_run'):
    all_csvs = []

    for root, _, files in os.walk(base_dir):
        for file in files:
            if not file.endswith('.csv'):
                continue

            path = os.path.join(root, file)
            df = pd.read_csv(path)

            df = add_num_vars_column(df, filename=file)
            df['__source_file__'] = file  # 调试用

            all_csvs.append(df)

    if not all_csvs:
        return pd.DataFrame()

    return pd.concat(all_csvs, ignore_index=True)


def _env_bool(name, default=False):
    """Parse boolean environment variable."""
    v = os.getenv(name)
    if v is None:
        return default
    return str(v).strip().lower() in {'1', 'true', 'yes', 'y', 'on'}


def _env_number_list(name, number_type=int):
    """Parse an optional comma-separated numeric environment variable."""
    raw = os.getenv(name, '').strip()
    if not raw:
        return None
    try:
        values = [number_type(item.strip()) for item in raw.split(',') if item.strip()]
    except ValueError as exc:
        raise ValueError(f'Invalid {name}={raw!r}: expected comma-separated numbers') from exc
    return values or None


def _env_method_keys():
    """Read comma-separated plotting methods, preserving the legacy defaults."""
    raw = os.getenv('EXDBN_METHOD_KEYS', '').strip()
    if not raw:
        return ['milp', 'clique', 'edge_limit']
    return [item.strip() for item in raw.split(',') if item.strip()]


def _method_runtime_prefix(method):
    """Map a public method key to the runtime CSV filename prefix."""
    normalized = str(method).strip().lower()
    if normalized in {'milp', 'exdbn'}:
        return 'runtime_'
    if normalized in {'edge_limit', 'edge-limit', 'limit'}:
        return 'limit_runtime_'
    return f'{str(method).strip()}_runtime_'


def _method_summary_filename(method, scenario_key):
    """Keep legacy table names while giving every clique variant its own table."""
    normalized = str(method).strip().lower()
    if normalized in {'milp', 'exdbn'}:
        return f'{scenario_key}.csv'
    if normalized in {'edge_limit', 'edge-limit', 'limit'}:
        return f'limit_{scenario_key}.csv'
    return f'{str(method).strip()}_{scenario_key}.csv'


def _timelimit_from_filename(path):
    """Read the configured time limit from a runtime filename such as *_1800s_*.csv."""
    match = re.search(r'_(\d+(?:\.\d+)?)s(?:_|\.)', os.path.basename(path))
    return float(match.group(1)) if match else None


def _normalize_legend_style(legend_style=None, default='standard'):
    """
    Canonical legend styles:
      - half_running_time
      - single_data
      - standard
    """
    raw = legend_style if legend_style is not None else os.getenv('EXDBN_LEGEND_STYLE', default)
    raw = str(raw).strip().lower().replace('-', '_').replace(' ', '_')
    aliases = {
        'half': 'half_running_time',
        'half_running': 'half_running_time',
        'half_running_time': 'half_running_time',
        'running_time': 'half_running_time',
        'single': 'single_data',
        'single_data': 'single_data',
        'single_dataset': 'single_data',
        'standard': 'standard',
        'default': 'standard',
    }
    return aliases.get(raw, raw if raw in {'half_running_time', 'single_data', 'standard'} else default)


# def _legend_method_labels(legend_style: str) -> dict[str, str]:
#     if legend_style == 'half_running_time':
#         return {
#             'exdbn': 'EXDBN',
#             'limit': 'Edge-limit MILP',
#             'clique': 'Clique-width MILP',
#         }
#     return {
#         'exdbn': 'EXDBN',
#         'limit': 'Edge-limit MILP',
#         'clique': 'Clique-width MILP',
#     }

def _legend_method_labels(legend_style: str) -> dict[str, str]:
    return {
        'milp': 'ExDBN',
        'exdbn': 'ExDBN',
        'limit': 'Edge-limit MILP',
        'clique': 'Clique',
        'clique_B1-F2': 'Clique · First k+1',
        'clique_B3': 'Clique · Most-Violated',
        'clique_C3': 'Clique · QR Repair',
        'clique_C5': 'Clique · Auto-Repair',
        'clique_E2': 'Clique · M=20',
    }

def _legend_layout_config(num_labels, legend_style=None, position_override=None, single_scenario_mode=False):
    """
    Configure legend placement.
    """
    if legend_style is None:
        if position_override is not None:
            position = str(position_override).strip().lower()
            if position in {'bottom', 'lower'}:
                legend_style = 'single_data'
            elif position in {'half_running_time', 'half', 'running_time'}:
                legend_style = 'half_running_time'
            else:
                legend_style = 'standard'
        else:
            legend_style = 'single_data' if single_scenario_mode else 'standard'
    legend_style = _normalize_legend_style(legend_style, default='standard')

    if legend_style == 'half_running_time':
        return {
            'kind': 'boxed',
            'loc': 'upper left',
            'bbox_to_anchor': (0.88, 0.98),
            'tight_rect': (0.05, 0.05, 0.86, 0.95),
            'legend_fontsize': 7,
            'xlabel_y': 0.02,
            'ncol': 1,
        }
    if legend_style == 'single_data':
        return {
            'kind': 'figure',
            'loc': 'lower center',
            'bbox_to_anchor': (0.5, 0.07),
            'tight_rect': (0.05, 0.16, 0.98, 0.95),
            'legend_fontsize': 7,
            'xlabel_y': 0.005,
            'ncol': max(1, num_labels),
        }
    return {
        'kind': 'figure',
        'loc': 'upper left',
        'bbox_to_anchor': (0.79, 0.90),
        'tight_rect': (0.05, 0.10, 0.82, 0.95),
        'legend_fontsize': 11,
        'xlabel_y': 0.005,
        'ncol': 1,
    }


def _aggregate_metric_value(df_stats, col):
    if col not in df_stats.columns:
        return None
    series = pd.to_numeric(df_stats[col], errors='coerce')
    if col == 'shd':
        # Keep SHD aggregation aligned with the time-limit plots and summary CSVs.
        return series.mean()
    if col == 'f1score':
        # Use the same aggregation style as runtime/shd for consistent method plots.
        return series.mean()
    return series.mean()


def _metric_label(metric):
    labels = {
        'f1score': 'F1 score',
        'runtime_seconds': 'runningtime',
        'shd': 'SHD',
        'gap': 'MIP gap',
        'lazy_count': 'Lazy constraints',
        'cycle_lazy_count': 'Cycle lazy constraints',
        'clique_lazy_count': 'Clique lazy constraints',
    }
    return labels.get(metric, metric)


def _metric_file_suffix(metric):
    aliases = {
        'f1score': 'f1score',
        'runtime_seconds': 'runtime',
        'shd': 'shd',
        'gap': 'gap',
        'lazy_count': 'lazy_count',
        'cycle_lazy_count': 'cycle_lazy_count',
        'clique_lazy_count': 'clique_lazy_count',
    }
    return aliases.get(metric, metric.replace('.', '_'))


def _find_f1_plateau_start(df_local, f1_tol=1e-3, min_plateau_points=3):
    """
    Find the earliest index i such that f1score from i..end is nearly constant.
    If not found, return 0 (use all rows).
    """
    if 'f1score' not in df_local.columns:
        return 0
    f1 = pd.to_numeric(df_local['f1score'], errors='coerce').to_numpy()
    n = len(f1)
    if n < max(2, min_plateau_points):
        return 0
    for i in range(0, n - min_plateau_points + 1):
        tail = f1[i:]
        tail = tail[~pd.isna(tail)]
        if len(tail) < min_plateau_points:
            continue
        if float(tail.max() - tail.min()) <= float(f1_tol):
            return i
    return 0


def build_runtime_summary_dataframe(
    base_dir='results/exdbn/exdbn_run',
    runtime_prefix='runtime_',
    plateau_by_f1=None,
    f1_tol=1e-3,
    min_plateau_points=3,
):
    """
    Aggregate all runtime_*.csv files under base_dir into one summary dataframe.
    """
    if plateau_by_f1 is None:
        plateau_by_f1 = _env_bool('EXDBN_PLATEAU_BY_F1', default=False)

    metrics = [
        'degree', 'runtime_seconds', 'gap', 'fdr', 'tpr', 'fpr',
        'shd', 'nnz', 'precision', 'f1score', 'g_score', 'lazy_count'
    ]

    runtime_paths = []
    for root, _, files in os.walk(base_dir):
        for file in files:
            if file.startswith(runtime_prefix) and file.endswith('.csv'):
                runtime_paths.append(os.path.join(root, file))
    runtime_paths = sorted(runtime_paths)
    if not runtime_paths:
        return pd.DataFrame()

    rows = []
    for path in runtime_paths:
        df = pd.read_csv(path)
        if df.empty:
            continue

        if 'degree' in df.columns:
            df = df.sort_values('degree').reset_index(drop=True)

        df_stats = df
        if plateau_by_f1 and 'f1score' in df.columns:
            start_idx = _find_f1_plateau_start(df, f1_tol=f1_tol, min_plateau_points=min_plateau_points)
            df_stats = df.iloc[start_idx:].copy()
            if df_stats.empty:
                df_stats = df

        row = {
            'dataset': str(df_stats['dataset'].iloc[0]) if 'dataset' in df_stats.columns else os.path.basename(path),
            'features': int(df_stats['features'].iloc[0]) if 'features' in df_stats.columns else None,
            'samples': int(df_stats['samples'].iloc[0]) if 'samples' in df_stats.columns else None,
            'timelimit': _timelimit_from_filename(path),
            '__source_file__': os.path.basename(path),
        }
        for col in metrics:
            row[f'{col}_mean'] = _aggregate_metric_value(df_stats, col)
            row[f'{col}_std'] = df_stats[col].std() if col in df_stats.columns else None
            # Keep compatibility with existing plotting flow expecting raw metric columns.
            row[col] = row[f'{col}_mean']

        rows.append(row)

    if not rows:
        return pd.DataFrame()

    out = pd.DataFrame(rows)
    out = add_num_vars_column(out)
    return out


def generate_runtime_summary_csv(
    base_dir='results/exdbn/exdbn_run',
    scenario_key='SF-5-0',
    mode='static',
    runtime_prefix='runtime_',
    output_filename=None,
    plateau_by_f1=None,
    f1_tol=1e-3,
    min_plateau_points=3,
):
    """
    Aggregate runtime CSVs ({runtime_prefix}*.csv) into one scenario summary CSV.

    Example:
        runtime_static_SF-5-0_gauss_d20_n2000.csv
        -> grouped into SF-5-0.csv with mean/std columns.
    """
    base_dir = os.path.abspath(base_dir)
    prefix = f'{runtime_prefix}{mode}_{scenario_key}_'
    runtime_paths = []

    for root, _, files in os.walk(base_dir):
        for file in files:
            if file.startswith(prefix) and file.endswith('.csv'):
                runtime_paths.append(os.path.join(root, file))

    runtime_paths = sorted(runtime_paths)
    if not runtime_paths:
        raise FileNotFoundError(
            f'No runtime CSV found for scenario={scenario_key}, mode={mode} under {base_dir}'
        )

    # Switch:
    # - plateau_by_f1=True/False: explicit
    # - plateau_by_f1=None: read EXDBN_PLATEAU_BY_F1 (default False)
    if plateau_by_f1 is None:
        plateau_by_f1 = _env_bool('EXDBN_PLATEAU_BY_F1', default=False)

    metrics = [
        'degree', 'runtime_seconds', 'gap', 'fdr', 'tpr', 'fpr',
        'shd', 'nnz', 'precision', 'f1score', 'g_score', 'lazy_count'
    ]

    rows = []
    for path in runtime_paths:
        df = pd.read_csv(path)
        if df.empty:
            continue

        if 'degree' in df.columns:
            df = df.sort_values('degree').reset_index(drop=True)

        df_stats = df
        if plateau_by_f1 and 'f1score' in df.columns:
            start_idx = _find_f1_plateau_start(df)
            df_stats = df.iloc[start_idx:].copy()
            if df_stats.empty:
                df_stats = df

        row = {
            'dataset': str(df_stats['dataset'].iloc[0]) if 'dataset' in df_stats.columns else os.path.basename(path),
            'features': int(df_stats['features'].iloc[0]) if 'features' in df_stats.columns else None,
            'samples': int(df_stats['samples'].iloc[0]) if 'samples' in df_stats.columns else None,
            'timelimit': _timelimit_from_filename(path),
        }

        for col in metrics:
            row[col] = _aggregate_metric_value(df_stats, col)
        for col in metrics:
            row[f'{col}_std'] = df_stats[col].std() if col in df_stats.columns else None

        rows.append(row)

    if not rows:
        raise RuntimeError(f'All matching runtime CSVs are empty for scenario={scenario_key}')

    out_df = pd.DataFrame(rows).sort_values(['dataset']).reset_index(drop=True)
    ordered_columns = [
        'dataset', 'features', 'samples', 'timelimit',
        'degree', 'runtime_seconds', 'gap', 'fdr', 'tpr', 'fpr', 'shd', 'nnz', 'precision', 'f1score', 'g_score', 'lazy_count',
        'degree_std', 'runtime_seconds_std', 'gap_std', 'fdr_std', 'tpr_std', 'fpr_std', 'shd_std', 'nnz_std',
        'precision_std', 'f1score_std', 'g_score_std', 'lazy_count_std'
    ]
    out_df = out_df[ordered_columns]

    if output_filename is None:
        output_filename = f'{scenario_key}.csv'
    output_path = os.path.join(base_dir, output_filename)
    out_df.to_csv(output_path, index=False)
    return output_path, out_df


def _discover_runtime_scenarios(base_dir='results/exdbn/exdbn_run', modes=('static', 'dynamic')):
    """
    Discover available scenario keys per runtime prefix by scanning all runtime CSV files.
    Returns:
      {
        'runtime_': {'static': {'ER-3-0', ...}, ...},
        'limit_runtime_': {...},
        'clique_runtime_': {...},
      }
    """
    discovered = {}
    pattern = re.compile(
        r'^(?P<prefix>(?:[A-Za-z0-9-]+_)*runtime_)'
        r'(?P<mode>static|dynamic)_'
        r'(?P<scenario>[A-Za-z0-9-]+)_[A-Za-z0-9]+_d\d+_n\d+(?:_.*)?\.csv$'
    )

    for root, _, files in os.walk(base_dir):
        for file in files:
            m = pattern.match(file)
            if not m:
                continue
            prefix = m.group('prefix')
            mode = m.group('mode')
            scenario = m.group('scenario')
            if prefix not in discovered:
                discovered[prefix] = {available_mode: set() for available_mode in modes}
            if mode in discovered[prefix]:
                discovered[prefix][mode].add(scenario)
    return discovered


def generate_all_runtime_summary_tables(
    base_dir='results/exdbn/exdbn_run',
    modes=('static',),
    plateau_by_f1=None,
    method_keys=None,
):
    """
    Generate all summary CSV tables to base_dir:
      - {scenario}.csv
      - limit_{scenario}.csv
      - clique_{scenario}.csv
    based on discovered runtime files.
    """
    base_dir = os.path.abspath(base_dir)
    discovered = _discover_runtime_scenarios(base_dir=base_dir, modes=modes)
    output_paths = []

    prefix_to_output = {
        'runtime_': lambda s: f'{s}.csv',
        'limit_runtime_': lambda s: f'limit_{s}.csv',
        'clique_runtime_': lambda s: f'clique_{s}.csv',
    }
    requested_prefixes = None
    if method_keys:
        requested_prefixes = {_method_runtime_prefix(method) for method in method_keys}

    for runtime_prefix, mode_map in discovered.items():
        if requested_prefixes is not None and runtime_prefix not in requested_prefixes:
            continue
        for mode in modes:
            scenario_keys = sorted(mode_map.get(mode, set()))
            for scenario_key in scenario_keys:
                output_filename = prefix_to_output.get(
                    runtime_prefix,
                    lambda s, prefix=runtime_prefix: (
                        f'{prefix.removesuffix("runtime_").rstrip("_")}_{s}.csv'
                    ),
                )(scenario_key)
                output_path, _ = generate_runtime_summary_csv(
                    base_dir=base_dir,
                    scenario_key=scenario_key,
                    mode=mode,
                    runtime_prefix=runtime_prefix,
                    output_filename=output_filename,
                    plateau_by_f1=plateau_by_f1,
                )
                output_paths.append(output_path)

    return sorted(set(output_paths))


# ============================================================
# 统一版本的绘图函数（使用 num_vars）
# ============================================================
def make_grid_problem_samples_plot(
    data_to_plot,
    y_col,
    label,
    output_dir,
    outputfile: str,
    problem_cols,
    plot_max,
    plot_min,
    problem_name_callback=None,
    y_lim=None,
    method_name_callback=None,
    append_metric_suffix=True,
    row_order=None,
    row_y_limits=None,
    independent_y_axes=False,
    legend_style=None,
    legend_position=None,
    single_scenario_mode=False,
    x_col='num_vars',
    x_label='Number of nodes (d)',
):
    font_size = 8 if single_scenario_mode else 10
    tick_font_size = 6 if single_scenario_mode else 7
    relplot_height = 2.2 if single_scenario_mode else 1.9
    relplot_aspect = 1.5 if single_scenario_mode else 1.5

    if x_col not in data_to_plot.columns:
        raise KeyError(f'Missing x-axis column {x_col!r}')

    data_to_plot[x_col] = pd.to_numeric(data_to_plot[x_col], errors='coerce')
    data_to_plot = data_to_plot.dropna(subset=[x_col]).copy()

    if '.' in y_col:
        file_suffix = y_col.split('.', 1)[1].replace('.', '_')
    else:
        file_suffix = y_col

    # ------------------------
    # Method 名称
    # ------------------------
    if method_name_callback is None:
        if 'params.solver.name' in data_to_plot.columns:
            def method_name_callback(x):
                return x['params.solver.name']
        else:
            def method_name_callback(x):
                return 'EXDBN'

    data_to_plot['Method'] = data_to_plot.apply(method_name_callback, axis=1)

    # ------------------------
    # 行名称（问题类型）
    # ------------------------
    if problem_name_callback is None:
        def problem_name_callback(x):
            return '-'.join(
                f'{x[c]}'.replace('bowfree_admg', 'BF').upper()
                for c in problem_cols
            )

    data_to_plot['row_key'] = data_to_plot[problem_cols].apply(
        problem_name_callback, axis=1
    )

    # ------------------------
    # Seaborn Relplot
    # ------------------------


    # 自动选择 col 参数和分组参数
    col_name = None
    groupby_keys = ['row_key']
    if 'params.problem.number_of_samples' in data_to_plot.columns:
        col_name = 'params.problem.number_of_samples'
        groupby_keys.append('params.problem.number_of_samples')
    elif 'samples' in data_to_plot.columns:
        col_name = 'samples'
        groupby_keys.append('samples')

    relplot_kwargs = dict(
        x=x_col,
        y=y_col + '_mean',
        hue='Method',
        row='row_key',
        data=data_to_plot,
        kind='line',
        height=relplot_height,
        aspect=relplot_aspect,
        linewidth=0.8,
    )
    if row_order is not None:
        relplot_kwargs['row_order'] = row_order
    if col_name:
        relplot_kwargs['col'] = col_name
    # A facet-specific y-limit requires independent y-axes.  This is used for
    # the low-range SF-5 SHD row without constraining the ER rows.
    if row_y_limits or independent_y_axes:
        relplot_kwargs['facet_kws'] = {'sharey': False}

    pic = sns.relplot(**relplot_kwargs)

    pic.fig.subplots_adjust(hspace=0.01, wspace=0.01)

    # ------------------------
    # 填充 std / max / min
    # ------------------------
    # 兼容单行/单列 axes
    axes = pic.axes
    if axes.ndim == 1:
        # 只有一行或一列
        if len(pic.row_names) == 1:
            axes = axes[None, :]
        elif len(pic.col_names) == 1:
            axes = axes[:, None]

    for ax, (g_k, group_data) in zip(
        axes.flat,
        data_to_plot.groupby(groupby_keys, dropna=False)
    ):
        # 兼容单行/单列
        if len(groupby_keys) == 2:
            row_val, col_val = g_k
            row_index = pic.row_names.index(row_val)
            col_index = pic.col_names.index(col_val)
        else:
            row_val = g_k[0]
            row_index = pic.row_names.index(row_val)
            col_index = 0

        ax = axes[row_index, col_index]

        print_solver_params(
            group_data,
            get_solver_columns_names(group_data) + ['Method']
        )

        if row_y_limits and row_val in row_y_limits:
            ax.set_ylim(*row_y_limits[row_val])
        elif y_lim is not None:
            ax.set_ylim(ymax=y_lim)

        ax_handles, ax_labels = axes[0, 0].get_legend_handles_labels()

        for method, method_data in group_data.groupby('Method', dropna=False):
            color = ax_handles[ax_labels.index(method)].get_color()
            method_data = method_data.sort_values(x_col)

            std_col = y_col + '_std'
            if std_col not in method_data.columns and (y_col + '_sd') in method_data.columns:
                std_col = y_col + '_sd'
            if std_col in method_data.columns:
                ax.fill_between(
                    method_data[x_col],
                    method_data[y_col + '_mean'] - method_data[std_col],
                    method_data[y_col + '_mean'] + method_data[std_col],
                    alpha=0.1,
                    color=color,
                )

            if plot_max and (y_col + '_max') in method_data.columns:
                ax.plot(
                    method_data[x_col],
                    method_data[y_col + '_max'],
                    linestyle='--',
                    color=color,
                    linewidth=0.5,
                    alpha=0.4,
                )

            if plot_min and (y_col + '_min') in method_data.columns:
                ax.plot(
                    method_data[x_col],
                    method_data[y_col + '_min'],
                    linestyle='dotted',
                    color=color,
                    linewidth=0.5,
                    alpha=0.4,
                )

    # ------------------------
    # 全局样式
    # ------------------------
    for ax in pic.axes.flatten():
        ax.set_xlabel('')
        ax.set_ylabel('')
        ax.tick_params(axis='both', labelsize=tick_font_size)

    legend_cfg = _legend_layout_config(
        0,
        legend_style=legend_style,
        position_override=legend_position,
        single_scenario_mode=single_scenario_mode,
    )

    pic.figure.text(
        x=0.5,
        y=legend_cfg['xlabel_y'] + 0.08,
            s=x_label,
        ha='center',
        fontsize=9
    )

    if single_scenario_mode and len(pic.row_names) == 1:
        pic.figure.text(
            x=0.055, y=0.5,
            s=label,
            ha='center',
            va='center',
            rotation=90,
            fontsize=font_size
        )
    else:
        pic.figure.text(
            x=0.85, y=0.5,
            s=label,
            ha='center',
            va='center',
            rotation=270,
            fontsize=font_size + 4
        )

        row_label_side = os.getenv('EXDBN_ROW_LABEL_SIDE', 'left').strip().lower()
        for i, row_name in enumerate(pic.row_names):
            # Place right-side row labels past the right-most facet, where
            # they remain distinct from the shared metric label and legend.
            row_axis = pic.axes[i, -1] if row_label_side == 'right' else pic.axes[i, 0]
            row_axis.annotate(
                text=row_name,
                xy=(1.12 if row_label_side == 'right' else -0.2, 0.0 if row_label_side == 'right' else 0.5),
                xycoords='axes fraction',
                ha='center',
                va='bottom' if row_label_side == 'right' else 'center',
                fontsize=font_size,
                rotation=90
            )

    for j, col_name in enumerate(pic.col_names):
        pic.axes[0, j].annotate(
            text=f'n={col_name}',
            xy=(0.5, 1.1 if single_scenario_mode else 1.02),
            xycoords='axes fraction',
            ha='center',
            va='center',
            fontsize=font_size
        )

    pic.set_titles('')
    if x_col == 'num_vars':
        max_number_vars = ((round(data_to_plot[x_col].max()) // 5) + 1) * 5
        min_number_vars = (round(data_to_plot[x_col].min()) // 5) * 5
        pic.set(xticks=list(range(min_number_vars, max_number_vars + 1, 5)))

    figure = pic.figure
    # A selected method can be absent from the first facet.  Merge handles
    # from all facets so the shared legend still represents every method.
    legend_entries = {}
    for ax in pic.axes.flatten():
        ax_handles, ax_labels = ax.get_legend_handles_labels()
        for handle, label_text in zip(ax_handles, ax_labels):
            legend_entries.setdefault(label_text, handle)
    labels = list(legend_entries)
    handles = [legend_entries[label_text] for label_text in labels]
    legend_cfg = _legend_layout_config(
        len(labels),
        legend_style=legend_style,
        position_override=legend_position,
        single_scenario_mode=single_scenario_mode,
    )
    if legend_cfg['kind'] == 'boxed':
        # Keep the original outside-right box for half-running-time layouts.
        from matplotlib.lines import Line2D as _Line2D
        from matplotlib.offsetbox import AnchoredOffsetbox, DrawingArea, HPacker, TextArea, VPacker

        legend_rows = []
        for idx, (handle, label_text) in enumerate(zip(handles, labels)):
            color = handle.get_color() if hasattr(handle, 'get_color') else 'black'
            da = DrawingArea(16, 8, 0, 0)
            sample = _Line2D([0, 16], [4, 4], color=color, linewidth=1.1)
            da.add_artist(sample)

            label_lines = str(label_text).split('\n')
            method_line = label_lines[0]
            detail_line = '\n'.join(label_lines[1:]).strip()

            text_children = [
                TextArea(method_line, textprops=dict(color=color, fontsize=7)),
            ]
            if detail_line:
                text_children.append(TextArea(detail_line, textprops=dict(color='black', fontsize=7)))
            if idx < len(labels) - 1:
                text_children.append(TextArea(" ", textprops=dict(color='black', fontsize=3)))

            text_box = VPacker(children=text_children, align="left", pad=0, sep=1)
            row = HPacker(children=[da, text_box], align="center", pad=0, sep=5)
            legend_rows.append(row)

        legend_box = VPacker(children=legend_rows, align="left", pad=0, sep=2)
        anchored_box = AnchoredOffsetbox(
            loc=legend_cfg['loc'],
            child=legend_box,
            frameon=True,
            bbox_to_anchor=legend_cfg['bbox_to_anchor'],
            bbox_transform=figure.transFigure,
            borderpad=0.3,
            pad=0.3,
        )
        anchored_box.patch.set_linewidth(0.6)
        figure.add_artist(anchored_box)
    else:
        figure.legend(
            handles,
            labels,
            loc=legend_cfg['loc'],
            ncol=legend_cfg['ncol'],
            bbox_to_anchor=legend_cfg['bbox_to_anchor'],
            borderaxespad=0.0,
            frameon=True,
            fontsize=legend_cfg['legend_fontsize'],
            handlelength=1.2,
            handletextpad=0.4,
            labelspacing=0.25,
            borderpad=0.25,
            columnspacing=0.6,
            markerscale=0.8,
        )

    figure.tight_layout(rect=legend_cfg['tight_rect'])
    pic._legend.remove()

    os.makedirs(output_dir, exist_ok=True)
    if append_metric_suffix:
        filename = f'{outputfile}_{file_suffix}.png'
    else:
        filename = f'{outputfile}.png'

    formats = [item.strip().lower().lstrip('.') for item in os.getenv('EXDBN_PLOT_FORMATS', 'png').split(',') if item.strip()]
    dpi = int(os.getenv('EXDBN_PLOT_DPI', '300'))
    stem = os.path.splitext(filename)[0]
    for image_format in dict.fromkeys(formats):
        figure.savefig(join(output_dir, f'{stem}.{image_format}'), bbox_inches='tight', dpi=dpi)
    plt.close(figure)


def _runtime_dataset_label(row):
    """
    Convert dataset stem to:
    {VARIANT-INTRAEDGE-ARORDER}

    Handles stems like:
    - static_SF-3-1_gauss_d35_n2000
    - dynamic_SF-3-1_gauss_d35_n2000
    - SF-3-1_d35_n2000
    """
    dataset = str(row.get("dataset", ""))

    # Newer format with static|dynamic + sem_type
    m = re.match(
        r'^(?:static|dynamic)_([A-Za-z0-9-]+)_[A-Za-z0-9]+_d(\d+)_n(\d+)$',
        dataset
    )
    if m:
        key, _, _ = m.groups()
        return key

    # Format without static/dynamic, sem_type
    m = re.match(r'^([A-Za-z0-9-]+)_d(\d+)_n(\d+)$', dataset)
    if m:
        key, _, _ = m.groups()
        return key

    # Fallback
    return dataset.removesuffix(".npz")


def _runtime_dataset_dimension_label(row):
    """
    Row label for time-limit plots when the same scenario has multiple d values.
    The title prefix is controlled from shell via EXDBN_ROW_TITLE.
    """
    dataset = str(row.get("dataset", ""))
    title = os.getenv('EXDBN_ROW_TITLE', '').strip()

    d_match = re.search(r'_d(\d+)_', dataset)
    if d_match:
        d_label = f'd={d_match.group(1)}'
    else:
        d_label = dataset.removesuffix(".npz")

    return f'{title}\n{d_label}' if title else d_label


def _runtime_dimension_row_order(data):
    if 'dataset' not in data.columns:
        return None

    labels = data.apply(_runtime_dataset_dimension_label, axis=1)
    dims = pd.to_numeric(
        data['dataset'].astype(str).str.extract(r'_d(\d+)_', expand=False),
        errors='coerce',
    )
    order_df = pd.DataFrame({'label': labels, 'dim': dims})
    order_df = order_df.drop_duplicates()
    order_df['dim_sort'] = order_df['dim'].fillna(float('inf'))
    order_df = order_df.sort_values(['dim_sort', 'label'])
    return order_df['label'].tolist()


def plot_three_method_tables_one_figure(
    base_dir='results/exdbn/exdbn_run',
    scenario_key='SF-5-0',
    output_dir='figures',
    output_name=None,
    legend_style=None,
):
    """
    Plot three summary tables in one figure:
      - {scenario_key}.csv (milp/runtime)
      - limit_{scenario_key}.csv
      - clique_{scenario_key}.csv
    """
    table_specs = [
        (os.path.join(base_dir, f'{scenario_key}.csv'), 'milp'),
        (os.path.join(base_dir, f'limit_{scenario_key}.csv'), 'edge_limit'),
        (os.path.join(base_dir, f'clique_{scenario_key}.csv'), 'milp_clique'),
    ]

    dfs = []
    for path, method in table_specs:
        if not os.path.exists(path):
            continue
        df = pd.read_csv(path)
        if df.empty:
            continue
        df = add_num_vars_column(df, filename=os.path.basename(path))
        df['Method'] = method
        dfs.append(df)

    if not dfs:
        raise FileNotFoundError(f'No non-empty method summary table found under {base_dir}')

    data = pd.concat(dfs, ignore_index=True)
    data = data.dropna(subset=['num_vars']).copy()
    data['num_vars'] = pd.to_numeric(data['num_vars'], errors='coerce')
    data = data.dropna(subset=['num_vars']).copy()
    data['num_vars'] = data['num_vars'].astype(int)
    data = data.sort_values(['Method', 'samples', 'num_vars']).reset_index(drop=True)

    legend_style = _normalize_legend_style(legend_style, default='standard')
    label_map = _legend_method_labels(legend_style)

    method_order = ['milp', 'edge_limit', 'milp_clique']
    # palette = {'milp': '#1f77b4',
    #            'edge_limit': '#ff7f0e',
    #            'milp_clique': '#2ca02c'}
    palette = {"milp": "#1f77b4",
                "milp_clique": "#ff7f0e",
                "edge_limit": "#2ca02c"}

    metrics = [
        ('f1score', 'F1 score'),
        ('runtime_seconds', 'Runtime (seconds)'),
        ('shd', 'SHD'),
    ]

    fig, axes = plt.subplots(1, 3, figsize=(13, 4), sharex=True)

    for ax, (metric, ylabel) in zip(axes, metrics):
        mean_col = f'{metric}_mean' if f'{metric}_mean' in data.columns else metric
        std_col = f'{metric}_std'

        for method in method_order:
            mdf = data[data['Method'] == method]
            if mdf.empty or mean_col not in mdf.columns:
                continue
            x = pd.to_numeric(mdf['num_vars'], errors='coerce')
            y = pd.to_numeric(mdf[mean_col], errors='coerce')
            mask = (~x.isna()) & (~y.isna())
            if not mask.any():
                continue
            x = x[mask]
            y = y[mask]
            ax.plot(x, y, marker='o', linewidth=1.2, markersize=3.5, color=palette[method], label=method)
            if std_col in mdf.columns:
                s = pd.to_numeric(mdf[std_col], errors='coerce')[mask].fillna(0.0)
                ax.fill_between(x, y - s, y + s, color=palette[method], alpha=0.12)

        ax.set_title(ylabel, fontsize=10)
        ax.set_xlabel('d (number of nodes)')
        ax.grid(alpha=0.25)

    axes[0].set_ylabel('Value')
    handles, labels = axes[0].get_legend_handles_labels()
    if handles:
        mapped_labels = [label_map.get(label, label) for label in labels]
        legend_cfg = _legend_layout_config(len(mapped_labels), legend_style=legend_style)
        fig.legend(
            handles,
            mapped_labels,
            loc=legend_cfg['loc'],
            ncol=legend_cfg['ncol'],
            bbox_to_anchor=legend_cfg['bbox_to_anchor'],
            frameon=True,
            fontsize=legend_cfg['legend_fontsize'],
        )

    fig.suptitle(f'{scenario_key}: milp vs edge_limit vs milp_clique', fontsize=11, y=1.02)
    fig.tight_layout(rect=_legend_layout_config(len(labels), legend_style=legend_style)['tight_rect'])

    os.makedirs(output_dir, exist_ok=True)
    if output_name is None:
        output_name = f'exdbn_three_methods_{scenario_key}.png'
    out_path = os.path.join(output_dir, output_name)
    fig.savefig(out_path, dpi=300, bbox_inches='tight')
    plt.close(fig)
    return out_path


def plot_three_method_tables_as_three_figures(
    base_dir='results/exdbn/exdbn_run',
    scenario_keys=('ER-3-0', 'ER-4-0', 'SF-5-0'),
    output_dir='figures',
    output_prefix='exdbn_methods',
    legend_style=None,
    y_metrics=None,
    x_axis='nodes',
    features=None,
    timelimits=None,
    method_keys=None,
):
    """
    Reuse existing grid plotting logic and output three figures:
      - metrics requested by EXDBN_Y_AXIS / y_metrics
    with method comparison from:
      {scenario}.csv, limit_{scenario}.csv, clique_{scenario}.csv
    for each scenario in scenario_keys.
    """
    if isinstance(scenario_keys, str):
        scenario_keys = [s.strip() for s in scenario_keys.split(',') if s.strip()]
    scenario_keys = list(scenario_keys)
    if not scenario_keys:
        scenario_keys = ['ER-3-0', 'ER-4-0', 'SF-5-0']

    timelimit_axis = x_axis in {'timelimit', 'time_limit', 'time-limit'}
    # "Single scenario" is axis-dependent:
    #   nodes     -> exactly one requested scenario key;
    #   timelimit -> exactly one requested feature/node count.
    # An unset EXDBN_FEATURES is not considered a single timelimit scenario,
    # even if filtering happens to leave only one feature in the data.
    if timelimit_axis:
        single_scenario_mode = bool(features) and len({int(value) for value in features}) == 1
    else:
        single_scenario_mode = len(scenario_keys) == 1

    method_keys = method_keys or ['milp', 'clique', 'edge_limit']
    dfs = []
    scenario_method_presence = {k: set() for k in scenario_keys}
    for scenario_key in scenario_keys:
        table_specs = [
            (os.path.join(base_dir, _method_summary_filename(method, scenario_key)), method)
            for method in method_keys
        ]
        for path, method_name in table_specs:
            if not os.path.exists(path):
                continue
            df = pd.read_csv(path)
            if df.empty:
                continue
            df = add_num_vars_column(df, filename=os.path.basename(path))
            df['Method'] = method_name
            dfs.append(df)
            scenario_method_presence[scenario_key].add(method_name)

    if not dfs:
        raise FileNotFoundError(f'No non-empty method summary table found under {base_dir}')

    data = pd.concat(dfs, ignore_index=True)
    data = data.dropna(subset=['num_vars']).copy()
    data['num_vars'] = pd.to_numeric(data['num_vars'], errors='coerce')
    data = data.dropna(subset=['num_vars']).copy()
    data['num_vars'] = data['num_vars'].astype(int)

    if features:
        requested_features = {int(value) for value in features}
        data = data[data['num_vars'].isin(requested_features)].copy()

    if timelimits:
        if 'timelimit' not in data.columns:
            raise KeyError(
                'EXDBN_TIMELIMITS is set, but the summary tables have no timelimit column. '
                'Use EXDBN_GENERATE_SUMMARY_TABLES=1 to regenerate them.'
            )
        requested_timelimits = {float(value) for value in timelimits}
        parsed_timelimits = pd.to_numeric(data['timelimit'], errors='coerce')
        data = data[parsed_timelimits.isin(requested_timelimits)].copy()

    if data.empty:
        raise RuntimeError(
            f'No rows match EXDBN_FEATURES={features!r} and '
            f'EXDBN_TIMELIMITS={timelimits!r}'
        )

    # Keep only requested scenarios in case unrelated rows exist.
    if 'dataset' in data.columns:
        pattern = '|'.join(re.escape(s) for s in scenario_keys)
        data = data[data['dataset'].astype(str).str.contains(pattern, na=False)].copy()
    if data.empty:
        raise RuntimeError(f'No rows left after filtering scenarios={scenario_keys}')
    valid_scenarios = []
    for s in scenario_keys:
        methods = scenario_method_presence.get(s, set())
        if methods:
            valid_scenarios.append(s)
            missing = set(method_keys) - methods
            if missing:
                print(f'[PLOT] scenario={s} missing methods={sorted(missing)}, plotting available={sorted(methods)}')
    row_order = []
    if 'dataset' in data.columns:
        ds = data['dataset'].astype(str)
        for s in valid_scenarios:
            if ds.str.contains(re.escape(s), na=False).any():
                row_order.append(s)
    if not row_order:
        row_order = valid_scenarios or scenario_keys

    single_scenario_output = _env_bool('EXDBN_SINGLE_SCENARIO_OUTPUT', default=False)
    scenario_suffix = None
    legend_position = None
    if single_scenario_output and single_scenario_mode and len(row_order) == 1:
        scenario_suffix = row_order[0]
        legend_position = 'bottom'

    default_metrics = ['runtime_seconds', 'f1score', 'shd']
    if y_metrics is None or not str(y_metrics).strip():
        y_metrics = default_metrics
    else:
        y_metrics = [
            item.strip()
            for item in str(y_metrics).replace(',', '/').split('/')
            if item.strip()
        ] or default_metrics

    # Ensure *_mean columns exist for plotting function.
    for metric in y_metrics:
        mean_col = f'{metric}_mean'
        if mean_col not in data.columns and metric in data.columns:
            data[mean_col] = data[metric]
        std_col = f'{metric}_std'
        sd_col = f'{metric}_sd'
        if std_col not in data.columns and sd_col in data.columns:
            data[std_col] = data[sd_col]

    if legend_style is None:
        # Preserve the original bottom-center layout for a single scenario;
        # use the expanded right-side layout only for multi-scenario figures.
        legend_style = 'single_data' if single_scenario_mode else 'standard'
    legend_style = _normalize_legend_style(legend_style, default='standard')
    legend_labels = _legend_method_labels(legend_style)

    def method_name_callback(x):
        method = x.get('Method', 'exdbn')
        return legend_labels.get(method, method)

    os.makedirs(output_dir, exist_ok=True)
    if timelimit_axis:
        x_col = 'timelimit'
        x_label = 'Time limit(s)'
        problem_name_callback = _runtime_dataset_dimension_label
        dimension_row_order = _runtime_dimension_row_order(data)
        if dimension_row_order:
            row_order = dimension_row_order
    else:
        x_col = 'num_vars'
        x_label = 'Number of nodes (d)'
        problem_name_callback = _runtime_dataset_label

    output_paths = []
    sf_shd_ymax_text = os.getenv('EXDBN_SF_SHD_YMAX', '').strip()
    sf_shd_ymax = float(sf_shd_ymax_text) if sf_shd_ymax_text else None
    for metric in y_metrics:
        mean_col = f'{metric}_mean'
        if mean_col not in data.columns:
            print(f'[PLOT] skip metric={metric}: missing column {mean_col}')
            continue

        suffix = _metric_file_suffix(metric)
        outputfile = f'{output_prefix}_{suffix}_{scenario_suffix}' if scenario_suffix else f'{output_prefix}_{suffix}'
        make_grid_problem_samples_plot(
            data_to_plot=data,
            y_col=metric,
            label=_metric_label(metric),
            output_dir=output_dir,
            outputfile=outputfile,
            problem_cols=['dataset'],
            plot_max=False,
            plot_min=False,
            problem_name_callback=problem_name_callback,
            y_lim=None,
            method_name_callback=method_name_callback,
            append_metric_suffix=False,
            row_order=row_order,
            # When an explicit SF limit is not requested, SHD panels retain
            # independent, data-driven y-ranges rather than sharing the ER range.
            row_y_limits=({'cliquefree-sf-5-0': (0.0, sf_shd_ymax)}
                          if metric == 'shd' and sf_shd_ymax is not None and not timelimit_axis
                          else None),
            independent_y_axes=(metric == 'shd' and not timelimit_axis),
            legend_style=legend_style,
            legend_position=legend_position,
            single_scenario_mode=single_scenario_mode,
            x_col=x_col,
            x_label=x_label,
        )
        output_paths.append(os.path.join(output_dir, f'{outputfile}.png'))

    return output_paths


def discover_summary_scenarios(base_dir='results/exdbn/exdbn_run'):
    """
    Discover scenario keys from summary tables in base_dir.
    Accepts any of:
      {scenario}.csv, limit_{scenario}.csv, clique_{scenario}.csv
    """
    base_dir = os.path.abspath(base_dir)
    scenarios = set()
    patterns = [
        re.compile(r'^(?P<scenario>[A-Za-z0-9-]+)\.csv$'),
        re.compile(r'^limit_(?P<scenario>[A-Za-z0-9-]+)\.csv$'),
        re.compile(r'^clique_(?P<scenario>[A-Za-z0-9-]+)\.csv$'),
    ]
    for file in os.listdir(base_dir):
        if not file.endswith('.csv'):
            continue
        for p in patterns:
            m = p.match(file)
            if m:
                scenario = m.group('scenario')
                if re.match(r'^[A-Za-z]+-\d+-\d+$', scenario):
                    scenarios.add(scenario)
                break
    return sorted(scenarios)


# ============================================================
# main
# ============================================================
if __name__ == "__main__":
    scenario_keys = os.getenv('EXDBN_SCENARIO_KEYS', os.getenv('SCENARIO_KEYS', 'all'))
    x_axis = os.getenv('EXDBN_X_AXIS', 'nodes').strip().lower()
    summary_modes = os.getenv('EXDBN_SUMMARY_MODES', 'static')
    y_axis = os.getenv('EXDBN_Y_AXIS', 'runtime_seconds/f1score/shd')
    method_keys = _env_method_keys()
    features = _env_number_list('EXDBN_FEATURES', int)
    timelimits = _env_number_list('EXDBN_TIMELIMITS', float)
    project_dir = os.path.dirname(os.path.abspath(__file__))

    if str(scenario_keys).strip().lower() not in {'', 'all'} and ',' not in str(scenario_keys):
        default_base_dir = os.path.join(project_dir, 'results', str(scenario_keys))
        default_output_dir = os.path.join(project_dir, 'reports', str(scenario_keys))
    else:
        default_base_dir = os.path.join(project_dir, 'results')
        default_output_dir = os.path.join(project_dir, 'reports')

    base_dir = os.getenv('EXDBN_TABLE_BASE_DIR', default_base_dir)
    output_dir = os.getenv('EXDBN_PLOT_OUTPUT_DIR', default_output_dir)
    output_prefix = os.getenv('EXDBN_PLOT_OUTPUT_PREFIX', f'{x_axis}_{summary_modes}')
    legend_style = os.getenv('EXDBN_LEGEND_STYLE', '')
    generate_summaries = _env_bool('EXDBN_GENERATE_SUMMARY_TABLES', default=True)
    modes = tuple(m.strip() for m in summary_modes.split(',') if m.strip())

    if x_axis not in {'nodes', 'node', 'd', 'timelimit', 'time_limit', 'time-limit'}:
        raise ValueError(
            f"Unsupported EXDBN_X_AXIS={x_axis!r} in this plotting entry. "
            "Use EXDBN_X_AXIS=nodes or EXDBN_X_AXIS=timelimit."
        )

    if generate_summaries:
        generated = generate_all_runtime_summary_tables(
            base_dir=base_dir,
            modes=modes,
            method_keys=method_keys,
        )
        if generated:
            print(f'Generated {len(generated)} summary tables under {base_dir}')
        else:
            print(f'No runtime CSV found for summary generation under {base_dir}')

    if isinstance(scenario_keys, str) and scenario_keys.strip().lower() == 'all':
        scenario_keys = discover_summary_scenarios(base_dir=base_dir)
        if not scenario_keys:
            base_name = os.path.basename(os.path.abspath(base_dir))
            if os.path.exists(os.path.join(base_dir, f'{base_name}.csv')) or os.path.exists(os.path.join(base_dir, f'clique_{base_name}.csv')):
                scenario_keys = [base_name]
            else:
                raise FileNotFoundError(f'No summary scenario tables found under {base_dir}')
        scenario_keys = ','.join(scenario_keys)

    output_paths = plot_three_method_tables_as_three_figures(
        base_dir=base_dir,
        scenario_keys=scenario_keys,
        output_dir=output_dir,
        output_prefix=output_prefix,
        legend_style=legend_style or None,
        y_metrics=y_axis,
        x_axis=x_axis,
        features=features,
        timelimits=timelimits,
        method_keys=method_keys,
    )
    for path in output_paths:
        print(f'Figure saved to {path}')
