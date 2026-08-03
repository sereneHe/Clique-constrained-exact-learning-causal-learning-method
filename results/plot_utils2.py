from os.path import join

import mlflow
import pandas as pd
import seaborn as sns
from matplotlib import pyplot as plt

from results.data_load_utils import print_solver_params, get_solver_columns_names


def make_grid_problem_samples_plot2(data_to_plot, y_col, label, output_dir, outputfile:str, problem_cols, plot_max, plot_min, problem_name_callback, y_lim=None, method_name_callback=None, method_detail_names=False):
    font_size = 10
    max_number_vars = ((round(max(data_to_plot['params.problem.number_of_variables'])) // 5) + 1) * 5
    min_number_vars = (round(min(data_to_plot['params.problem.number_of_variables'])) // 5) * 5
    file_suffix = y_col.split('.',1)[1].replace('.','_')

    method_cols = ['params.solver.name', 'params.solver.time_limit','params.solver.exmag_version', 'params.solver.note', 'params.solver.tabu_edges', 'params.solver.lambda1', 'params.solver.reg_type', 'params.problem.number_of_samples']#, 'params.solver.callback_mode']#, 'params.solver.time_limit']
    if method_name_callback is None:
        def method_name_callback(x):
            solver_name = x['params.solver.name'] + ' ' + f'{x['params.problem.number_of_samples']}'
            if method_detail_names:
                if solver_name == 'exdbn':
                    solver_name = solver_name + ' ' + x['params.solver.callback_mode']
                if solver_name == 'exmag':
                    return f'{solver_name} {x['params.solver.time_limit']} {x['params.solver.exmag_version']} {x['params.solver.note']} tabu: {x['params.solver.tabu_edges']} {x['params.solver.lambda1']} {x['params.solver.reg_type']}'
            return solver_name

    #data_to_plot = data_to_plot.rename(columns={'params.solver.name': 'Method'})
    data_to_plot['Method'] = data_to_plot[method_cols].apply(lambda x : method_name_callback(x), axis=1)
    if problem_name_callback is None:
        def problem_name_callback(x):
            return '-'.join(f'{x[c]}'.replace('bowfree_admg', 'BF').upper() for c in problem_cols)

    data_to_plot['row_key'] = data_to_plot[problem_cols].apply(lambda x : problem_name_callback(x), axis=1)
    pic = sns.relplot(x='params.problem.number_of_variables', y=y_col + '_mean',
                      #style='Aggregation',
                      hue='Method',
                      #markers=True,
                      #col='params.problem.number_of_samples',
                      #col_wrap=2,
                      data=data_to_plot,
                      row='row_key',
                      kind='line',
                      height=1.4,   # Height of each subplot
                      aspect=1.2,
                      linewidth=0.8,
                      )
    pic.fig.subplots_adjust(hspace=0.01, wspace=0.01)
    for ax, (g_k, group_data) in zip(pic.axes.flat, data_to_plot.groupby(['row_key'], dropna=False)):
        print(g_k)
        row_index = pic.row_names.index(g_k[0])
        col_index = 0 #pic.col_names.index(g_k[1])
        print(f'plot_index({row_index}, {col_index}')
        print_solver_params(group_data, get_solver_columns_names(group_data) + ['Method'])
        ax = pic.axes[row_index, col_index]
        if y_lim is not None:
            ax.set_ylim(ymax=y_lim)
        ax_handles, ax_labels = pic.axes[0][0].get_legend_handles_labels()
        for (g_a, method_data) in group_data.groupby('Method', dropna=False):
            color = ax_handles[ax_labels.index(g_a)].get_color()
            print(g_a)
            method_data.sort_values(by='params.problem.number_of_variables', inplace=True)
            print(method_data.to_string())
            filler = ax.fill_between(
                method_data['params.problem.number_of_variables'],
                method_data[y_col + '_mean'] - method_data[y_col + '_std'],
                method_data[y_col + '_mean'] + method_data[y_col + '_std'],
                alpha=0.1,
                color=color,
                #label="Std Dev",
            )
            if plot_max:
                ax.plot(
                    method_data['params.problem.number_of_variables'],
                    method_data[y_col + '_max'],
                    linestyle='--',
                    color=color,
                    linewidth=0.5,
                    alpha=0.4,
                )
            if plot_min:
                ax.plot(
                    method_data['params.problem.number_of_variables'],
                    method_data[y_col + '_min'],
                    linestyle='dotted',
                    color=color,
                    linewidth=0.5,
                    alpha=0.4,
                )

    # Remove individual x and y axis labels
    for ax in pic.axes.flatten():
        ax.set_xlabel('')
        ax.set_ylabel('')

    # Add global x-axis label
    pic.figure.text(
        x=0.5,  # Centered horizontally
        y=0.02,  # Position near the bottom
        s="d (number of nodes)",
        ha='center',
        fontsize=font_size
    )

    # Add global y-axis label
    pic.figure.text(
        x=0.98,  # Position near the right edge
        y=0.5,  # Centered vertically
        s=label,
        ha='center',
        va='center',
        rotation=270,
        fontsize=font_size # 14
    )

    # Add row labels (y-axis labels for rows)
    for i, row_name in enumerate(pic.row_names):
        pic.axes[i, 0].annotate(
            text=row_name,
            xy=(-0.5, 0.5),  # Adjust position relative to the axis
            xycoords='axes fraction',
            ha='center',
            va='center',
            fontsize=font_size, # 12
            rotation=90
        )

    # Add column labels (x-axis labels for columns)
    for j, col_name in enumerate(pic.col_names):
        pic.axes[0, j].annotate(
            text=f'n={col_name}',
            xy=(0.5, 1.1),  # Adjust position relative to the axis
            xycoords='axes fraction',
            ha='center',
            va='center',
            fontsize=font_size
        )

    # for ax in pic.axes.flatten():
    #     for i, l in enumerate(ax.get_lines()):
    #         if i == 1 or i == 0:
    #             l.set_color('black')

    #pic.set_axis_labels('Number of variables', col_name)
    pic.set_titles('')
    #pic.set_titles(row_template="Row: {row_name}", col_template="Col: {col_name}")
    pic.set(xticks=list(range(min_number_vars, max_number_vars, 5)))

    figure = pic.figure
    handles, labels = pic.axes[0][0].get_legend_handles_labels()
    figure.legend(handles, labels, loc='lower center', ncol=len(handles), bbox_to_anchor=(0.5, -0.15)) # -.05) for 4 and rows
    figure.tight_layout(rect=(0.05, 0.05, 0.95, 0.95))
    pic._legend.remove()


    filepath = join(output_dir,f'{outputfile}_{file_suffix}.png')
    figure.savefig(filepath, bbox_inches='tight', dpi=300)
    plt.close(figure)
    if mlflow.active_run():
        mlflow.log_artifact(filepath)


