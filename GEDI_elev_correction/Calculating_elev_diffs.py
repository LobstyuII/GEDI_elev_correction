import numpy as np
from geopy.distance import geodesic
import ee
import pandas as pd
from datetime import datetime
import rasterio
import pyproj
import os
from concurrent.futures import ThreadPoolExecutor
from scipy.ndimage import gaussian_filter


def GEE_authorizing():
    # Initialize Google Earth Engine with a service account.
    service_account = "lobstyu@premium-cipher-424203-d0.iam.gserviceaccount.com"
    credentials = ee.ServiceAccountCredentials(service_account, 'GEDI_elev_correction\\premium-cipher-424203-d0-c6894a29d00c.json')
    ee.Initialize(credentials)

    return 0

def get_matrix_elev_diff(center_lat, center_lon, elev_GEDI, tan_direction, spacing=1, extent=35, buffer_extent=10):
    half_extent = extent
    x = np.arange(-half_extent - buffer_extent, half_extent + spacing + buffer_extent, spacing)
    y = np.arange(-half_extent - buffer_extent, half_extent + spacing + buffer_extent, spacing)
    xx, yy = np.meshgrid(x, y)

    angle = np.arctan(tan_direction)
    cos_angle = np.cos(angle)
    sin_angle = np.sin(angle)

    # Calculate rotation in the UTM coordinate system
    x_rot = xx * cos_angle - yy * sin_angle
    y_rot = xx * sin_angle + yy * cos_angle

    # Convert UTM displacement to WGS-84 lat/lon
    points_lat = np.zeros_like(xx, dtype=float)
    points_lon = np.zeros_like(yy, dtype=float)

    for i in range(xx.shape[0]):
        for j in range(xx.shape[1]):
            displacement = (
            y_rot[i, j], x_rot[i, j])  # Note the order: (latitude displacement, longitude displacement)
            origin = (center_lat, center_lon)
            destination = geodesic(meters=displacement[0]).destination(origin, 0)
            destination = geodesic(meters=displacement[1]).destination(destination, 90)
            points_lat[i, j] = destination.latitude
            points_lon[i, j] = destination.longitude

    # Split points into batches for parallel processing
    num_points = points_lat.size
    indices = np.arange(num_points)
    batches = np.array_split(indices, 8)

    def fetch_elevations(batch):
        try:
            latitudes = points_lat.flatten()[batch].reshape(-1, 1)
            longitudes = points_lon.flatten()[batch].reshape(-1, 1)
            points = ee.FeatureCollection([ee.Feature(ee.Geometry.Point([lon, lat])) for lat, lon in zip(latitudes.flatten(), longitudes.flatten())])

            # Define the 3DEP dataset
            dataset = ee.ImageCollection("USGS/3DEP/1m")
            image = dataset.mosaic()

            # Get the elevation at the points
            elevations = image.reduceRegions(
                collection=points,
                reducer=ee.Reducer.first(),
                scale=1  # Use 1 meter scale since 3DEP data is at 1m resolution
            )

            # Extract the results
            elevation_values = []
            for feature in elevations.getInfo().get('features', []):
                value = feature.get('properties', {}).get('first')
                if value is None:
                    return None

                elevation_values.append(value)
            return elevation_values

        except Exception as e:
            print(f"Error fetching elevation data: {e}")
            return None

    with ThreadPoolExecutor(max_workers=8) as executor:
        futures = [executor.submit(fetch_elevations, batch) for batch in batches]
        results = [f.result() for f in futures]

    if any(result is None for result in results):
        return None

    elevation_values = [val for result in results for val in result]

    # Reshape to 71x71 matrix
    elevation_matrix = np.array(elevation_values).reshape(points_lat.shape)

    # Apply 2D Gaussian filter to smooth the elevation matrix
    smoothed_elevation_matrix = gaussian_filter(elevation_matrix, sigma=5.5)
    elev_3DEP = smoothed_elevation_matrix[10:81, 10:81]

    elev_diff = elev_GEDI - elev_3DEP
    if np.any(np.abs(elev_diff) > 15):
        return None

    return elev_diff

def load_geoid(geoid_file):
    """加载GEOID12B数据并获取其属性"""
    with rasterio.open(geoid_file) as src:
        geoid_data = src.read(1)
        transform = src.transform
        crs = src.crs
    return geoid_data, transform, crs


def get_geoid_height(lat, lon, geoid_data, transform, geoid_crs):
    """根据经纬度获取大地水准面高度"""
    wgs84 = pyproj.CRS("EPSG:4326")
    transformer = pyproj.Transformer.from_crs(wgs84, geoid_crs, always_xy=True)
    lon = lon + 360 if lon < 0 else lon
    x, y = transformer.transform(lon, lat)
    col, row = ~transform * (x, y)
    row, col = int(row), int(col)
    if 0 <= row < geoid_data.shape[0] and 0 <= col < geoid_data.shape[1]:
        return geoid_data[row, col]
    else:
        return None


def calculating_elev_diffs():
    GEE_authorizing()

    geoid_file = 'g2012bu0.bin'
    geoid_data, transform, geoid_crs = load_geoid(geoid_file)

    base_dir = 'GEDI_data'
    beam_prefixes = ['BEAM0000', 'BEAM0001', 'BEAM0010', 'BEAM0011', 'BEAM0101', 'BEAM0110', 'BEAM1000', 'BEAM1011']
    # beam_prefixes = ['BEAM0001', 'BEAM0010', 'BEAM0011', 'BEAM0101', 'BEAM0110', 'BEAM1000', 'BEAM1011']
    # beam_prefixes = ['BEAM0000']
    for root, dirs, files in os.walk(base_dir):
        for file in files:
            if any(file.startswith(prefix) and file.endswith('Filtered_data.csv') for prefix in beam_prefixes):
                file_path = os.path.join(root, file)
                beam_name = file.split('_')[0]
                elev_diffs_filename = os.path.join(root, f'elev_diffs_{beam_name}.npy')
                abs_elev_diffs_filename = os.path.join(root, f'abs_elev_diffs_{beam_name}.npy')

                if os.path.exists(elev_diffs_filename) and os.path.exists(abs_elev_diffs_filename):
                    print(
                        f"Files {elev_diffs_filename} and {abs_elev_diffs_filename} already exist. Skipping computation.")
                    continue
                beam_data = pd.read_csv(file_path)
                start_time = datetime.now()
                print("start_time:", start_time)
                valid_footprints = 0
                invalid_footprints = 0
                elev_diffs = []
                abs_elev_diffs = []

                for idx, row in beam_data.iterrows():
                    if (valid_footprints + invalid_footprints) % 10 == 0:
                        print(
                            f'{valid_footprints + invalid_footprints} of {len(beam_data)} footprints were converted in {beam_name} at {datetime.now()}')
                        print(f'valid_footprints: {valid_footprints}; invalid_footprints: {invalid_footprints} ')

                    center_lat, center_lon, wgs84_elev_GEDI, tan_direction = row['Latitude'], row['Longitude'], row[
                        'Elevation'], row['Smoothed_Tan']
                    geoid_height = get_geoid_height(center_lat, center_lon, geoid_data, transform, geoid_crs)
                    if geoid_height is not None:
                        elev_GEDI = wgs84_elev_GEDI - geoid_height
                    else:
                        invalid_footprints += 1
                        continue
                    elev_diff = get_matrix_elev_diff(center_lat, center_lon, elev_GEDI, tan_direction)
                    if elev_diff is None:
                        invalid_footprints += 1
                        continue
                    valid_footprints += 1
                    # 此处有异议
                    abs_elev_diff = np.abs(elev_diff)
                    elev_diffs.append(elev_diff)
                    abs_elev_diffs.append(abs_elev_diff)

                # 转换 elev_diffs 为三维数组
                elev_diffs = np.array(elev_diffs)
                abs_elev_diffs = np.array(abs_elev_diffs)

                filename = os.path.join(root, f'elev_diffs_{beam_name}.npy')
                np.save(filename, elev_diffs)
                filename = os.path.join(root, f'abs_elev_diffs_{beam_name}.npy')
                np.save(filename, abs_elev_diffs)
                end_time = datetime.now()
                runningtime = end_time - start_time

                print(f"file_path:{file_path}")
                print(f"Saved elev_diffs to {filename} in {runningtime} at {end_time}")
                del beam_data, elev_diffs, abs_elev_diffs
                # gc.collect()

    return 0