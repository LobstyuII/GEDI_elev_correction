import numpy as np
import pandas as pd
import os
from scipy.optimize import curve_fit


def gaussian_2d(data, x0, y0, sigma_x, sigma_y, A):
    x, y = data
    return A * (5 - np.exp(-(((x - x0) ** 2) / (2 * sigma_x ** 2) + ((y - y0) ** 2) / (2 * sigma_y ** 2))))

def fit_2d_inverted_gaussian(mean_elev_diff, init_center_x, init_center_y):
    try:
        x = np.linspace(-35, 35, mean_elev_diff.shape[0])
        y = np.linspace(-35, 35, mean_elev_diff.shape[1])
        X, Y = np.meshgrid(x, y)
        xdata = np.vstack((X.ravel(), Y.ravel()))
        zdata = mean_elev_diff.ravel()

        initial_guess = (init_center_x, init_center_y, 5.5, 5.5, np.max(mean_elev_diff))
        bounds = ([-35, -35, 1e-6, 1e-6, 0], [35, 35, np.inf, np.inf, np.inf])

        popt, _ = curve_fit(gaussian_2d, xdata, zdata, p0=initial_guess, bounds=bounds, maxfev=5000)

        x0, y0, sigma_x, sigma_y, A = popt
        fitted_data = gaussian_2d((X, Y), *popt).reshape(mean_elev_diff.shape)
        bias = gaussian_2d((np.array([x0]), np.array([y0])), *popt)[0]
        # 计算 RMSE
        residuals = mean_elev_diff - fitted_data
        minRMSE = np.sqrt(np.mean(residuals ** 2))
        return x0, y0, sigma_x, sigma_y, fitted_data, bias, minRMSE
    except Exception as e:
        print(f"Error in Gaussian fit: {e}")
        return None, None, None, None, None, None, None

def calculating_2d_gaussian():
    base_dir = 'GEDI_data'
    beam_prefixes = ['BEAM0000', 'BEAM0001', 'BEAM0010', 'BEAM0011', 'BEAM0101', 'BEAM0110', 'BEAM1000', 'BEAM1011']

    for root, dirs, files in os.walk(base_dir):
        for file in files:
            if any(file.startswith(f'abs_elev_diffs_{prefix}.npy') for prefix in beam_prefixes):
                file_path = os.path.join(root, file)
                elev_diffs = np.load(file_path)
                beam_name_npy = file.split('_')[3]
                beam_name = beam_name_npy.split('.')[0]
                if elev_diffs.size == 0:
                    print(f'No data available in {beam_name} of {file_path}.')
                    continue
                elev_diffs = np.array(elev_diffs)
                n = elev_diffs.shape[0]
                average_elevation = np.nanmean(elev_diffs, axis=0)
                min_pos = np.unravel_index(np.argmin(np.abs(average_elevation)), average_elevation.shape)
                init_x, init_y = -35 + min_pos[1] * (70 / average_elevation.shape[1]), -35 + min_pos[0] * (70 / average_elevation.shape[0])
                gaussianfit_x, gaussianfit_y, sigma_x, sigma_y, fitted_data, bias, minRMSE = fit_2d_inverted_gaussian(average_elevation, init_x, init_y)
                if gaussianfit_x is None:
                    print(f'Failed Gaussian fitting in {beam_name} of {file_path}.')
                    continue
                filename = os.path.join(root, f'abs_adjusted_elev_diffs_{beam_name}.npy')
                np.save(filename, fitted_data)

                result = {
                    'Label': beam_name,
                    'n': n,
                    'bias': bias,
                    'minRMSE': minRMSE,
                    'init_x': init_x,
                    'init_y': init_y,
                    'adjusted_x': gaussianfit_x,
                    'adjusted_y': gaussianfit_y,
                }

                results_filename = os.path.join(root, f'results_{beam_name}.csv')
                df = pd.DataFrame([result])
                df.to_csv(results_filename, index=False)
                print(f"Saved progress to {filename}")

    return 0
