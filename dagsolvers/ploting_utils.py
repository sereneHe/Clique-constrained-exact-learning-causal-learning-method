import os
from os.path import join

import numpy as np
from matplotlib import pyplot as plt

from dagsolvers.dagsolver_utils import plot, plot_heatmap


def make_plots(run, W_true, W_est, best_W, W_bi_true, Wbi, best_Wbi, intra_nodes, A_true, A_est, best_A, inter_nodes, output_dir, dpis):
    if isinstance(dpis, int):
        dpis = [dpis]
    for dpi in dpis:
        dpi_str=f'_{dpi}' if dpi != dpis[0] else ''

        plot(W_true, intra_nodes, filename=join(output_dir,f'W_true{dpi_str}.png'), dpi=dpi)
        run.log_artifact(join(output_dir, f'W_true{dpi_str}.png'))
        if Wbi is not None:
            plot_heatmap(best_Wbi, intra_nodes, intra_nodes, filename=join(output_dir,f'W_bi_est_heatmap{dpi_str}.png'), dpi=dpi)
            run.log_artifact(join(output_dir,f'W_bi_est_heatmap{dpi_str}.png'))
            plot_heatmap(Wbi, intra_nodes, intra_nodes, filename=join(output_dir,f'W_bi_est_no_t_heatmap{dpi_str}.png'), dpi=dpi)
            run.log_artifact(join(output_dir,f'W_bi_est_no_t_heatmap{dpi_str}.png'))
            plot(best_Wbi, intra_nodes, filename=join(output_dir,f'W_bi_est{dpi_str}.png'), dpi=dpi)
            run.log_artifact(join(output_dir,f'W_bi_est{dpi_str}.png'))
            plot(Wbi, intra_nodes, filename=join(output_dir,f'W_bi_est_no_t{dpi_str}.png'), dpi=dpi)
            run.log_artifact(join(output_dir,f'W_bi_est_no_t{dpi_str}.png'))
            plot_heatmap(W_bi_true, intra_nodes, intra_nodes, filename=join(output_dir,f'W_bi_true_heatmap{dpi_str}.png'), dpi=dpi)
            run.log_artifact(join(output_dir,f'W_bi_true_heatmap{dpi_str}.png'))
            plot(W_bi_true, intra_nodes, filename=join(output_dir,f'W_bi_true{dpi_str}.png'), dpi=dpi)
            run.log_artifact(join(output_dir,f'W_bi_true{dpi_str}.png'))

        plot_heatmap(W_true, intra_nodes, intra_nodes, filename=join(output_dir,f'W_true_heatmap{dpi_str}.png'), dpi=dpi)
        run.log_artifact(join(output_dir,f'W_true_heatmap{dpi_str}.png'))
        plot(best_W, intra_nodes, filename=join(output_dir,f'W_est{dpi_str}.png'), dpi=dpi)
        run.log_artifact(join(output_dir,f'W_est{dpi_str}.png'))
        plot_heatmap(best_W, intra_nodes, intra_nodes, filename=join(output_dir,f'W_est_heatmap{dpi_str}.png'), dpi=dpi)
        run.log_artifact(join(output_dir,f'W_est_heatmap{dpi_str}.png'))
        plot(W_est, intra_nodes, filename=join(output_dir,f'W_est_no_t{dpi_str}.png'), dpi=dpi)
        run.log_artifact(join(output_dir,f'W_est_no_t.png'))
        plot_heatmap(W_est, intra_nodes, intra_nodes, filename=join(output_dir,f'W_est_no_t_heatmap{dpi_str}.png'), dpi=dpi)
        run.log_artifact(join(output_dir,f'W_est_no_t_heatmap{dpi_str}.png'))

        for i, A_est_i in enumerate(A_est):
            lag_inter_nodes = [n for n in inter_nodes if f'_lag{i+1}' in n]
            plot(A_est_i, None, filename=join(output_dir,f'A_est_{i}_no_t{dpi_str}.png'), dpi=dpi)
            run.log_artifact(join(output_dir,f'A_est_{i}_no_t{dpi_str}.png'))
            plot_heatmap(A_true[i], intra_nodes, lag_inter_nodes, filename=join(output_dir,f'A_true_{i}_heatmap{dpi_str}.png'), dpi=dpi)
            run.log_artifact(join(output_dir,f'A_true_{i}_heatmap{dpi_str}.png'))
            plot_heatmap(A_est_i, intra_nodes, lag_inter_nodes, filename=join(output_dir,f'A_est_{i}_no_t_heatmap{dpi_str}.png'), dpi=dpi)
            run.log_artifact(join(output_dir,f'A_est_{i}_no_t_heatmap{dpi_str}.png'))
            plot_heatmap(best_A[i], intra_nodes, lag_inter_nodes, filename=join(output_dir,f'A_est_{i}_heatmap{dpi_str}.png'), dpi=dpi)
            run.log_artifact(join(output_dir,f'A_est_{i}_heatmap{dpi_str}.png'))




def draw_adjacency_matrix_colormap_with_variables(adjacency_matrix, number_of_lags, d, title, result_folder,
                                                  variable_names, add_title=False):
    # https://stackoverflow.com/questions/38973868/adjusting-gridlines-and-ticks-in-matplotlib-imshow

    plt.figure()
    im = plt.imshow(adjacency_matrix[:, -d:], interpolation='none')

    # https://matplotlib.org/3.1.1/api/_as_gen/matplotlib.pyplot.gca.html
    ax = plt.gca()

    plt.tick_params(left=False,
                    top=False,
                    bottom=False,
                    labelleft=True,
                    labeltop=False,
                    labelbottom=True)

    # Labels for major ticks
    ax.set_xticklabels(variable_names[-d:], rotation=-90)
    ax.set_yticklabels(variable_names)

    total_d = d * (number_of_lags + 1)

    # Major ticks
    ax.set_xticks(np.arange(0, d, 1))
    ax.set_yticks(np.arange(0, total_d, 1))

    # Minor ticks
    ax.set_xticks(np.arange(-.5, d, 1), minor=True)
    ax.set_yticks(np.arange(-.5, total_d, 1), minor=True)

    # Gridlines based on minor ticks
    ax.grid(which='minor', color='w', linestyle='-', linewidth=0.5)

    if add_title:
        plt.title(title, fontsize=20)

    # Saving the plot as an image
    plt.savefig(os.path.join(result_folder, title.replace(" ", "_") + "_Matrix_Colormap.png"), bbox_inches="tight")
    plt.close('all')  # close all plots, otherwise it would consume memory
