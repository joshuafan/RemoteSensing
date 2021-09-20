import csv
import math
import matplotlib.pyplot as plt
from matplotlib import path
from matplotlib.patches import Circle, Wedge, Polygon
from matplotlib.collections import PatchCollection
import numpy as np
import os
import xarray as xr
from sif_utils import plot_histogram, lat_long_to_index
import sif_utils

DATA_DIR = "/mnt/beegfs/bulk/mirror/jyf6/datasets"
#OCO2_FILE = os.path.join(DATA_DIR, "OCO2/oco2_20180801_20180816_1800m.nc")
#OCO2_FILE = os.path.join(DATA_DIR, "OCO2/oco2_20180801_20180816_3km.nc")
# OCO2_FILE = os.path.join(DATA_DIR, "OCO2/oco2_20180708_20180915_14day_3km.nc")
OCO2_FILE = os.path.join(DATA_DIR, "OCO2/oco2_20180429_20180916_3km.nc")
#DATE = "2018-08-01" #"2016-07-16"
# TILES_DIR = os.path.join(DATA_DIR, "tiles_" + DATE)
# DATASET_DIR = os.path.join(DATA_DIR, "dataset_" + DATE)
#OCO2_SUBTILES_DIR = os.path.join(DATA_DIR, "oco2_subtiles_" + DATE)  # Directory to output subtiles to
#OUTPUT_CSV_FILE = os.path.join(DATASET_DIR, "oco2_eval_subtiles.csv")
OUTPUT_CSV_FILENAME = "oco2_eval_subtiles.csv"
# if not os.path.exists(OCO2_SUBTILES_DIR):
#     os.makedirs(OCO2_SUBTILES_DIR)
DATES = ["2018-04-29", "2018-05-13", "2018-05-27", "2018-06-10", "2018-06-24", "2018-07-08",
         "2018-07-22", "2018-08-05", "2018-08-19", "2018-09-02", "2018-09-16"]

COLUMN_NAMES = ["lon", "lat", "date",
                     "tile_file", 'ref_1', 'ref_2', 'ref_3', 'ref_4', 'ref_5', 'ref_6', 'ref_7',
                    'ref_10', 'ref_11', 'Rainf_f_tavg', 'SWdown_f_tavg', 'Tair_f_tavg', 
                    'grassland_pasture', 'corn', 'soybean', 'shrubland',
                    'deciduous_forest', 'evergreen_forest', 'spring_wheat', 'developed_open_space',
                    'other_hay_non_alfalfa', 'winter_wheat', 'herbaceous_wetlands',
                    'woody_wetlands', 'open_water', 'alfalfa', 'fallow_idle_cropland',
                    'sorghum', 'developed_low_intensity', 'barren', 'durum_wheat',
                    'canola', 'sunflower', 'dry_beans', 'developed_med_intensity',
                    'millet', 'sugarbeets', 'oats', 'mixed_forest', 'peas', 'barley',
                    'lentils', 'missing_reflectance', "SIF", "num_soundings"]



# For plotting
point_lons = []
point_lats = []
point_sifs = []

# Parameters
RES = (0.00026949458523585647, 0.00026949458523585647)
LARGE_TILE_PIXELS = 371
OCO2_TILE_PIXELS = 100
OCO2_TILE_DEGREES = RES[0] * OCO2_TILE_PIXELS
MAX_FRACTION_MISSING_OVERALL = 0.1
PURE_THRESHOLD = 0.5
MIN_SIF = 0.2
MIN_NUM_SOUNDINGS = 5
INPUT_CHANNELS = 43
REFLECTANCE_BANDS = list(range(0, 9))
MISSING_REFLECTANCE_IDX = -1

pure_corn_points = 0
pure_soy_points = 0
missing_points = 0

# Open dataset and print
dataset = xr.open_dataset(OCO2_FILE)
print(dataset)

times = dataset.time.values
lons = dataset.lon.values
lats = dataset.lat.values
sifs = dataset.dcSIF.values
num_soundings = dataset.n.values

plot_histogram(sifs, "sif_distribution_oco2_all.png", title="OCO2 SIF distribution (longitude: -108 to -82, latitude: 38 to 48.7)")
print('Times', times.shape)
print('Lons', lons.shape)
print('Lats', lats.shape)
print('Sifs', sifs.shape)

num_soundings_dist = num_soundings.flatten()
num_soundings_dist = num_soundings_dist[~np.isnan(num_soundings_dist)]
num_soundings_dist = num_soundings_dist[num_soundings_dist > 0]
plot_histogram(num_soundings_dist, "oco2_num_soundings.png", title="OCO2 num soundings")


# Loop through all OCO-2 data points
# Loop through all time ranges
datapoints = 0
for time_idx in range(len(times)):
    date_time = times[time_idx]
    DATE = np.datetime_as_string(date_time, unit='D')
    if DATE not in DATES:
        continue
    print('Date', DATE)
    TILES_DIR = os.path.join(DATA_DIR, "tiles_" + DATE)
    DATASET_DIR = os.path.join(DATA_DIR, "dataset_" + DATE)  
    OCO2_SUBTILES_DIR = os.path.join(DATA_DIR, "oco2_subtiles_" + DATE)

    # Make directory for OCO2 subtiles, if it does not exist
    if not os.path.exists(OCO2_SUBTILES_DIR):
        os.makedirs(OCO2_SUBTILES_DIR)
    
    # Initialize this time period's dataset of OCO2 values
    dataset_rows = []
    dataset_rows.append(COLUMN_NAMES)

    # Loop through all lat/lon
    for lon_idx in range(len(lons)):
        for lat_idx in range(len(lats)):
            lon = lons[lon_idx]
            lat = lats[lat_idx]
            sif = sifs[lat_idx, lon_idx, time_idx]
            num_soundings_point = num_soundings[lat_idx, lon_idx, time_idx]

            # Ignore grid squares where there is no data
            if math.isnan(sif):
                continue

            # From region indices, compute lat/lon bounds on this tile
            tile_max_lat = lat + (OCO2_TILE_DEGREES / 2)
            tile_min_lat = lat - (OCO2_TILE_DEGREES / 2)
            tile_min_lon = lon - (OCO2_TILE_DEGREES / 2)
            tile_max_lon = lon + (OCO2_TILE_DEGREES / 2)

            # Extract input data for this region from files
            subtile = sif_utils.extract_input_subtile(tile_min_lon, tile_max_lon, tile_min_lat, tile_max_lat,
                                                      TILES_DIR, OCO2_TILE_PIXELS, RES)
            if subtile is None:
                print('No input tiles found')
                continue
            # sifs_to_average = []
            # sif_lat_idx_low = max(0, lat_idx - 1)
            # sif_lat_idx_high = min(sifs.shape[0], lat_idx + 2) # Exclusive (high lat index)
            # sif_lon_idx_low = max(0, lon_idx - 1)
            # sif_lon_idx_high = min(sifs.shape[1], lon_idx + 2)
            # print('Lon idx', sif_lon_idx_low, sif_lon_idx_high)
            # print('Lat idx', sif_lat_idx_low, sif_lat_idx_high)
            # for i in range(sif_lat_idx_low, sif_lat_idx_high):
            #     for j in range(sif_lon_idx_low, sif_lon_idx_high):
            #         neighbor_sif = sifs[i, j]
            #         if not math.isnan(neighbor_sif):
            #             sifs_to_average.append(neighbor_sif)
            # print('Centre', sifs[lat_idx, lon_idx])
            # print('SIFs to average', sifs_to_average)
            # sif = sum(sifs_to_average) / len(sifs_to_average)

            # # Compute rectangle that bounds this OCO-2 observation
            # min_lon = lon - SUBTILE_DEGREES / 2
            # max_lon = lon + SUBTILE_DEGREES / 2
            # min_lat = lat - SUBTILE_DEGREES / 2
            # max_lat = lat + SUBTILE_DEGREES / 2
            # # print('====================================')
            # # print("Lon: min", min_lon, "max:", max_lon)
            # # print("Lat: min", min_lat, "max:", max_lat)

            # # Figure out which reflectance files to open. For each edge of the bounding box,
            # # find the left/top bound of the surrounding reflectance large tile.
            # min_lon_tile_left = (math.floor(min_lon * 10) / 10)
            # max_lon_tile_left = (math.floor(max_lon * 10) / 10)
            # min_lat_tile_top = (math.ceil(min_lat * 10) / 10)
            # max_lat_tile_top = (math.ceil(max_lat * 10) / 10)
            # num_tiles_lon = round((max_lon_tile_left - min_lon_tile_left) * 10) + 1
            # num_tiles_lat = round((max_lat_tile_top - min_lat_tile_top) * 10) + 1
            # file_left_lons = np.linspace(min_lon_tile_left, max_lon_tile_left, num_tiles_lon, endpoint=True)
            # file_top_lats = np.linspace(min_lat_tile_top, max_lat_tile_top, num_tiles_lat, endpoint=True)[::-1]  # Go through lats from top to bottom, because indices are numbered from top to bottom
            # # print("File left lons", file_left_lons)
            # # print("File top lats", file_top_lats)

            # # Because a sub-tile could span multiple files, patch together all of the files that 
            # # contain any portion of the sub-tile
            # columns = []
            # for file_left_lon in file_left_lons:
            #     rows = []
            #     for file_top_lat in file_top_lats:
            #         # Find what reflectance file to read from
            #         file_center_lon = round(file_left_lon + 0.05, 2)
            #         file_center_lat = round(file_top_lat - 0.05, 2)
            #         large_tile_filename = TILES_DIR + "/reflectance_lat_" + str(file_center_lat) + "_lon_" + str(file_center_lon) + ".npy"
            #         if not os.path.exists(large_tile_filename):
            #             # print('Needed data file', large_tile_filename, 'does not exist!')
            #             # For now, consider the data for this section as missing
            #             missing_tile = np.zeros((INPUT_CHANNELS, LARGE_TILE_PIXELS, LARGE_TILE_PIXELS))
            #             missing_tile[-1, :, :] = 1
            #             rows.append(missing_tile)
            #         else:
            #             # print('Large tile filename', large_tile_filename)
            #             large_tile = np.load(large_tile_filename)
            #             rows.append(large_tile)

            #     column = np.concatenate(rows, axis=1)
            #     columns.append(column)
            
            # combined_large_tiles = np.concatenate(columns, axis=2)
            # # print('All large tiles shape', combined_large_tiles.shape)

            # # Find indices of bounding box within this combined large tile 
            # top_idx, left_idx = lat_long_to_index(max_lat, min_lon, max_lat_tile_top, min_lon_tile_left, RES)
            # bottom_idx = top_idx + SUBTILE_PIXELS
            # right_idx = left_idx + SUBTILE_PIXELS
            # # print('From combined large tile: Top', top_idx, 'Bottom', bottom_idx, 'Left', left_idx, 'Right', right_idx)

            # # If the selected region (box) goes outside the range of the cover or reflectance dataset, that's a bug!
            # if top_idx < 0 or left_idx < 0:
            #     print("Index was negative!")
            #     exit(1)
            # if (bottom_idx >= combined_large_tiles.shape[1] or right_idx >= combined_large_tiles.shape[2]):
            #     print("Reflectance index went beyond edge of array!")
            #     exit(1)

            # # subtile = combined_large_tiles[:, top_idx:bottom_idx, left_idx:right_idx]

            # # Compute averages of each band (over non-cloudy pixels)
            # # Reshape tile into a list of pixels (pixels x channels)
            # pixels = np.moveaxis(subtile, 0, -1)
            # pixels = pixels.reshape((-1, pixels.shape[2]))

            # # Compute averages of each feature (band) over all pixels
            # tile_averages = np.mean(pixels, axis=0)

            # # NOTE: Exclude missing (cloudy) pixels for reflectance band averages
            # pixels_with_data = pixels[pixels[:, MISSING_REFLECTANCE_IDX] == 0]

            # # Remove tiles where no pixels have data (it's completely covered by clouds)
            # if pixels_with_data.shape[0] == 0:
            #     continue

            # # Compute average of the reflectance, over the non-cloudy pixels
            # reflectance_averages = np.mean(pixels_with_data[:, REFLECTANCE_BANDS], axis=0)
            # tile_averages[REFLECTANCE_BANDS] = reflectance_averages
                
            # # Remove tiles with any NaNs
            # if np.isnan(tile_averages).any():
            #     print('tile contained nan:', tile_filename)
            #     continue

            subtile_averages = sif_utils.compute_band_averages(subtile, subtile[MISSING_REFLECTANCE_IDX])

            # Save the sub-tiles array to file
            subtile_filename = OCO2_SUBTILES_DIR + "/lat_" + str(lat) + "_lon_" + str(lon) + ".npy"
            np.save(subtile_filename, subtile)

            # Record lon/lat/SIF and all the metadata about this sub-tile in a csv row
            point_lons.append(lon)
            point_lats.append(lat)
            point_sifs.append(sif)
            dataset_rows.append([lon, lat, DATE, subtile_filename] + subtile_averages.tolist() + 
                                [sif, num_soundings_point])
            

    # Write dataset to file
    with open(os.path.join(DATASET_DIR, OUTPUT_CSV_FILENAME), "w") as output_csv_file:
        csv_writer = csv.writer(output_csv_file, delimiter=",", quoting=csv.QUOTE_MINIMAL)
        for row in dataset_rows:
            csv_writer.writerow(row) 


point_sifs = np.array(point_sifs)
print('SIFs', np.min(point_sifs), np.max(point_sifs))

# Plot histogram of SIFs
plot_histogram(point_sifs, "sif_distribution_oco2.png")

# Scatterplot of OCO-2 points
green_cmap = plt.get_cmap('Greens')
plt.scatter(point_lons, point_lats, c=point_sifs, cmap=green_cmap)
plt.xlabel('Longitude')
plt.ylabel('Latitude')
plt.title('All OCO-2 points')
plt.savefig(os.path.join(DATA_DIR, 'exploratory_plots', 'oco2_points.png'))
plt.close()