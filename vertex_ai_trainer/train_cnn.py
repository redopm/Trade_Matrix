import os
import io
import json
import argparse
from collections import Counter
import random
import subprocess

# Auto-install dependencies before importing them (for pre-built containers)
print("Installing dependencies...")
subprocess.check_call(["pip", "install", "--no-cache-dir", "timm==0.9.12", "mplfinance==0.9.0", "yfinance==0.2.37", "google-cloud-storage==2.15.0"])
print("Dependencies installed successfully!")

import torch
import torch.nn as nn
import torch.optim as optim
from torch.utils.data import Dataset, DataLoader
from torchvision import transforms
from torch.optim.lr_scheduler import OneCycleLR
import timm
import yfinance as yf
import mplfinance as mpf
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np
from PIL import Image
from google.cloud import storage
import joblib
from sklearn.preprocessing import LabelEncoder

# ── Argument Parsing ──────────────────────────────────────────────────────────
parser = argparse.ArgumentParser()
parser.add_argument('--bucket', type=str, required=True, help='GCS bucket name for data and models')
args = parser.parse_args()

BUCKET_NAME = args.bucket
os.makedirs('/app/data', exist_ok=True)
os.makedirs('/app/output', exist_ok=True)

print(f"Starting Training on Bucket: {BUCKET_NAME}")

# ── 1. Download Labels from GCS ───────────────────────────────────────────────
storage_client = storage.Client()
bucket = storage_client.bucket(BUCKET_NAME)
blob = bucket.blob('training_data/labels.jsonl')

if not blob.exists():
    print("No labels.jsonl found! Please upload one to gs://{}/training_data/labels.jsonl".format(BUCKET_NAME))
    exit(1)

blob.download_to_filename('/app/data/labels.jsonl')

labels = []
with open('/app/data/labels.jsonl', 'r') as f:
    for line in f:
        line = line.strip()
        if line:
            labels.append(json.loads(line))

high_conf = [l for l in labels if float(l.get('confidence', 0)) >= 0.65]
print(f"Total labels: {len(labels)} | High-confidence (>=65%): {len(high_conf)}")

# Add more patterns to the classes
PATTERN_CLASSES = sorted(set(l['pattern_name'] for l in high_conf))
CLASS_TO_IDX = {c: i for i, c in enumerate(PATTERN_CLASSES)}
print(f'Classes ({len(PATTERN_CLASSES)}): {PATTERN_CLASSES}')

# ── 2. Chart Generation (FAST CACHING) ─────────────────────────────────────────
DARK_STYLE = mpf.make_mpf_style(
    base_mpl_style='dark_background',
    marketcolors=mpf.make_marketcolors(
        up='#00f5a0', down='#ff4466', edge='inherit', wick='inherit'
    ),
)

print("Pre-downloading historical data to prevent yfinance rate limits...")
import pandas as pd
unique_symbols = list(set(l['symbol'] for l in high_conf))
stock_data = {}

for sym in unique_symbols:
    try:
        df = yf.download(sym, period="5y", progress=False)
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.droplevel(1)
        stock_data[sym] = df[['Open','High','Low','Close','Volume']].dropna()
    except Exception:
        pass
print(f"Pre-download complete for {len(stock_data)} stocks!")

def generate_chart_image(symbol, window_start, window_end, img_size=(224, 224)):
    try:
        if symbol not in stock_data: return None
        df = stock_data[symbol]
        mask = (df.index >= window_start) & (df.index <= window_end)
        sub_df = df.loc[mask]
        
        if sub_df.empty or len(sub_df) < 5:
            return None

        ema50 = sub_df['Close'].ewm(span=50).mean()
        ema200 = sub_df['Close'].ewm(span=200).mean()

        apds = [
            mpf.make_addplot(ema50, color='#4facfe', linewidth=1),
            mpf.make_addplot(ema200, color='#ffd700', linewidth=1.5),
        ]

        buf = io.BytesIO()
        fig, _ = mpf.plot(
            sub_df, type='candle', style=DARK_STYLE,
            addplot=apds, volume=True,
            figsize=(4, 3), returnfig=True,
            tight_layout=True
        )
        fig.savefig(buf, format='png', dpi=100)
        plt.close(fig)
        buf.seek(0)
        return Image.open(buf).convert('RGB').resize(img_size)
    except Exception:
        return None

# ── 3. Dataset & DataLoader ───────────────────────────────────────────────────
class ChartPatternDataset(Dataset):
    def __init__(self, labels, transform=None, img_size=(224, 224)):
        self.labels = labels
        self.transform = transform
        self.img_size = img_size
        self._cache = {}

    def __len__(self):
        return len(self.labels)

    def __getitem__(self, idx):
        label = self.labels[idx]
        key = f"{label['symbol']}_{label.get('window_end', '')}"
        
        if key not in self._cache:
            img = generate_chart_image(label['symbol'], label.get('window_start'), label.get('window_end'), self.img_size)
            if img is None:
                img = Image.new('RGB', self.img_size, (8, 12, 20))
            self._cache[key] = img

        img = self._cache[key]
        if self.transform:
            img = self.transform(img)
        return img, CLASS_TO_IDX[label['pattern_name']]

train_transform = transforms.Compose([
    transforms.RandomHorizontalFlip(p=0.3),
    transforms.ColorJitter(brightness=0.2, contrast=0.2),
    transforms.ToTensor(),
    transforms.Normalize([0.485, 0.456, 0.406], [0.229, 0.224, 0.225]),
])

val_transform = transforms.Compose([
    transforms.ToTensor(),
    transforms.Normalize([0.485, 0.456, 0.406], [0.229, 0.224, 0.225]),
])

random.shuffle(high_conf)
split = int(len(high_conf) * 0.85)
train_labels, val_labels = high_conf[:split], high_conf[split:]

train_ds = ChartPatternDataset(train_labels, transform=train_transform)
val_ds = ChartPatternDataset(val_labels, transform=val_transform)

train_loader = DataLoader(train_ds, batch_size=32, shuffle=True, num_workers=0)
val_loader = DataLoader(val_ds, batch_size=32, shuffle=False, num_workers=0)

device = 'cuda' if torch.cuda.is_available() else 'cpu'
print(f"Running on Device: {device}")

# ── 4. Model Architecture ─────────────────────────────────────────────────────
class PatternCNN(nn.Module):
    def __init__(self, n_classes, dropout=0.3):
        super().__init__()
        self.backbone = timm.create_model('efficientnet_b0', pretrained=True, num_classes=0)
        in_features = self.backbone.num_features
        self.classifier = nn.Sequential(
            nn.Dropout(dropout),
            nn.Linear(in_features, 256),
            nn.ReLU(),
            nn.Dropout(dropout / 2),
            nn.Linear(256, n_classes),
        )
    def forward(self, x):
        return self.classifier(self.backbone(x))

model = PatternCNN(n_classes=len(PATTERN_CLASSES)).to(device)

# ── 5. Training Loop ──────────────────────────────────────────────────────────
EPOCHS = 25
optimizer = optim.AdamW(model.parameters(), lr=1e-3, weight_decay=1e-4)
scheduler = OneCycleLR(optimizer, max_lr=1e-3, epochs=EPOCHS, steps_per_epoch=len(train_loader) if len(train_loader) > 0 else 1)
criterion = nn.CrossEntropyLoss(label_smoothing=0.1)

best_val_acc = 0.0
history = {'train_loss': [], 'val_acc': []}

if len(train_loader) > 0:
    for epoch in range(EPOCHS):
        model.train()
        train_loss = 0
        for imgs, targets in train_loader:
            imgs, targets = imgs.to(device), targets.to(device)
            optimizer.zero_grad()
            outputs = model(imgs)
            loss = criterion(outputs, targets)
            loss.backward()
            optimizer.step()
            scheduler.step()
            train_loss += loss.item()

        model.eval()
        correct, total = 0, 0
        with torch.no_grad():
            for imgs, targets in val_loader:
                imgs, targets = imgs.to(device), targets.to(device)
                outputs = model(imgs)
                _, predicted = outputs.max(1)
                total += targets.size(0)
                correct += predicted.eq(targets).sum().item()

        val_acc = correct / total if total > 0 else 0
        avg_loss = train_loss / len(train_loader)
        history['train_loss'].append(avg_loss)
        history['val_acc'].append(val_acc)

        if val_acc >= best_val_acc:
            best_val_acc = val_acc
            torch.save(model.state_dict(), '/app/output/best_cnn.pth')
            
        print(f'Epoch {epoch+1:>2}/{EPOCHS} | Loss: {avg_loss:.4f} | Val Acc: {val_acc:.2%}')

# ── 6. Save Bundle & Upload to GCS ────────────────────────────────────────────
class ColabCNNWrapper:
    def __init__(self, cnn_model, classes, device):
        self.cnn_model = cnn_model
        self.classes = classes
        self.device = device
        self.model_type = 'cnn_efficientnet_b0'

    def predict_proba(self, X):
        n = len(self.classes)
        return np.ones((1, n)) / n

    def predict_from_image(self, img_tensor):
        with torch.no_grad():
            output = self.cnn_model(img_tensor.to(self.device))
            proba = torch.softmax(output, dim=1).cpu().numpy()[0]
        return proba

le = LabelEncoder()
le.fit(PATTERN_CLASSES)

if os.path.exists('/app/output/best_cnn.pth'):
    model.load_state_dict(torch.load('/app/output/best_cnn.pth', map_location=device))
model.eval()

model_bundle = {
    'model': ColabCNNWrapper(model, PATTERN_CLASSES, device),
    'cnn_state_dict': model.state_dict(),
    'cnn_architecture': 'efficientnet_b0',
    'label_encoder': le,
    'classes': PATTERN_CLASSES,
    'feature_names': [],
    'n_features': 0,
    'model_type': 'cnn',
    'val_accuracy': best_val_acc,
    'n_classes': len(PATTERN_CLASSES),
    'training_history': history,
}

output_path = '/app/output/vertex_colab_model.pkl'
joblib.dump(model_bundle, output_path)

# Upload back to GCS
print(f"Uploading model to gs://{BUCKET_NAME}/models/vertex_colab_model.pkl")
out_blob = bucket.blob('models/vertex_colab_model.pkl')
out_blob.upload_from_filename(output_path)
print("Training Job Completed successfully!")
