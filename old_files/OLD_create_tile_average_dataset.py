"""
Randomly splits tiles into 80% train, 20% validation.
Throws out tiles with insufficient CDL coverage.
Creates a dataset of tile averages.
"""
import csv
import matplotlib.pyplot as plt
import numpy as np
import os
import pandas as pd
import sklearn.model_selection
from sif_utils import plot_histogram
import torch

DATA_DIR = "/mnt/beegfs/bulk/mirror/jyf6/datasets"
# DATASET_DIRS = [os.path.join(DATA_DIR, "dataset_2018-07-08"),
#                 os.path.join(DATA_DIR, "dataset_2018-07-22"),
#                 os.path.join(DATA_DIR, "dataset_2018-08-05"),
#                 os.path.join(DATA_DIR, "dataset_2018-08-19"),
#                 os.path.join(DATA_DIR, "dataset_2018-09-02")] 
DATASET_DIRS = [os.path.join(DATA_DIR, "dataset_2018-09-02")] 

REFLECTANCE_BANDS = list(range(0, 9))
CDL_BANDS = list(range(12, 42))
MIN_CDL_COVERAGE = 0.5  # Throw out tiles if less than this fraction of land cover is unknown
MISSING_REFLECTANCE_IDX = -1

for DATASET_DIR in DATASET_DIRS:
    print("Dateset dir:", DATASET_DIR)
    INITIAL_CSV_FILE = os.path.join(DATASET_DIR, "reflectance_cover_to_sif.csv")
    TILE_AVERAGE_FILE = os.path.join(DATASET_DIR, "tile_averages.csv")
    NEW_COLUMNS = ['lon', 'lat', 'date', 'tile_file', 'ref_1', 'ref_2', 'ref_3', 'ref_4', 'ref_5', 'ref_6', 'ref_7',
                        'ref_10', 'ref_11', 'Rainf_f_tavg', 'SWdown_f_tavg', 'Tair_f_tavg', 
                        'grassland_pasture', 'corn', 'soybean', 'shrubland',
                        'deciduous_forest', 'evergreen_forest', 'spring_wheat', 'developed_open_space',
                        'other_hay_non_alfalfa', 'winter_wheat', 'herbaceous_wetlands',
                        'woody_wetlands', 'open_water', 'alfalfa', 'fallow_idle_cropland',
                        'sorghum', 'developed_low_intensity', 'barren', 'durum_wheat',
                        'canola', 'sunflower', 'dry_beans', 'developed_med_intensity',
                        'millet', 'sugarbeets', 'oats', 'mixed_forest', 'peas', 'barley',
                        'lentils', 'missing_reflectance', 'SIF', 'cloud_fraction', 'num_soundings']



    # Read all tile metadata
    dataset = pd.read_csv(INITIAL_CSV_FILE)
    dataset.reset_index(drop=True, inplace=True)
    print('(Unfiltered) number of large tiles:', len(dataset))

    # Check if any CUDA devices are visible. If so, pick a default visible device.
    # If not, use CPU.
    if 'CUDA_VISIBLE_DEVICES' in os.environ:
        print('CUDA_VISIBLE_DEVICES:', os.environ['CUDA_VISIBLE_DEVICES'])
        device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    else:
        device = "cpu"
    print("Device", device)


    # Split into train/val, and write the split to a file (to ensure that all methods use the same
    # train/val split)
    # train_set, val_set = sklearn.model_selection.train_test_split(tile_metadata, test_size=0.2)
    # datasets = {"train": train_set, "val": val_set}
    # for split in ["train", "val"]:

    # Create a dataset of tile-average values
    csv_rows = []
    csv_rows.append(NEW_COLUMNS)
    i = -1
    for index, row in dataset.iterrows():
        i += 1
        if i % 100 == 0:
            print('Processing tile', i)

        # Tile assumed to be (band x lat x long)
        tile = np.load(row.loc['tile_file'])
        # print('Tile', tile.shape, 'dtype', tile.dtype)
        tile_averages = torch.mean(torch.tensor(tile).to(device), dim=(1,2)).cpu().numpy()

        # Reshape tile into a list of pixels (pixels x channels)
        pixels = np.moveaxis(tile, 0, -1)
        pixels = pixels.reshape((-1, pixels.shape[2]))
        tile_averages = np.mean(pixels, axis=0)
        # print('=================================')
        # print('Pixels shape', pixels.shape)
        # print('Band averages', tile_averages)

        # NOTE: Exclude missing (cloudy) pixels for reflectance band averages
        pixels_with_data = pixels[pixels[:, MISSING_REFLECTANCE_IDX] == 0]
        # print('Pixels with data', pixels_with_data.shape)

        # Remove tiles where no pixels have data (it's completely covered by clouds)
        if pixels_with_data.shape[0] == 0:
            continue

        # Compute average of the reflectance, over the non-cloudy pixels
        reflectance_averages = np.mean(pixels_with_data[:, REFLECTANCE_BANDS], axis=0)
        # print('Reflectance averages', reflectance_averages.shape)

        tile_averages[REFLECTANCE_BANDS] = reflectance_averages
        # print('After reflectance filter', tile_averages)

        # Remove tiles with any NaNs
        if np.isnan(tile_averages).any():
            print('tile contained nan:', row.loc['tile_file'])
            continue

        # Remove tiles with little CDL coverage (for the crops we're interested in)
        cdl_coverage = np.sum(tile_averages[CDL_BANDS])
        if cdl_coverage < MIN_CDL_COVERAGE:
            print('CDL coverage too low:', cdl_coverage)
            print(row.loc['tile_file'])
            continue

        # # If too much of this pixel is covered by clouds (reflectance
        # # data is missing), throw this tile out
        # if tile_averages[-1] > MAX_LANDSAT_CLOUD_COVER:
        #     continue

        # # Remove tiles with low SIF (those observations may be unreliable)
        # if float(row.loc['SIF']) < MIN_SIF:
        #     continue

        # if float(row.loc['cloud_fraction']) > MAX_TROPOMI_CLOUD_COVER:
        #     continue

        # if float(row.loc['num_soundings']) < MIN_NUM_SOUNDINGS:
        #   continue

        csv_row = [row.loc['lon'], row.loc['lat'], row.loc['date'], row.loc['tile_file']] + tile_averages.tolist() + [row.loc['SIF'], row.loc['cloud_fraction'], row.loc['num_soundings']]
        csv_rows.append(csv_row)

    # Write rows to .csv file
    print('Writing to', TILE_AVERAGE_FILE)
    with open(TILE_AVERAGE_FILE, "w") as output_csv_file:
        csv_writer = csv.writer(output_csv_file, delimiter=",", quoting=csv.QUOTE_MINIMAL)
        for row in csv_rows:
            csv_writer.writerow(row)


