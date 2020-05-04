import copy
import math
import matplotlib.pyplot as plt
import os
import numpy as np
import pandas as pd
from sklearn.model_selection import train_test_split
from sklearn.metrics import mean_squared_error, r2_score
from scipy.stats import pearsonr, spearmanr
from torch.optim import lr_scheduler
from eval_subtile_dataset import EvalSubtileDataset
import time
import torch
import torchvision
import torchvision.transforms as transforms
import resnet
import torch.nn as nn
import torch.optim as optim

# Don't know how to properly import from Tile2Vec
# TODO this is a hack
import sys
sys.path.append('../')
import simple_cnn
import tile_transforms


DATA_DIR = "/mnt/beegfs/bulk/mirror/jyf6/datasets"
EVAL_DATASET_DIR = os.path.join(DATA_DIR, "dataset_2016-07-17")
TRAIN_DATASET_DIR = os.path.join(DATA_DIR, "dataset_2018-07-17")
EVAL_FILE = os.path.join(EVAL_DATASET_DIR, "eval_subtiles.csv") 
BAND_STATISTICS_FILE = os.path.join(TRAIN_DATASET_DIR, "band_statistics_train.csv")
SUBTILE_SIF_MODEL_FILE = os.path.join(DATA_DIR, "models/subtile_sif_simple_cnn_6")  # "models/subtile_sif_simple_cnn_4")
TRUE_VS_PREDICTED_PLOT = 'exploratory_plots/true_vs_predicted_sif_eval_subtile_simple_cnn.png'

INPUT_CHANNELS = 43

eval_points = pd.read_csv(EVAL_FILE)


def eval_model(subtile_sif_model, dataloader, dataset_size, criterion, device, sif_mean, sif_std):
    subtile_sif_model.eval()
    sif_mean = torch.tensor(sif_mean).to(device)
    sif_std = torch.tensor(sif_std).to(device)
    predicted = []
    true = []
    running_loss = 0.0

    # Iterate over data.
    for sample in dataloader:
        input_tile_standardized = sample['subtile'].to(device)
        true_sif_non_standardized = sample['SIF'].to(device)
        #print('Sample tile', input_tile_standardized[0, :, 8, 8])

        # forward
        with torch.set_grad_enabled(False):
            predicted_sif_standardized = subtile_sif_model(input_tile_standardized).flatten()
        predicted_sif_non_standardized = predicted_sif_standardized * sif_std + sif_mean
        loss = criterion(predicted_sif_non_standardized, true_sif_non_standardized)

        # statistics
        running_loss += loss.item() * len(sample['SIF'])
        predicted += predicted_sif_non_standardized.tolist()
        true += true_sif_non_standardized.tolist()
    return predicted, true


# Check if any CUDA devices are visible. If so, pick a default visible device.
# If not, use CPU.
if 'CUDA_VISIBLE_DEVICES' in os.environ:
    print('CUDA_VISIBLE_DEVICES:', os.environ['CUDA_VISIBLE_DEVICES'])
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
else:
    device = "cpu"
print("Device", device)

# Read train/val tile metadata
eval_metadata = pd.read_csv(EVAL_FILE)
print("Eval samples", len(eval_metadata))

# Read mean/standard deviation for each band, for standardization purposes
train_statistics = pd.read_csv(BAND_STATISTICS_FILE)
train_means = train_statistics['mean'].values
train_stds = train_statistics['std'].values
print("Validation samples", len(eval_metadata))
print("Means", train_means)
print("Stds", train_stds)
band_means = train_means[:-1]
sif_mean = train_means[-1]
band_stds = train_stds[:-1]
sif_std = train_stds[-1]

# Set up image transforms
transform_list = []
transform_list.append(tile_transforms.StandardizeTile(band_means, band_stds))
transform = transforms.Compose(transform_list)

# Set up Dataset and Dataloader
dataset_size = len(eval_metadata)
dataset = EvalSubtileDataset(eval_metadata, transform=transform)
dataloader = torch.utils.data.DataLoader(dataset, batch_size=4,
                                         shuffle=True, num_workers=4)

subtile_sif_model = simple_cnn.SimpleCNN(input_channels=INPUT_CHANNELS, reduced_channels=20, output_dim=1).to(device)
subtile_sif_model.load_state_dict(torch.load(SUBTILE_SIF_MODEL_FILE, map_location=device))

criterion = nn.MSELoss(reduction='mean')

# Evaluate the model
predicted, true = eval_model(subtile_sif_model, dataloader, dataset_size, criterion, device, sif_mean, sif_std)
print('Predicted', predicted[0:50])
print('True', true[0:50])

# Compare predicted vs true: calculate NRMSE, R2, scatter plot
nrmse = math.sqrt(mean_squared_error(predicted, true)) / sif_mean
corr, _ = pearsonr(predicted, true)
print('NRMSE:', round(nrmse, 3))
print("Pearson correlation coefficient:", round(corr, 3))

# Scatter plot of true vs predicted
plt.scatter(true, predicted)
plt.xlabel('True')
plt.ylabel('Predicted')
plt.title('Subtile prediction with simple CNN')
plt.savefig(TRUE_VS_PREDICTED_PLOT)
plt.close()