from PIL import Image, ExifTags
import pillow_heif
pillow_heif.register_heif_opener()
import piexif

path = r"C:\Users\lords\OneDrive\Desktop\RoadDamageDetection\IMG_7002.HEIC"

def to_deg_ratio(vals):
    # vals: ((num,den), (num,den), (num,den))
    d = vals[0][0] / vals[0][1]
    m = vals[1][0] / vals[1][1]
    s = vals[2][0] / vals[2][1]
    return d + m/60 + s/3600

img = Image.open(path)

# Path A: standard PIL getexif() (your file showed an int here, so likely won’t work)
gps_info = None
exif = img.getexif()
if exif and len(exif):
    for k, v in exif.items():
        if ExifTags.TAGS.get(k) == "GPSInfo":
            if isinstance(v, dict):
                gps_info = {ExifTags.GPSTAGS.get(t, t): v[t] for t in v}
            else:
                print(f"⚠️ GPSInfo via getexif() is not a dict (type={type(v)}). Will try img.info['exif'].")
            break

if gps_info and "GPSLatitude" in gps_info and "GPSLongitude" in gps_info:
    lat = to_deg_ratio(gps_info["GPSLatitude"])
    lon = to_deg_ratio(gps_info["GPSLongitude"])
    if gps_info.get("GPSLatitudeRef", "N").upper() == "S":
        lat = -lat
    if gps_info.get("GPSLongitudeRef", "E").upper() == "W":
        lon = -lon
    print(f"✅ GPS (getexif): ({lat:.6f}, {lon:.6f})")
else:
    # Path B: EXIF bytes provided via pillow-heif in img.info['exif']
    exif_bytes = img.info.get("exif")
    if not exif_bytes:
        print("❌ No exif bytes found in img.info — EXIF may be stripped.")
    else:
        exif_dict = piexif.load(exif_bytes)
        gps_ifd = exif_dict.get("GPS", {})
        if gps_ifd:
            lat_vals = gps_ifd.get(piexif.GPSIFD.GPSLatitude)
            lon_vals = gps_ifd.get(piexif.GPSIFD.GPSLongitude)
            lat_ref  = gps_ifd.get(piexif.GPSIFD.GPSLatitudeRef, b"N").decode(errors="ignore").upper()
            lon_ref  = gps_ifd.get(piexif.GPSIFD.GPSLongitudeRef, b"E").decode(errors="ignore").upper()
            if lat_vals and lon_vals:
                lat = to_deg_ratio(lat_vals)
                lon = to_deg_ratio(lon_vals)
                if lat_ref == "S":
                    lat = -lat
                if lon_ref == "W":
                    lon = -lon
                print(f"✅ GPS (img.info['exif']): ({lat:.6f}, {lon:.6f})")
            else:
                print("❌ GPS section exists but is missing latitude/longitude values.")
        else:
            print("❌ No GPS section in EXIF bytes.")
