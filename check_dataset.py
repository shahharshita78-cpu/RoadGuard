import os
from pathlib import Path

# Paths
train_images = Path("datasets/train/images")
train_labels = Path("datasets/train/labels")
val_images = Path("datasets/val/images")
val_labels = Path("datasets/val/labels")
test_images = Path("datasets/test/images")
test_labels = Path("datasets/test/labels")

# Classes (must match data.yaml)
classes = ["D00", "D10", "D20", "D40"]

def check_split(images_path, labels_path, split_name):
    images = list(images_path.glob("*.jpg")) + list(images_path.glob("*.png"))
    missing_labels = []
    empty_labels = []
    invalid_labels = []

    for img in images:
        label_file = labels_path / (img.stem + ".txt")
        if not label_file.exists():
            missing_labels.append(img.name)
        else:
            with open(label_file, "r") as f:
                lines = f.readlines()
                if len(lines) == 0:
                    empty_labels.append(img.name)
                else:
                    for line in lines:
                        try:
                            cls_id = int(line.split()[0])
                            if cls_id < 0 or cls_id >= len(classes):
                                invalid_labels.append((img.name, line.strip()))
                        except:
                            invalid_labels.append((img.name, line.strip()))

    print(f"\n📂 {split_name} check:")
    print(f"  Total images: {len(images)}")
    print(f"  Missing labels: {len(missing_labels)}")
    print(f"  Empty labels: {len(empty_labels)}")
    print(f"  Invalid class IDs: {len(invalid_labels)}")

    if missing_labels:
        print(f"  ⚠️ Example missing: {missing_labels[:5]}")
    if empty_labels:
        print(f"  ⚠️ Example empty: {empty_labels[:5]}")
    if invalid_labels:
        print(f"  ⚠️ Example invalid: {invalid_labels[:5]}")

# Run checks
check_split(train_images, train_labels, "Train")
check_split(val_images, val_labels, "Val")
check_split(test_images, test_labels, "Test")
