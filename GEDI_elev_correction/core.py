from GEDI_elev_correction import Load_GEDI_L2A_files, Calculating_elev_diffs, Calculating_2D_Gaussian
from GEDI_elev_correction import plot_bullseye, plot_timeseries


def run_part1():
    Load_GEDI_L2A_files.extracting_GEDI_data()
    return 0


def run_part2():
    Calculating_elev_diffs.calculating_elev_diffs()
    return 0


def run_part3():
    Calculating_2D_Gaussian.calculating_2d_gaussian()
    return 0

def run_part4():
    plot_bullseye.plot_bullseye()
    plot_timeseries.plot_timeseries()
    return 0