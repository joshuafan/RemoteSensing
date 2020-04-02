"""
Learns embedding-to-SIF model, given pre-computed (fixed) embeddings,
"""
# TODO
import copy
import pickle
import math
import matplotlib.pyplot as plt
import numpy as np
import os
import pandas as pd
from sklearn.model_selection import train_test_split
from torch.optim import lr_scheduler

import time
import torch
import torchvision
import torchvision.transforms as transforms
import resnet
import torch.nn as nn
import torch.optim as optim

from reflectance_cover_sif_dataset import ReflectanceCoverSIFDataset
from subtile_embedding_dataset import SubtileEmbeddingDataset

from sif_utils import get_subtiles_list
import tile_transforms


# TODO this is a hack
import sys
sys.path.append('../')
from tile2vec.src.tilenet import make_tilenet
from embedding_to_sif_model import EmbeddingToSIFModel
from embedding_to_sif_nonlinear_model import EmbeddingToSIFNonlinearModel

DATASET_DIR = "datasets/dataset_2018-08-01"
# INFO_FILE_TRAIN = os.path.join(DATASET_DIR, "tile_info_train.csv")
# INFO_FILE_VAL = os.path.join(DATASET_DIR, "tile_info_val.csv")
BAND_STATISTICS_FILE = os.path.join(DATASET_DIR, "band_statistics_train.csv")
TILE2VEC_MODEL_FILE = "models/tile2vec_dim10_v2/TileNet_epoch50.ckpt"
EMBEDDING_TO_SIF_MODEL_FILE = "models/tile2vec_dim10_embedding_to_sif_nonlinear"

# LOAD_EMBEDDINGS = False
SUBTILE_EMBEDDING_DATASET_TRAIN = os.path.join(DATASET_DIR, "tile2vec_dim10_embeddings_train.csv")
SUBTILE_EMBEDDING_DATASET_VAL = os.path.join(DATASET_DIR, "tile2vec_dim10_embeddings_val.csv")

# If EMBEDDING_TYPE is 'average', the embedding is just the average of each band.
# If it is 'tile2vec', we use the Tile2Vec model 
# EMBEDDING_TYPE = 'average'
TRAINING_PLOT_FILE = 'exploratory_plots/tile2vec_dim10_nonlinear_subtile_sif_prediction.png'
SUBTILE_DIM = 10
Z_DIM = 10
INPUT_CHANNELS = 14
NUM_EPOCHS = 30
LEARNING_RATE = 1e-3


def train_embedding_to_sif_model(embedding_to_sif_model, dataloaders, dataset_sizes, criterion, optimizer, device, sif_mean, sif_std, num_epochs=25):
    since = time.time()

    best_model_wts = copy.deepcopy(embedding_to_sif_model.state_dict())
    best_loss = float('inf')
    train_losses = []
    val_losses = []
    print('SIF mean', sif_mean)
    print('SIF std', sif_std)
    sif_mean = torch.tensor(sif_mean).to(device)
    sif_std = torch.tensor(sif_std).to(device)

    for epoch in range(num_epochs):
        print('Epoch {}/{}'.format(epoch, num_epochs - 1))
        print('-' * 10)

        # Each epoch has a training and validation phase
        for phase in ['train', 'val']:
            if phase == 'train':
                embedding_to_sif_model.train()
            else:
                embedding_to_sif_model.eval()

            running_loss = 0.0

            # Iterate over data.
            for sample in dataloaders[phase]:
                batch_size = len(sample['SIF'])
                subtile_embeddings = sample['subtile_embeddings'].to(device)
                true_sif_non_standardized = sample['SIF'].to(device)
                true_sif_standardized = ((true_sif_non_standardized - sif_mean) / sif_std).to(device)

                # zero the parameter gradients
                optimizer.zero_grad()
                predicted_subtile_sifs = torch.empty((batch_size, subtile_embeddings.shape[1]), device=device)
                #print('Subtile embeddings', subtile_embeddings.shape)
                #print('Predicted subtile SIFs', predicted_subtile_sifs.shape)

                # Forward pass: feed subtiles through embedding model and then the
                # embedding -> SIF model
                with torch.set_grad_enabled(phase == 'train'):
                    for i in range(batch_size):
                        predicted_sifs = embedding_to_sif_model(subtile_embeddings[i])

                        #print('predicted_sif shape', predicted_sifs.shape)
                        predicted_subtile_sifs[i] = predicted_sifs.flatten()
                    
                    # Predicted SIF for full tile
                    predicted_sif_standardized = torch.mean(predicted_subtile_sifs, axis=1)
                    #print('Shape of predicted total SIFs', predicted_sif_standardized.shape)
                    #print('Shape of true total SIFs', true_sif_standardized.shape)
                    loss = criterion(predicted_sif_standardized, true_sif_standardized)

                    # backward + optimize only if in training phase
                    if phase == 'train':
                        loss.backward()
                        optimizer.step()

                    # statistics
                    predicted_sif_non_standardized = torch.tensor(predicted_sif_standardized * sif_std + sif_mean, dtype=torch.float).to(device)
                    #print('========================')
                    #print('Predicted', predicted_sif_non_standardized)
                    #print('True', true_sif_non_standardized)
                    non_standardized_loss = criterion(predicted_sif_non_standardized, true_sif_non_standardized)
                    running_loss += non_standardized_loss.item()

            epoch_loss = (math.sqrt(running_loss / dataset_sizes[phase]) / sif_mean).item()

            print('{} Loss: {:.4f}'.format(
                phase, epoch_loss))

            # deep copy the model
            if phase == 'val' and epoch_loss < best_loss:
                best_loss = epoch_loss
                best_model_wts = copy.deepcopy(embedding_to_sif_model.state_dict())

            # Record loss
            if phase == 'train':
                train_losses.append(epoch_loss)
            else:
                val_losses.append(epoch_loss)

        print()

    time_elapsed = time.time() - since
    print('Training complete in {:.0f}m {:.0f}s'.format(
        time_elapsed // 60, time_elapsed % 60))
    print('Best val loss: {:4f}'.format(best_loss))

    # load best model weights
    embedding_to_sif_model.load_state_dict(best_model_wts)
    return embedding_to_sif_model, train_losses, val_losses, best_loss



# Check if any CUDA devices are visible. If so, pick a default visible device.
# If not, use CPU.
if 'CUDA_VISIBLE_DEVICES' in os.environ:
    print('CUDA_VISIBLE_DEVICES:', os.environ['CUDA_VISIBLE_DEVICES'])
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
else:
    device = "cpu"
print("Device", device)

# Read mean/standard deviation for each band, for standardization purposes
train_statistics = pd.read_csv(BAND_STATISTICS_FILE)
train_means = train_statistics['mean'].values
train_stds = train_statistics['std'].values
band_means = train_means[:-1]
sif_mean = train_means[-1]
band_stds = train_stds[:-1]
sif_std = train_stds[-1]

# Load pre-computed subtile embeddings from file
train_tile_rows = pd.read_csv(SUBTILE_EMBEDDING_DATASET_TRAIN)
val_tile_rows = pd.read_csv(SUBTILE_EMBEDDING_DATASET_VAL)

# Set up datasets and dataloaders
embedding_datasets = {'train': SubtileEmbeddingDataset(train_tile_rows),
                      'val': SubtileEmbeddingDataset(val_tile_rows)}
embedding_dataloaders = {x: torch.utils.data.DataLoader(embedding_datasets[x], batch_size=2,
                                                        shuffle=True, num_workers=1)
                  for x in ['train', 'val']}

#if EMBEDDING_TYPE == 'average':
#    embedding_to_sif_model = EmbeddingToSIFModel(embedding_size=INPUT_CHANNELS).to(device)  # TODO
#elif EMBEDDING_TYPE == 'tile2vec':
#    embedding_to_sif_model = EmbeddingToSIFModel(embedding_size=Z_DIM).to(device)
#else:
#    print('Unsupported embedding type', EMBEDDING_TYPE)
#    exit(1)

# Create embedding-to-SIF model
embedding_to_sif_model = EmbeddingToSIFNonlinearModel(embedding_size=Z_DIM).to(device)
criterion = nn.MSELoss(reduction='mean')
optimizer = optim.Adam(embedding_to_sif_model.parameters(), lr=LEARNING_RATE)
dataset_sizes = {'train': len(train_tile_rows),
                 'val': len(val_tile_rows)}

# Train model
embedding_to_sif_model, train_losses, val_losses, best_loss = train_embedding_to_sif_model(embedding_to_sif_model, embedding_dataloaders, dataset_sizes, criterion, optimizer, device, sif_mean, sif_std, num_epochs=NUM_EPOCHS)

torch.save(embedding_to_sif_model.state_dict(), EMBEDDING_TO_SIF_MODEL_FILE)

# Plot loss curves
print("Train losses:", train_losses)
print("Validation losses:", val_losses)
epoch_list = range(NUM_EPOCHS)
train_plot, = plt.plot(epoch_list, train_losses, color='blue', label='Train NRMSE')
val_plot, = plt.plot(epoch_list, val_losses, color='red', label='Validation NRMSE')
plt.legend(handles=[train_plot, val_plot])
plt.xlabel('Epoch #')
plt.ylabel('Normalized Root Mean Squared Error')
plt.savefig(TRAINING_PLOT_FILE) 
plt.close()





