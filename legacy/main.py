import os

def train_model():
    os.system("python models/yolov5/train.py --img 640 --batch 16 --epochs 50 --data datasets/data.yaml --weights yolov5s.pt")

def detect_images():
    os.system("python models/yolov5/detect.py --weights runs/train/exp/weights/best.pt --source datasets/val/images")

if __name__ == "__main__":
    print("1. Train Model\n2. Run Detection")
    choice = input("Enter choice: ")
    if choice == "1":
        train_model()
    else:
        detect_images()
