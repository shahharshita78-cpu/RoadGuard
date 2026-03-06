import os
import random
import shutil
from pathlib import Path

# Paths
val_images = Path("datasets/val/images")
val_labels = Path("datasets/val/labels")
test_images = Path("datasets/test/images")
test_labels = Path("datasets/test/labels")

# Create test folders
os.makedirs(test_images, exist_ok=True)
os.makedirs(test_labels, exist_ok=True)

# How much of val to move into test (e.g. 30%)
test_ratio = 0.3

val_image_files = list(val_images.glob("*.jpg")) + list(val_images.glob("*.png"))
random.shuffle(val_image_files)

split = int(len(val_image_files) * test_ratio)
test_files = val_image_files[:split]

for img_file in test_files:
    label_file = val_labels / (img_file.stem + ".txt")

    # Move image
    shutil.move(str(img_file), str(test_images / img_file.name))

    # Move corresponding label
    if label_file.exists():
        shutil.move(str(label_file), str(test_labels / label_file.name))

print(f"✅ Moved {len(test_files)} images from val -> test")
print(f"Remaining val images: {len(list(val_images.glob('*')))}")
print(f"Test images: {len(list(test_images.glob('*')))}")
