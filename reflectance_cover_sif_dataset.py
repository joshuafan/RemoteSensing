from __future__ import print_function, division
import os
import torch
import pandas as pd
from skimage import io, transform
import numpy as np
from torch.utils.data import Dataset, DataLoader
from PIL import Image
from torchvision import transforms
import sif_utils

# Ignore warnings
import warnings

warnings.filterwarnings("ignore")



class ReflectanceCoverSIFDataset(Dataset):
    """Dataset mapping a tile (with reflectance/cover bands) to total SIF"""

    def __init__(self, tile_info):  # root_dir, transform=None):
        """
        Args:
            tile_info_file (string): Pandas dataframe containing metadata for each tile.
            The tile is assumed to have shape (band x lat x long)
        """
        self.tile_info = tile_info
        #self.root_dir = root_dir
        #self.transform = transform

    def __len__(self):
        return len(self.tile_info)

    def __getitem__(self, idx):
        if torch.is_tensor(idx):
            idx = idx.tolist()

        current_tile_info = self.tile_info.iloc[idx]
        #year, month, day_of_year = sif_utils.parse_date_string(current_tile_info.loc['date'])
        tile = np.load(current_tile_info.loc['tile_file'])
        #print('tile shape', tile.shape)
        #for i in range(tile.shape[0]):
        #    print('Band i average', np.mean(tile[i].flatten()))
 
        tile = torch.tensor(tile, dtype=torch.float)
        #print('Tile shape', tile.shape)
        
        #tile = Image.fromarray(tile)
        #if self.transform:
        #    tile = self.transform(tile)

        sample = {'lon': current_tile_info.loc['lon'],
                  'lat': current_tile_info.loc['lat'],
                  #'year': year,
                  #'day_of_year': day_of_year,
                  'tile': tile,
                  'SIF': current_tile_info.loc["SIF"]}
        return sample
