import torch
import yaml
from pathlib import Path
from torch.utils.data import DataLoader
from torchvision import transforms, datasets

# ----------------------------
# Load dataset config
# ----------------------------
def load_yaml(yaml_path):
    with open(yaml_path, "r") as f:
        return yaml.safe_load(f)

# ----------------------------
# Dummy YOLO-like Model (Tiny CNN)
# ----------------------------
import torch.nn as nn
import torch.nn.functional as F

class TinyYOLO(nn.Module):
    def __init__(self, num_classes=4):
        super(TinyYOLO, self).__init__()
        self.conv1 = nn.Conv2d(3, 16, 3, stride=2, padding=1)
        self.conv2 = nn.Conv2d(16, 32, 3, stride=2, padding=1)
        self.fc1 = nn.Linear(32*80*80, 128)   # assumes input 640x640
        self.fc2 = nn.Linear(128, num_classes)

    def forward(self, x):
        x = F.relu(self.conv1(x))
        x = F.relu(self.conv2(x))
        x = x.view(x.size(0), -1)
        x = F.relu(self.fc1(x))
        return self.fc2(x)

# ----------------------------
# Training Loop
# ----------------------------
def train():
    # Load dataset info
    data_cfg = load_yaml("datasets/data.yaml")
    nc = data_cfg["nc"]
    class_names = data_cfg["names"]

    print(f"Training with {nc} classes: {class_names}")

    # Simple transform
    transform = transforms.Compose([
        transforms.Resize((640, 640)),
        transforms.ToTensor()
    ])

    # Use ImageFolder as a placeholder dataset
    train_data = datasets.ImageFolder("datasets/train/images", transform=transform)
    val_data   = datasets.ImageFolder("datasets/val/images", transform=transform)

    train_loader = DataLoader(train_data, batch_size=4, shuffle=True)
    val_loader   = DataLoader(val_data, batch_size=4, shuffle=False)

    # Model
    device = "cuda" if torch.cuda.is_available() else "cpu"
    model = TinyYOLO(num_classes=nc).to(device)

    optimizer = torch.optim.Adam(model.parameters(), lr=1e-3)
    criterion = nn.CrossEntropyLoss()

    # Train
    epochs = 2  # keep small for test
    for epoch in range(epochs):
        model.train()
        total_loss = 0
        for imgs, labels in train_loader:
            imgs, labels = imgs.to(device), labels.to(device)
            optimizer.zero_grad()
            outputs = model(imgs)
            loss = criterion(outputs, labels)
            loss.backward()
            optimizer.step()
            total_loss += loss.item()
        print(f"Epoch {epoch+1}/{epochs}, Loss: {total_loss/len(train_loader):.4f}")

    # Save weights
    Path("runs/train/exp/weights").mkdir(parents=True, exist_ok=True)
    torch.save(model.state_dict(), "runs/train/exp/weights/best.pt")
    print("✅ Training complete. Model saved at runs/train/exp/weights/best.pt")

if __name__ == "__main__":
    train()
