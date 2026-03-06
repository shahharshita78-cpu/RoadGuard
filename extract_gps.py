from PIL import Image, ExifTags
import pillow_heif
pillow_heif.register_heif_opener()

path = r"C:\Users\lords\OneDrive\Desktop\RoadDamageDetection\IMG_7002.HEIC"
img = Image.open(path)
exif = img.getexif()

gps_info = None
for key, val in exif.items():
    if ExifTags.TAGS.get(key) == 'GPSInfo':
        # Ensure 'val' is a dictionary-like object, not just an int
        if isinstance(val, dict):
            gps_info = {ExifTags.GPSTAGS.get(t, t): val[t] for t in val}
        elif isinstance(val, int):
            print(f"⚠️ Skipping non-dict GPSInfo value: {val}")
        else:
            print(f"⚠️ Unhandled GPSInfo type: {type(val)}")
        break

if gps_info:
    def to_deg(value):
        d = value[0][0] / value[0][1]
        m = value[1][0] / value[1][1]
        s = value[2][0] / value[2][1]
        return d + (m / 60.0) + (s / 3600.0)

    lat = to_deg(gps_info['GPSLatitude'])
    lon = to_deg(gps_info['GPSLongitude'])
    if gps_info.get('GPSLatitudeRef') in ['S', 's']:
        lat = -lat
    if gps_info.get('GPSLongitudeRef') in ['W', 'w']:
        lon = -lon

    print(f"✅ GPS Coordinates: ({lat:.6f}, {lon:.6f})")
else:
    print("❌ No usable GPS info found in EXIF.")
