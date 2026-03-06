from PIL import Image, ExifTags
import pillow_heif
pillow_heif.register_heif_opener()
import piexif

# Your HEIC image path
path = r"C:\Users\lords\OneDrive\Desktop\RoadDamageDetection\IMG_7002.HEIC"

# Open image
img = Image.open(path)

def show_exif(img):
    print("---- getexif() ----")
    exif = img.getexif()
    if exif and len(exif):
        d = {ExifTags.TAGS.get(k, k): v for k, v in exif.items()}
        print("Keys:", list(d.keys()))
        print("GPSInfo present?", 'GPSInfo' in d)
    else:
        print("No EXIF via getexif()")

    print("---- img.info['exif'] ----")
    exif_bytes = img.info.get("exif")
    if exif_bytes:
        exif_dict = piexif.load(exif_bytes)
        print("Sections:", exif_dict.keys())
        print("GPS section keys:", list(exif_dict.get('GPS', {}).keys()))
    else:
        print("No exif in img.info")

# Run the function
show_exif(img)
