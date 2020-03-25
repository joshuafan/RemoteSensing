import copy
import math
import matplotlib.pyplot as plt
import os
import numpy as np
import pandas as pd
from sklearn.model_selection import train_test_split
from torch.optim import lr_scheduler
from reflectance_cover_sif_dataset import ReflectanceCoverSIFDataset
import time
import torch
import torchvision
import torchvision.transforms as transforms
import resnet
import torch.nn as nn
import torch.optim as optim


DATASET_DIR = "datasets/dataset_2016-08-01"
EVAL_FILE = os.path.join(DATASET_DIR, "tile_info_val.csv")  #"datasets/generated_subtiles/eval_subtiles.csv" 
TRAINED_MODEL_FILE = "models/large_tile_sif_prediction"

eval_points = pd.read_csv(EVAL_FILE)

def eval_model(model, dataloader, dataset_size, criterion, device, sif_mean, sif_std):
    model.eval()   # Set model to evaluate mode
    sif_mean = torch.tensor(sif_mean).to(device)
    sif_std = torch.tensor(sif_std).to(device)

    running_loss = 0.0

    # Iterate over data.
    for sample in dataloader:
        input_tile = sample['tile'].to(device)
        true_sif_non_standardized = sample['SIF'].to(device)

        # forward
        # track history if only in train
        with torch.set_grad_enabled(False):
            predicted_sif_standardized = model(input_tile).flatten()
        predicted_sif_non_standardized = torch.tensor(predicted_sif_standardized * sif_std + sif_mean, dtype=torch.float).to(device)
        loss = criterion(predicted_sif_non_standardized, true_sif_non_standardized)

        # statistics
        running_loss += loss.item() * len(sample['SIF'])

    loss = math.sqrt(running_loss / dataset_size) / sif_mean
    return loss


device = torch.device("cuda:0" if torch.cuda.is_available() else "cpu")
print("Device", device)

# Read train/val tile metadata
eval_metadata = pd.read_csv(EVAL_FILE)
average_sif = eval_metadata['SIF'].mean()
print("Average sif", average_sif)
print("Eval samples", len(eval_metadata))

# Read mean/standard deviation for each band, for standardization purposes
train_statistics = pd.read_csv(BAND_STATISTICS_FILE)
train_means = train_statistics['mean'].values
train_stds = train_statistics['std'].values
print("Train samples", len(train_metadata))
print("Validation samples", len(val_metadata))
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
dataset = ReflectanceCoverSIFDataset(eval_metadata)
dataloader = torch.utils.data.DataLoader(dataset, batch_size=4,
                                         shuffle=True, num_workers=4)

# Load trained model from file
resnet_model = resnet.resnet18(input_channels=14).to(device)
resnet_model.load_state_dict(torch.load(TRAINED_MODEL_FILE))
criterion = nn.MSELoss(reduction='mean')

# Evaluate the model
loss = eval_model(resnet_model, dataloader, dataset_size, criterion, device, sif_mean, sif_std)
print("Eval Loss", loss)

