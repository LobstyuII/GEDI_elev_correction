import os
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from mpl_toolkits.axes_grid1 import make_axes_locatable


def plot_contours(beams, geomatrix_path_beam, results_path_beam, output_path):
    fig, axes = plt.subplots(2, 4, figsize=(18, 10))
    axes = axes.flatten()
    Label = []
    n = []
    bias = []
    minRMSE = []
    init_x = []
    init_y = []
    adjusted_x = []
    adjusted_y = []

    for i, beam in enumerate(beams):
        geomatrix_path = geomatrix_path_beam.replace("beamname", beam)
        if not os.path.exists(geomatrix_path):
            print(f"File not found: {geomatrix_path}, skipping this beam.")
            return 0
        gaussian_elev_diff = np.load(geomatrix_path)
        # gaussian_elev_diff = np.nanmean(gaussian_elev_diff, axis=0)

        results_path = results_path_beam.replace("beamname", beam)
        if not os.path.exists(results_path):
            print(f"File not found: {results_path}, skipping this beam.")
            return 0
        results = pd.read_csv(results_path)
        Label.append(results['Label'][0])
        n.append(results['n'][0])
        bias.append(results['bias'][0])
        minRMSE.append(results['minRMSE'][0])
        init_x.append(results['init_x'][0])
        init_y.append(results['init_y'][0])
        adjusted_x.append(results['adjusted_x'][0])
        adjusted_y.append(results['adjusted_y'][0])

        X, Y = np.meshgrid(np.linspace(-35, 35, gaussian_elev_diff.shape[1]), np.linspace(-35, 35, gaussian_elev_diff.shape[0]))
        cs = axes[i].contourf(X, Y, gaussian_elev_diff, levels=np.linspace(np.min(gaussian_elev_diff), np.max(gaussian_elev_diff), 100), cmap='viridis_r')
        axes[i].contour(X, Y, gaussian_elev_diff, levels=7, colors='black', linewidths=0.3)

        axes[i].set_xticks(np.arange(-30, 31, 10))
        axes[i].set_yticks(np.arange(-30, 31, 10))

        # crosshairs#1
        axes[i].plot([init_x[i], init_x[i]], [-35, 35], color='saddlebrown', linewidth=0.1)
        axes[i].plot([-35, 35], [init_y[i], init_y[i]], color='saddlebrown', linewidth=0.1)

        # crosshairs#2
        axes[i].plot([adjusted_x[i], adjusted_x[i]], [-35, 35], 'r--')
        axes[i].plot([-35, 35], [adjusted_y[i], adjusted_y[i]], 'r--')

        # height(colorbar)
        divider = make_axes_locatable(axes[i])
        cax = divider.append_axes("right", size="5%", pad=0.1)  # 增加pad以避免重叠
        cbar = fig.colorbar(cs, cax=cax)
        cbar.set_label('Elevation difference (m)')
        cbar.ax.yaxis.set_major_formatter(plt.FuncFormatter(lambda x, _: f'{x:.1f}'))

    # subgraphs shape
    for i, ax in enumerate(axes):
        ax.set_aspect('equal', adjustable='box')
        ax.set_title(
            f"{Label[i]}: n={n[i]}, bias={bias[i]:.2f}, minRMSE={minRMSE[i]:.2f}\ninit x: {init_x[i]:.0f} y: {init_y[i]:.0f}; adjusted x: {adjusted_x[i]:.1f} y: {adjusted_y[i]:.1f}",
            fontsize = 10
        )

    # subgraphs interval
    plt.subplots_adjust(left=0.05, right=0.95, top=0.95, bottom=0.05, wspace=0.3, hspace=0.3)

    # Save the plot
    output_file = os.path.join(output_path, 'bulleyes_' + os.path.basename(os.path.dirname(geomatrix_path_beam)) + '.png')
    plt.savefig(output_file, dpi=300)
    # plt.show()

def plot_bullseye():

    # Path to the GEDI_data directory
    base_dir = 'GEDI_data'
    output_dir = 'figures'
    os.makedirs(output_dir, exist_ok=True)

    # List of subdirectories under GEDI_data
    directories = [os.path.join(base_dir, d) for d in os.listdir(base_dir) if os.path.isdir(os.path.join(base_dir, d))]

    beams = ['BEAM0000', 'BEAM0001', 'BEAM0010', 'BEAM0011', 'BEAM0101', 'BEAM0110', 'BEAM1000', 'BEAM1011']

    # Process each directory
    for dir_path in directories:
        geomatrix_path = os.path.join(dir_path, 'abs_adjusted_elev_diffs_beamname.npy')
        results_path = os.path.join(dir_path, 'results_beamname.csv')
        if not (os.path.exists(geomatrix_path.replace('beamname', beams[0])) and os.path.exists(results_path.replace('beamname', beams[0]))):
            print(f"Data not complete in {dir_path}, skipping this directory.")
            continue
        plot_contours(beams, geomatrix_path, results_path, output_dir)

    return 0