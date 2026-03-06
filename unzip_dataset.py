import zipfile
import os

# Change this to the exact name of your dataset zip file
zip_path = "RDD2020.zip"   # e.g. "RDD2020.zip"
extract_path = "datasets/"

with zipfile.ZipFile(zip_path, 'r') as zip_ref:
    zip_ref.extractall(extract_path)

print("✅ Dataset unzipped into:", extract_path)
