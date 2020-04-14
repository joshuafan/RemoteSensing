import math
import matplotlib.pyplot as plt
import numpy as np
import os
import pandas as pd
import xarray as xr
from sklearn.metrics import mean_squared_error, r2_score
from scipy.stats import pearsonr
from numpy import poly1d

from sif_utils import plot_histogram

# Taken from https://stackoverflow.com/questions/11159436/multiple-figures-in-a-single-window
def plot_figures(output_file, figures, nrows = 1, ncols=1):
    """Plot a dictionary of figures.

    Parameters
    ----------
    figures : <title, figure> dictionary
    ncols : number of columns of subplots wanted in the display
    nrows : number of rows of subplots wanted in the figure
    """
    #fig = plt.figure(figsize=(8, 20))
    fig, axeslist = plt.subplots(ncols=ncols, nrows=nrows, figsize=(20, 20))
    for ind,title in enumerate(figures):
        axeslist.ravel()[ind].imshow(figures[title])  #, cmap=plt.gray())
        axeslist.ravel()[ind].set_title(title)
        axeslist.ravel()[ind].set_axis_off()
    plt.tight_layout() # optional
    plt.savefig(output_file)
    plt.close()

def plot_images(image_rows, image_filename_column, output_file):
    images = {}
    for idx, image_row in image_rows.iterrows():
        subtile = np.load(image_row[image_filename_column]).transpose((1, 2, 0))
        title = 'Lat' + str(round(image_row['lat'], 6)) + ', Lon' + str(round(image_row['lon'], 6)) + ' (SIF = ' + str(round(image_row['SIF'], 3)) + ')'
        images[title] = subtile[:, :, RGB_BANDS] / 1000
    plot_figures(output_file, images, nrows=math.ceil(len(images) / 5), ncols=5)
 

DATA_DIR = "/mnt/beegfs/bulk/mirror/jyf6/datasets"
BAND_STATISTICS_FILE = os.path.join(DATA_DIR, "dataset_2018-08-01/band_statistics_train.csv")
TILES_DIR = os.path.join(DATA_DIR, "tiles_2016-08-01")
LAT_LON = 'lat_47.55_lon_-101.35'
IMAGE_FILE = os.path.join(TILES_DIR, "reflectance_" + LAT_LON + ".npy")
CFIS_SIF_FILE = os.path.join(DATA_DIR, "CFIS/CFIS_201608a_300m.npy")
TROPOMI_SIF_FILE = os.path.join(DATA_DIR, "TROPOMI_SIF/TROPO-SIF_01deg_biweekly_Apr18-Jan20.nc")
TROPOMI_DATE_RANGE = slice("2018-08-01", "2018-08-16")
EVAL_SUBTILE_DATASET = os.path.join(DATA_DIR, "dataset_2016-08-01/eval_subtiles.csv")
TRAIN_TILE_DATASET = os.path.join(DATA_DIR, "dataset_2018-08-01/tile_info_train.csv")
ALL_TILE_DATASET = os.path.join(DATA_DIR, "dataset_2018-08-01/reflectance_cover_to_sif.csv")
RGB_BANDS = [3, 2, 1]

# Display tiles with largest/smallest TROPOMI SIFs
train_metadata = pd.read_csv(TRAIN_TILE_DATASET)
highest_tropomi_sifs = train_metadata.nlargest(25, 'SIF')
plot_images(highest_tropomi_sifs, 'tile_file', 'exploratory_plots/tropomi_sif_high_subtiles.png')
lowest_tropomi_sifs = train_metadata.nsmallest(25, 'SIF')
plot_images(lowest_tropomi_sifs, 'tile_file', 'exploratory_plots/tropomi_sif_low_subtiles.png')
all_metadata = pd.read_csv(ALL_TILE_DATASET)

# Display tiles with largest/smallest CFIS SIFs
eval_metadata = pd.read_csv(EVAL_SUBTILE_DATASET)
highest_cfis_sifs = eval_metadata.nlargest(25, 'SIF')
plot_images(highest_cfis_sifs, 'subtile_file', 'exploratory_plots/cfis_sif_high_subtiles.png')
lowest_cfis_sifs = eval_metadata.nsmallest(25, 'SIF')
plot_images(lowest_cfis_sifs, 'subtile_file', 'exploratory_plots/cfis_sif_low_subtiles.png')

# Open CFIS SIF evaluation dataset
all_cfis_points = np.load(CFIS_SIF_FILE)
print("CFIS points total", all_cfis_points.shape[0])
print('CFIS points with reflectance data', len(eval_metadata))

# Open TROPOMI SIF dataset
tropomi_dataset = xr.open_dataset(TROPOMI_SIF_FILE)
tropomi_array = tropomi_dataset.sif_dc.sel(time=TROPOMI_DATE_RANGE).mean(dim='time')

# For each CFIS SIF point, find TROPOMI SIF of surrounding tile
tropomi_sifs = []  # TROPOMI SIF corresponding to each CFIS point
for i in range(len(eval_metadata)):  # range(cfis_points.shape[0]):
    lon = eval_metadata['lon'][i]  # cfis_points[i, 1]
    lat = eval_metadata['lat'][i]  # cfis_points[i, 2]
    tropomi_sif = tropomi_array.sel(lat=lat, lon=lon, method='nearest')
    tropomi_sifs.append(tropomi_sif)

# Plot histogram of CFIS and TROPOMI SIFs
plot_histogram(np.array(all_cfis_points[:, 0]), "sif_distribution_cfis_all.png")
plot_histogram(np.array(eval_metadata['SIF']), "sif_distribution_cfis_filtered.png") #  cfis_points[:, 0])
plot_histogram(np.array(tropomi_sifs), "sif_distribution_tropomi_eval_area.png")
plot_histogram(np.array(train_metadata['SIF']), "sif_distribution_tropomi_train.png")
plot_histogram(np.array(all_metadata['SIF']), "sif_distribution_tropomi_all.png")

# sif_mean = np.mean(train_metadata['SIF'])
train_statistics = pd.read_csv(BAND_STATISTICS_FILE)
sif_mean = train_statistics['mean'].values[-1]
print('SIF mean (TROPOMI, train set)', sif_mean)

# Scatterplot of CFIS points (all)
green_cmap = plt.get_cmap('Greens')
plt.scatter(all_cfis_points[:, 1], all_cfis_points[:, 2], c=all_cfis_points[:, 0], cmap=green_cmap)
plt.xlabel('Longitude')
plt.ylabel('Latitude')
plt.title('CFIS points (all)')
plt.savefig('exploratory_plots/cfis_points_all.png')
plt.close()

# Scatterplot of CFIS points (eval)
green_cmap = plt.get_cmap('Greens')
plt.scatter(eval_metadata['lon'], eval_metadata['lat'], c=eval_metadata['SIF'], cmap=green_cmap)
plt.xlabel('Longitude')
plt.ylabel('Latitude')
plt.title('CFIS points (reflectance data available, eval set)')
plt.savefig('exploratory_plots/cfis_points_filtered.png')
plt.close()

# Plot TROPOMI vs SIF (and linear regression)
x = eval_metadata['SIF']  # cfis_points[:, 0]
y = tropomi_sifs
coef = np.polyfit(x, y, 1)
print('Linear regression: x=CFIS, y=TROPOMI', coef)
poly1d_fn = np.poly1d(coef) 
plt.plot(x, y, 'bo', x, poly1d_fn(x), '--k')
plt.xlabel('CFIS SIF (small tile, 2016)')
plt.ylabel('TROPOMI SIF (surrounding large tile, 2018)')
plt.title('TROPOMI vs CFIS SIF')
plt.savefig('exploratory_plots/TROPOMI_vs_CFIS_SIF')
plt.close()

# Calculate NRMSE and correlation
nrmse = math.sqrt(mean_squared_error(y, x)) / sif_mean
corr, _ = pearsonr(y, x)
print('NRMSE', round(nrmse, 3))
print('Correlation', round(corr, 3))

# Show example tiles (RGB)
array = np.load(IMAGE_FILE).transpose((1, 2, 0))
print('Array shape', array.shape)
plt.imshow(array[:, :, RGB_BANDS] / 1000)
plt.savefig("exploratory_plots/dataset_rgb_2016.png")
plt.close()

fig, axeslist = plt.subplots(ncols=5, nrows=6, figsize=(20, 24))
for band in range(0, 29):
    layer = array[:, :, band]
    axeslist.ravel()[band].imshow(layer, cmap='Greens', vmin=np.min(layer), vmax=np.max(layer))
    axeslist.ravel()[band].set_title('Band ' + str(band))
    axeslist.ravel()[band].set_axis_off()
plt.tight_layout() # optional
plt.savefig('exploratory_plots/dataset_' + LAT_LON +'.png')
plt.close()

