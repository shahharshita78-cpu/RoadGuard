import os
import random
import cv2
from pathlib import Path

# Paths
images_path = "datasets/train/images"
labels_path = "datasets/train/labels"
classes = ["D00", "D10", "D20", "D40"]  # same as your data.yaml

# Pick random image
image_files = list(Path(images_path).glob("*.jpg")) + list(Path(images_path).glob("*.png"))
random.shuffle(image_files)

for img_path in image_files[:5]:  # show 5 samples
    label_path = os.path.join(labels_path, img_path.stem + ".txt")

    img = cv2.imread(str(img_path))
    h, w, _ = img.shape

    # Draw bounding boxes if label exists
    if os.path.exists(label_path):
        with open(label_path, "r") as f:
            for line in f.readlines():
                cls_id, x_center, y_center, bw, bh = map(float, line.split())
                cls_id = int(cls_id)

                # Convert YOLO format back to pixel coordinates
                x_center *= w
                y_center *= h
                bw *= w
                bh *= h

                x1 = int(x_center - bw / 2)
                y1 = int(y_center - bh / 2)
                x2 = int(x_center + bw / 2)
                y2 = int(y_center + bh / 2)

                cv2.rectangle(img, (x1, y1), (x2, y2), (0, 255, 0), 2)
                cv2.putText(img, classes[cls_id], (x1, y1 - 5),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)

    # Show image
    cv2.imshow("Sample", img)
    cv2.waitKey(0)

cv2.destroyAllWindows()
