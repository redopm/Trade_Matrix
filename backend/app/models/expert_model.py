"""
Expert Pattern Recognition Model (PyTorch)
Defines the exact architecture used during Kaggle training for loading weights.
"""
import torch
import torch.nn as nn
from torchvision import models

class ExpertTradeMatrixModel(nn.Module):
    """
    Dual-Input AI Model:
    1. CNN Head (EfficientNetV2_S) for chart images.
    2. LSTM Head for 60-day exact OHLCV numerical data.
    """
    def __init__(self, n_classes: int = 3):
        super(ExpertTradeMatrixModel, self).__init__()
        # Vision Branch (CNN)
        self.vision = models.efficientnet_v2_s(weights=None)
        num_ftrs = self.vision.classifier[1].in_features
        self.vision.classifier = nn.Identity() 
        
        # Sequence Branch (LSTM)
        self.lstm = nn.LSTM(input_size=5, hidden_size=64, num_layers=2, batch_first=True, dropout=0.2)
        
        # Combiner
        self.fc1 = nn.Linear(num_ftrs + 64, 256)
        self.relu = nn.ReLU()
        self.dropout = nn.Dropout(0.4)
        self.fc2 = nn.Linear(256, n_classes)
        
    def forward(self, img, series):
        img_features = self.vision(img) 
        lstm_out, (hn, cn) = self.lstm(series)
        seq_features = hn[-1] 
        combined = torch.cat((img_features, seq_features), dim=1)
        x = self.fc1(combined)
        x = self.relu(x)
        x = self.dropout(x)
        out = self.fc2(x)
        return out
