import h5py
import numpy as np
import ee
import os
import pandas as pd
import time


def get_center_data(file_path, beams):
    data = {}
    for beam in beams:
        with h5py.File(file_path, 'r') as file:
            lat = np.array(file[f'/{beam}/lat_lowestmode'])
            lon = np.array(file[f'/{beam}/lon_lowestmode'])
            elev = np.array(file[f'/{beam}/elev_lowestmode'])
            surface_flag = np.array(file[f'/{beam}/surface_flag'])

        dlat = np.diff(lat)
        dlon = np.diff(lon)
        instantaneous_tan = np.arctan2(dlat, dlon)
        instantaneous_tan = np.pad(instantaneous_tan, (0, 1), mode='edge')
        smoothed_tan = np.convolve(instantaneous_tan, np.ones(11) / 11, mode='same')
        smoothed_tan[:5] = instantaneous_tan[:5]
        smoothed_tan[-5:] = instantaneous_tan[-5:]

        # data in range of GEOIDL2B
        mask = (lat >= 24) & (lat <= 58) & (lon >= -130) & (lon <= -60) & (surface_flag == 1)
        ranged_data = np.stack((lat[mask], lon[mask], elev[mask], instantaneous_tan[mask], smoothed_tan[mask]),
                               axis=-1)

        data[beam] = ranged_data

    return data


def GEE_authorizing():
    # Initialize Google Earth Engine
    service_account = "lobstyu@premium-cipher-424203-d0.iam.gserviceaccount.com"
    credentials = ee.ServiceAccountCredentials(service_account, 'GEDI_elev_correction\\premium-cipher-424203-d0-c6894a29d00c.json')
    ee.Initialize(credentials)
    return 0

def get_center_LC_batch(latitudes, longitudes, batch_size=500):
    try:
        # 计算点的估计大小，并调整 batch_size 以接近 10MB 限制
        estimated_point_size = 200  # 每个点大约 200 字节
        max_batch_size = 10485760 // estimated_point_size  # 计算最大 batch size

        batch_size = min(batch_size, max_batch_size)  # 确保 batch_size 不超过最大限制

        land_cover_values = []
        total_points = len(latitudes)

        for start in range(0, total_points, batch_size):
            end = min(start + batch_size, total_points)
            batch_lat = latitudes[start:end]
            batch_lon = longitudes[start:end]

            start_time = time.time()

            # Create a FeatureCollection of points
            points = ee.FeatureCollection(
                [ee.Feature(ee.Geometry.Point([lon, lat])) for lat, lon in zip(batch_lat, batch_lon)])

            # Landcover dataset
            dataset = ee.ImageCollection("ESA/WorldCover/v100")
            image = dataset.first()

            land_cover = image.reduceRegions(
                collection=points,
                reducer=ee.Reducer.first(),
                scale=10
            )

            batch_land_cover_values = []
            for feature in land_cover.getInfo().get('features', []):

                value = feature.get('properties', {}).get('first', -999)
                batch_land_cover_values.append(value)

            land_cover_values.extend(batch_land_cover_values)

            end_time = time.time()
            progress = (end / total_points) * 100
            print(f"Batch {start // batch_size + 1}: API request took {end_time - start_time:.2f} seconds, Progress: {progress:.2f}%")

        return land_cover_values
    except Exception as e:
        print(f"Error fetching land cover: {e}")
        return [-999] * len(latitudes)
    return 0

def LC_selection(df, output_folder, beam, typeID):

    filtered_df = df[(df['Land_Cover'] == typeID)]

    # 保存筛选后的数据到新的CSV文件
    filtered_csv_file_path = os.path.join(output_folder, f"{beam}_Filtered_data.csv")
    filtered_df.to_csv(filtered_csv_file_path, index=False)

    return 0

def extracting_GEDI_data():
    directory_path = 'GEDI_data'
    beams = ['BEAM0000', 'BEAM0001', 'BEAM0010', 'BEAM0011', 'BEAM0101', 'BEAM0110', 'BEAM1000', 'BEAM1011']

    GEE_authorizing()

    for file_name in os.listdir(directory_path):
        if file_name.endswith('.h5'):
            file_path = os.path.join(directory_path, file_name)
            data_GEDI = get_center_data(file_path, beams)

            output_folder = os.path.join(directory_path, os.path.splitext(file_name)[0])
            os.makedirs(output_folder, exist_ok=True)

            for beam, ranged_data in data_GEDI.items():
                latitudes = ranged_data[:, 0]
                longitudes = ranged_data[:, 1]
                land_cover = get_center_LC_batch(latitudes, longitudes)

                # Landcover
                ranged_data_with_lc = np.column_stack((ranged_data, land_cover))
                data_GEDI[beam] = ranged_data_with_lc

                # save csv file
                df = pd.DataFrame(ranged_data_with_lc,
                                  columns=['Latitude', 'Longitude', 'Elevation', 'Instantaneous_Tan', 'Smoothed_Tan',
                                           'Land_Cover'])
                csv_file_path = os.path.join(output_folder, f"{beam}.csv")
                df.to_csv(csv_file_path, index=False)

                # typeID: 50-impervious，60-barren https://developers.google.com/earth-engine/datasets/catalog/ESA_WorldCover_v100
                LC_selection(df, output_folder, beam, 60)

                print(f"file_path:{file_path}")
                print(f"Saved elev_diffs to {csv_file_path}")
    return 0


