import torch
import cv2
import os
from pathlib import Path
import yaml
from torchvision import transforms

# ----------------------------
# Load dataset config
# ----------------------------
def load_yaml(yaml_path):
    with open(yaml_path, "r") as f:
        return yaml.safe_load(f)

# ----------------------------
# TinyYOLO (must match train.py)
# ----------------------------
import torch.nn as nn
import torch.nn.functional as F

class TinyYOLO(nn.Module):
    def __init__(self, num_classes=4):
        super(TinyYOLO, self).__init__()
        self.conv1 = nn.Conv2d(3, 16, 3, stride=2, padding=1)
        self.conv2 = nn.Conv2d(16, 32, 3, stride=2, padding=1)
        self.fc1 = nn.Linear(32*80*80, 128)   # must match training
        self.fc2 = nn.Linear(128, num_classes)

    def forward(self, x):
        x = F.relu(self.conv1(x))
        x = F.relu(self.conv2(x))
        x = x.view(x.size(0), -1)
        x = F.relu(self.fc1(x))
        return self.fc2(x)

# ----------------------------
# Detection Function
# ----------------------------
def detect(weights="runs/train/exp/weights/best.pt", source="datasets/val/images"):
    device = "cuda" if torch.cuda.is_available() else "cpu"

    # Load dataset config
    data_cfg = load_yaml("datasets/data.yaml")
    class_names = data_cfg["names"]
    nc = data_cfg["nc"]

    # Model
    model = TinyYOLO(num_classes=nc).to(device)
    model.load_state_dict(torch.load(weights, map_location=device))
    model.eval()

    # Transform
    transform = transforms.Compose([
        transforms.Resize((640, 640)),
        transforms.ToTensor()
    ])

    # Output folder
    Path("runs/detect/exp").mkdir(parents=True, exist_ok=True)

    # Loop over images
    for img_name in os.listdir(source):
        img_path = os.path.join(source, img_name)
        img = cv2.imread(img_path)
        if img is None:
            continue

        # Preprocess
        img_rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
        img_tensor = transform(cv2.resize(img_rgb, (640, 640))).unsqueeze(0).to(device)

        # Inference
        with torch.no_grad():
            preds = model(img_tensor)
            pred_class = preds.argmax(dim=1).item()

        # Annotate image
        label = class_names[pred_class]
        cv2.putText(img, f"Pred: {label}", (20, 40), cv2.FONT_HERSHEY_SIMPLEX, 
                    1, (0, 255, 0), 2, cv2.LINE_AA)

        # Save result
        save_path = f"runs/detect/exp/{img_name}"
        cv2.imwrite(save_path, img)
        print(f"✅ Saved detection: {save_path}")

    print("✅ Detection complete.")

if __name__ == "__main__":
    detect()
