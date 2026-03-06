import os
import xml.etree.ElementTree as ET
from pathlib import Path
import shutil
import random
import yaml

# ----------------------------
# Paths
# ----------------------------
base_path = "datasets/train"   # where India/, Japan/, Czech/ exist
output_train_images = "datasets/train/images"
output_train_labels = "datasets/train/labels"
output_val_images = "datasets/val/images"
output_val_labels = "datasets/val/labels"
yaml_file = "datasets/data.yaml"

# Clean old folders (so we don't duplicate files)
for folder in [output_train_images, output_train_labels, output_val_images, output_val_labels]:
    if os.path.exists(folder):
        shutil.rmtree(folder)

os.makedirs(output_train_images, exist_ok=True)
os.makedirs(output_train_labels, exist_ok=True)
os.makedirs(output_val_images, exist_ok=True)
os.makedirs(output_val_labels, exist_ok=True)

# ----------------------------
# Class mapping (YOLO format needs this)
# ----------------------------
classes = ["D00", "D10", "D20", "D40"]

def convert_annotation(xml_file, label_out):
    """Convert one XML annotation into YOLO txt format"""
    tree = ET.parse(xml_file)
    root = tree.getroot()
    img_width = int(root.find("size/width").text)
    img_height = int(root.find("size/height").text)
    
    lines = []
    for obj in root.findall("object"):
        cls = obj.find("name").text
        if cls not in classes:
            continue
        cls_id = classes.index(cls)
        xmlbox = obj.find("bndbox")
        xmin = float(xmlbox.find("xmin").text)
        ymin = float(xmlbox.find("ymin").text)
        xmax = float(xmlbox.find("xmax").text)
        ymax = float(xmlbox.find("ymax").text)

        # Convert to YOLO format
        x_center = ((xmin + xmax) / 2.0) / img_width
        y_center = ((ymin + ymax) / 2.0) / img_height
        width = (xmax - xmin) / img_width
        height = (ymax - ymin) / img_height

        lines.append(f"{cls_id} {x_center} {y_center} {width} {height}\n")
    
    with open(label_out, "w") as f:
        f.writelines(lines)

# ----------------------------
# Process each country folder
# ----------------------------
countries = ["India", "Japan", "Czech"]
missing_annotations = 0
copy_errors = 0

for country in countries:
    img_dir = os.path.join(base_path, country, "images")
    ann_dir = os.path.join(base_path, country, "annotations", "xmls")  # <-- FIXED

    img_files = []
    for ext in ["*.jpg", "*.JPG", "*.jpeg", "*.JPEG", "*.png", "*.PNG"]:
        img_files.extend(Path(img_dir).glob(ext))

    if not img_files:
        print(f"⚠️ No images found for {country}")
        continue

    random.shuffle(img_files)
    split = max(1, int(0.8 * len(img_files)))  # at least 1 file in val
    train_files = img_files[:split]
    val_files = img_files[split:]

    # Training set
    for img_file in train_files:
        xml_file = os.path.join(ann_dir, img_file.stem + ".xml")
        xml_file_alt = os.path.join(ann_dir, img_file.stem + ".XML")

        if os.path.exists(xml_file):
            xml_path = xml_file
        elif os.path.exists(xml_file_alt):
            xml_path = xml_file_alt
        else:
            missing_annotations += 1
            print(f"⚠️ No annotation found for {img_file.name}")
            continue

        try:
            shutil.copy(str(img_file), output_train_images)
            convert_annotation(xml_path, os.path.join(output_train_labels, img_file.stem + ".txt"))
        except Exception as e:
            print(f"❌ Error copying {img_file}: {e}")
            copy_errors += 1

    # Validation set
    for img_file in val_files:
        xml_file = os.path.join(ann_dir, img_file.stem + ".xml")
        xml_file_alt = os.path.join(ann_dir, img_file.stem + ".XML")

        if os.path.exists(xml_file):
            xml_path = xml_file
        elif os.path.exists(xml_file_alt):
            xml_path = xml_file_alt
        else:
            missing_annotations += 1
            print(f"⚠️ No annotation found for {img_file.name}")
            continue

        try:
            shutil.copy(str(img_file), output_val_images)
            convert_annotation(xml_path, os.path.join(output_val_labels, img_file.stem + ".txt"))
        except Exception as e:
            print(f"❌ Error copying {img_file}: {e}")
            copy_errors += 1

    print(f"📌 {country}: {len(train_files)} train, {len(val_files)} val")

# ----------------------------
# Write data.yaml
# ----------------------------
data_config = {
    "train": "datasets/train/images",
    "val": "datasets/val/images",
    "nc": len(classes),
    "names": classes
}

with open(yaml_file, "w") as f:
    yaml.dump(data_config, f)

# ----------------------------
# Final Summary
# ----------------------------
train_count = len(list(Path(output_train_images).glob("*")))
val_count = len(list(Path(output_val_images).glob("*")))

print("\n✅ All countries processed.")
print(f"✅ Total Train images: {train_count}")
print(f"✅ Total Val images: {val_count}")
print(f"⚠️ Total missing annotations: {missing_annotations}")
print(f"⚠️ Total copy errors: {copy_errors}")
print(f"✅ data.yaml created at {yaml_file}")
