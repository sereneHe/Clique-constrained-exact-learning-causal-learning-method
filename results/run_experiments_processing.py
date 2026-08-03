import math
from os.path import join

import hydra
import mlflow
from matplotlib import pyplot as plt
from omegaconf import DictConfig, OmegaConf

import polars as pl

from dagsolvers.experiments_utils import log_params_from_omegaconf_dict
from dagsolvers.utils import log_exceptions
from results.results_exmag_pavel import generate_exmag_graphs, generate_metrics_plots
from data_load_utils import load_data, save_dataframe, load_dataframe


@hydra.main(version_base=None,  config_path="./processing_conf", config_name="config")
@log_exceptions
def start_experiments_processing(cfg: DictConfig) -> None:

    conf_yaml = OmegaConf.to_yaml(cfg)
    if cfg.load_from_file is not None:
        df = load_dataframe(cfg.load_from_file)
    else:
        data = cfg.experiments_sources
        df, _ = load_data(data, csv_file_path=cfg.csv_file_path)

    if 'filter1' in cfg.filter:
        df = df[(df["params.solver.name"] != 'exmag') | (df["params.problem.number_of_samples"] == '50')]


    if 'filter2' in cfg.filter:
        df = df[(df["params.problem.name"] != 'bowfree_admg') | ( (df["params.problem.pdir"] != '0.2') | (df["params.problem.max_in_arrows"] == '3'))]
        df = df[(df["params.problem.name"] != 'bowfree_admg') | ( (df["params.problem.pdir"] != '0.4') | (df["params.problem.max_in_arrows"] != '3'))]


    mlflow.set_experiment(experiment_name=cfg.experiment)
    with mlflow.start_run():
        log_params_from_omegaconf_dict(cfg)
        output_dir = hydra.core.hydra_config.HydraConfig.get().runtime.output_dir
        mlflow.log_text(output_dir, 'work_dir.txt')
        with open(join(output_dir, 'config.yaml'), 'w') as f:
            f.write(conf_yaml)
        mlflow.log_artifact(join(output_dir, 'config.yaml'))
        if cfg.load_from_file is None:
            save_dataframe(df, join(output_dir, 'dataframe'))
        if cfg.type == 'EXMAG':
            generate_metrics_plots(df, output_dir, f'graphs_metrics',cfg)
        elif cfg.type == 'CLIQUE_WIDTH':
            df = pl.from_pandas(df)
            df = df.with_columns([
                pl.col("params.solver.time_limit").cast(pl.Int64),
                ('er-' + pl.col(
                    "params.problem.intra_edge_ratio") + '-d' + pl.col("params.problem.number_of_variables")+'-n' + pl.col("params.problem.number_of_samples")).alias('problem'),
                (pl.col(
                    "params.solver.name") + '-cl_size' + pl.col("params.solver.max_clique_size")).alias('solver_text')
            ])
            df = df.select(["params.solver.time_limit", "problem", 'solver_text', "metrics.t0.15_shd"])

            print(df)
            problems = df["problem"].unique().to_list()
            n_problems = len(problems)

            n_cols = 2  # math.ceil(math.sqrt(n_problems))
            n_rows = math.ceil(n_problems / n_cols)

            fig, axes = plt.subplots(n_rows, n_cols, figsize=(4 * n_cols, 3 * n_rows), squeeze=False)

            for i, problem in enumerate(problems):
                r, c = divmod(i, n_cols)
                ax = axes[r, c]

                sub_df = df.filter(pl.col("problem") == problem).sort("params.solver.time_limit")

                solvers = df["solver_text"].unique().to_list()
                for solver in solvers:
                    sub_df_solver = sub_df.filter(pl.col("solver_text") == solver)
                    sub_df_solver = sub_df_solver.group_by(["params.solver.time_limit", "problem", 'solver_text']).agg(
        pl.col("metrics.t0.15_shd").mean().alias("shd_mean")
    )
                    sub_df_solver = sub_df_solver.sort("params.solver.time_limit")
                    ax.plot(sub_df_solver["params.solver.time_limit"], sub_df_solver["shd_mean"], label=solver)

                #ax.plot(sub_df["params.solver.time_limit"], sub_df["metrics.t0.15_shd"], label=str(problem))

                ax.set_title(f"{problem}")
                ax.set_xlabel("Time limit")
                ax.set_ylabel("SHD")
                # ax.grid(True, linestyle="--", alpha=0.5)
                ax.legend()

            # Hide empty subplots if any
            for j in range(i + 1, n_rows * n_cols):
                r, c = divmod(j, n_cols)
                axes[r, c].axis("off")

            plt.tight_layout()
            plt.savefig(join(output_dir, "convergence.png"), dpi=300, bbox_inches="tight")
            plt.show()

            print('CLIQUE_WIDTH')
            pass


if __name__ == "__main__":
    start_experiments_processing()