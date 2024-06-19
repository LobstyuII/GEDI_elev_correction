import os
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from datetime import datetime, timedelta

def julian_to_gregorian(year, julian_day, hhmmss):
    base_date = datetime(year=year, month=1, day=1) + timedelta(days=(julian_day - 1))
    hours = int(hhmmss[:2])
    minutes = int(hhmmss[2:4])
    seconds = int(hhmmss[4:6])
    return base_date + timedelta(hours=hours, minutes=minutes, seconds=seconds)

def extract_date_from_path(dir_name):
    try:
        year = int(dir_name[9:13])
        julian_day = int(dir_name[13:16])
        hhmmss = dir_name[16:22]
        return julian_to_gregorian(year, julian_day, hhmmss)
    except ValueError:
        raise ValueError(f"Invalid date format in directory name: {dir_name}")

def load_and_process_data(base_dir, beams):
    all_data = []
    all_dates = []

    directories = [os.path.join(base_dir, d) for d in os.listdir(base_dir) if os.path.isdir(os.path.join(base_dir, d))]

    for dir_path in directories:
        dir_name = os.path.basename(dir_path)

        try:
            date = extract_date_from_path(dir_name)
        except ValueError as e:
            print(e)
            continue

        cross_track = []
        along_track = []

        for beam in beams:
            results_file = os.path.join(dir_path, f'results_{beam}.csv')
            if not os.path.exists(results_file):
                print(f"Results file not found: {results_file}, skipping this beam.")
                break

            results = pd.read_csv(results_file)
            cross_track.append(results['adjusted_x'][0])
            along_track.append(results['adjusted_y'][0])
        else:
            all_data.append((date, cross_track, along_track))
            all_dates.append(date)

    return pd.DataFrame(all_data, columns=['Date', 'CrossTrack', 'AlongTrack']).set_index('Date')

def plot_data(df, beams, output_file):
    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(15, 10), sharex=True)

    for i, beam in enumerate(beams):
        color = f'C{i}'
        ax1.plot(df.index, df['CrossTrack'].apply(lambda x: x[i]), marker='o', linestyle='None', label=beam, color=color)
        ax1.plot(df.index, df['CrossTrack'].apply(lambda x: x[i]), linestyle='--', color=color)
    ax1.axhline(0, color='black', linestyle='--')
    ax1.set_ylabel('Cross-track offset (m)')
    ax1.legend()

    for i, beam in enumerate(beams):
        color = f'C{i}'
        ax2.plot(df.index, df['AlongTrack'].apply(lambda x: x[i]), marker='o', linestyle='None', label=beam, color=color)
        ax2.plot(df.index, df['AlongTrack'].apply(lambda x: x[i]), linestyle='--', color=color)
    ax2.axhline(0, color='black', linestyle='--')
    ax2.set_ylabel('Along-track offset (m)')
    ax2.legend()

    ax1.set_yticks(np.arange(-30, 31, 10))
    ax2.set_yticks(np.arange(-30, 31, 10))

    plt.xlabel('Date')
    plt.suptitle('GEDI geolocation offsets: mission week 19 to 90 (Release 1)')

    dates = df.index
    unique_days = pd.to_datetime(dates.date).unique()
    ticks = [datetime.combine(day, datetime.min.time()) + timedelta(hours=12) for day in unique_days]
    ax2.set_xticks(ticks)
    ax2.set_xticklabels([day.strftime('%Y-%m-%d') for day in unique_days], rotation=45)

    ax1.grid(False)
    ax2.grid(False)

    plt.savefig(output_file, dpi=300)
    plt.show()

def plot_timeseries():
    base_dir = 'GEDI_data'
    output_dir = 'figures'
    os.makedirs(output_dir, exist_ok=True)

    beams_group1 = ['BEAM0000', 'BEAM0001', 'BEAM0010', 'BEAM0011']
    beams_group2 = ['BEAM0101', 'BEAM0110', 'BEAM1000', 'BEAM1011']

    df_group1 = load_and_process_data(base_dir, beams_group1)
    df_group2 = load_and_process_data(base_dir, beams_group2)

    if not df_group1.empty:
        plot_data(df_group1, beams_group1, os.path.join(output_dir, 'GEDI_geolocation_offsets_group1.png'))
    else:
        print("No valid data found for group 1.")

    if not df_group2.empty:
        plot_data(df_group2, beams_group2, os.path.join(output_dir, 'GEDI_geolocation_offsets_group2.png'))
    else:
        print("No valid data found for group 2.")

plot_timeseries()
