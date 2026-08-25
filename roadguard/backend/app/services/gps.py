"""
GPS / EXIF extraction service.

Ported from app_v3.py with generalised function signatures (operates on
raw bytes rather than local file paths) and improved documentation.

Supports:
  - JPEG / PNG via PIL getexif()
  - HEIC / HEIF via img.info['exif'] + piexif (requires pillow-heif)
"""
from __future__ import annotations

import io
from typing import Optional, Tuple

from PIL import Image, ExifTags


def _rational_to_decimal(vals) -> float:
    """Convert an EXIF rational tuple ((d_n,d_d),(m_n,m_d),(s_n,s_d)) to decimal degrees."""
    d = vals[0][0] / vals[0][1]
    m = vals[1][0] / vals[1][1]
    s = vals[2][0] / vals[2][1]
    return d + m / 60.0 + s / 3600.0


def extract_gps_from_bytes(file_bytes: bytes) -> Optional[Tuple[float, float]]:
    """
    Return (latitude, longitude) decimal degrees if EXIF GPS data is present.

    Tries two paths:
      Path A — PIL getexif() (works for JPEG/PNG with embedded IFD GPS dict)
      Path B — img.info['exif'] parsed by piexif (works for HEIC/HEIF)

    Returns None if GPS metadata is absent or cannot be parsed.
    """
    try:
        img = Image.open(io.BytesIO(file_bytes))

        # Path A: standard PIL IFD dictionary
        exif = img.getexif()
        if exif and len(exif):
            tags = {ExifTags.TAGS.get(k, k): v for k, v in exif.items()}
            gps_info = tags.get("GPSInfo")
            if isinstance(gps_info, dict):
                gps = {ExifTags.GPSTAGS.get(t, t): gps_info[t] for t in gps_info}
                if "GPSLatitude" in gps and "GPSLongitude" in gps:
                    lat = _rational_to_decimal(gps["GPSLatitude"])
                    lon = _rational_to_decimal(gps["GPSLongitude"])
                    if gps.get("GPSLatitudeRef", "N").upper() == "S":
                        lat = -lat
                    if gps.get("GPSLongitudeRef", "E").upper() == "W":
                        lon = -lon
                    return (lat, lon)

        # Path B: raw EXIF bytes via piexif (HEIC/HEIF)
        exif_bytes = img.info.get("exif")
        if exif_bytes:
            import piexif
            exif_dict = piexif.load(exif_bytes)
            gps_ifd = exif_dict.get("GPS", {})
            lat_vals = gps_ifd.get(piexif.GPSIFD.GPSLatitude)
            lon_vals = gps_ifd.get(piexif.GPSIFD.GPSLongitude)
            lat_ref = gps_ifd.get(piexif.GPSIFD.GPSLatitudeRef, b"N").decode(errors="ignore").upper()
            lon_ref = gps_ifd.get(piexif.GPSIFD.GPSLongitudeRef, b"E").decode(errors="ignore").upper()
            if lat_vals and lon_vals:
                lat = _rational_to_decimal(lat_vals)
                lon = _rational_to_decimal(lon_vals)
                if lat_ref == "S":
                    lat = -lat
                if lon_ref == "W":
                    lon = -lon
                return (lat, lon)

    except Exception:
        pass

    return None


def reverse_geocode(lat: float, lon: float) -> Optional[str]:
    """
    Return a human-readable address for the given coordinates using Nominatim.

    Returns None if geocoding fails or the service is unavailable.
    """
    try:
        from geopy.geocoders import Nominatim
        geolocator = Nominatim(user_agent="roadguard_platform")
        location = geolocator.reverse((lat, lon), timeout=10, language="en")
        return location.address if location else None
    except Exception:
        return None
