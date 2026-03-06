# app_v3.py
import io
import os
import sqlite3
from pathlib import Path
from datetime import datetime
from typing import Optional

import streamlit as st
import pydeck as pdk
import pandas as pd
from ultralytics import YOLO
from PIL import Image, ExifTags
import pillow_heif  # HEIC/HEIF support for Pillow
pillow_heif.register_heif_opener()
import piexif
from geopy.geocoders import Nominatim

# -------------------------------
# Helpers: GPS extraction + reverse geocoding
# -------------------------------
def _to_deg_tuple(vals):
    """Convert EXIF rational tuples to decimal degrees."""
    d = vals[0][0] / vals[0][1]
    m = vals[1][0] / vals[1][1]
    s = vals[2][0] / vals[2][1]
    return d + m / 60 + s / 3600

def get_image_gps_from_bytes(file_bytes: bytes):
    """
    Return (lat, lon) if EXIF GPS exists (JPG/PNG/HEIC supported).
    Tries PIL getexif() and img.info['exif'] (HEIC path via pillow-heif + piexif).
    """
    try:
        img = Image.open(io.BytesIO(file_bytes))

        # Path A: standard getexif()
        exif = img.getexif()
        if exif and len(exif):
            exif_data = {ExifTags.TAGS.get(k, k): v for k, v in exif.items()}
            gps_info = exif_data.get("GPSInfo")
            if isinstance(gps_info, dict):
                gps = {ExifTags.GPSTAGS.get(t, t): gps_info[t] for t in gps_info}
                if "GPSLatitude" in gps and "GPSLongitude" in gps:
                    lat = _to_deg_tuple(gps["GPSLatitude"])
                    lon = _to_deg_tuple(gps["GPSLongitude"])
                    if gps.get("GPSLatitudeRef", "N").upper() == "S":
                        lat = -lat
                    if gps.get("GPSLongitudeRef", "E").upper() == "W":
                        lon = -lon
                    return (lat, lon)

        # Path B: EXIF bytes (common for HEIC)
        exif_bytes = img.info.get("exif")
        if exif_bytes:
            exif_dict = piexif.load(exif_bytes)
            gps_ifd = exif_dict.get("GPS", {})
            lat_vals = gps_ifd.get(piexif.GPSIFD.GPSLatitude)
            lon_vals = gps_ifd.get(piexif.GPSIFD.GPSLongitude)
            lat_ref  = gps_ifd.get(piexif.GPSIFD.GPSLatitudeRef, b"N").decode(errors="ignore").upper()
            lon_ref  = gps_ifd.get(piexif.GPSIFD.GPSLongitudeRef, b"E").decode(errors="ignore").upper()
            if lat_vals and lon_vals:
                lat = _to_deg_tuple(lat_vals)
                lon = _to_deg_tuple(lon_vals)
                if lat_ref == "S":
                    lat = -lat
                if lon_ref == "W":
                    lon = -lon
                return (lat, lon)
        return None
    except Exception:
        return None

_geocoder = Nominatim(user_agent="road_damage_app")

def latlon_to_address(lat: float, lon: float) -> Optional[str]:
    """Reverse geocode to a human-readable address. Returns None on failure."""
    try:
        loc = _geocoder.reverse((lat, lon), timeout=10, language="en")
        return loc.address if loc else None
    except Exception:
        return None

# -------------------------------
# DB: self-healing schema
# -------------------------------
def ensure_schema(conn: sqlite3.Connection):
    cur = conn.cursor()
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS detections (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            image TEXT,
            lat REAL,
            lon REAL,
            address TEXT,
            cls TEXT,
            conf REAL,
            timestamp TEXT
        )
        """
    )
    # Make sure 'address' column exists (for older DBs)
    cur.execute("PRAGMA table_info(detections)")
    cols = {row[1] for row in cur.fetchall()}
    if "address" not in cols:
        try:
            cur.execute("ALTER TABLE detections ADD COLUMN address TEXT")
        except Exception:
            pass
    conn.commit()

# -------------------------------
# Page & model setup
# -------------------------------
st.set_page_config(page_title="AI Road Damage Detection", layout="wide")

MODEL_PATH = "runs/detect/train6/weights/best.pt"  # update if your best run folder differs
model = YOLO(MODEL_PATH)

# SQLite
conn = sqlite3.connect("detections.db", check_same_thread=False)
ensure_schema(conn)
cursor = conn.cursor()

# -------------------------------
# Sidebar: simple assistant
# -------------------------------
st.sidebar.title("💬 RoadBot Assistant")

if "chat_history" not in st.session_state:
    st.session_state.chat_history = []

q = st.sidebar.text_input("Ask something about road detection:")
if q:
    a = "This system detects potholes and cracks using a fine-tuned YOLOv8 model."
    lq = q.lower()
    if "accuracy" in lq or "precision" in lq:
        a = "Current run achieved ~0.68 precision and ~0.54 recall. Improve with more data, augmentation, and longer fine-tuning."
    elif "map" in lq or "gps" in lq:
        a = "If the image has GPS in EXIF (e.g., phone camera), detections are logged and plotted on the map. You can also enter location manually."
    elif "classes" in lq:
        a = "We trained on four classes (D00, D10, D20, D40) covering common crack/pothole types."
    elif "how" in lq:
        a = "YOLOv8 predicts bounding boxes for damages. You can tune confidence, epochs, and augmentations for better performance."
    st.session_state.chat_history.append((q, a))

for q_, a_ in st.session_state.chat_history:
    st.sidebar.write(f"🧑‍💻 You: {q_}")
    st.sidebar.write(f"🤖 RoadBot: {a_}")

# -------------------------------
# Main UI with Tabs
# -------------------------------
st.title("🛣️ Smart Road Damage Detection System")
st.markdown("Detect road damages in **images** or **videos**, log GPS & view them on a map.")

conf_thresh = st.slider("Confidence Threshold", 0.1, 1.0, 0.5, 0.05)

tab_img, tab_vid = st.tabs(["🖼️ Image", "🎥 Video"])

# -------------------------------
# IMAGE TAB
# -------------------------------
with tab_img:
    uploaded_file = st.file_uploader("📸 Upload Road Image", type=["jpg", "jpeg", "png", "heic", "heif"], key="image_uploader")

    if uploaded_file:
        file_bytes = uploaded_file.getvalue()

        # Save original upload
        uploads_dir = Path("uploads")
        uploads_dir.mkdir(parents=True, exist_ok=True)
        raw_path = uploads_dir / uploaded_file.name
        with open(raw_path, "wb") as f:
            f.write(file_bytes)

        # Show uploaded image
        st.image(uploaded_file, caption="Uploaded Image", use_container_width=True)

        # Get GPS (if present)
        gps = get_image_gps_from_bytes(file_bytes)
        address = None
        if gps:
            st.success(f"📍 Image GPS Location: {gps}")
            address = latlon_to_address(*gps)
            if address:
                st.info(f"📫 Address: {address}")
        else:
            st.warning("⚠️ No GPS data found in image metadata.")
            with st.expander("Manually enter location (optional)"):
                m_lat = st.number_input("Latitude", value=0.0, format="%.6f", key="img_lat")
                m_lon = st.number_input("Longitude", value=0.0, format="%.6f", key="img_lon")
                use_manual = st.checkbox("Use manual location", key="img_use_manual")
                if use_manual:
                    gps = (m_lat, m_lon)
                    st.success(f"📍 Using manual GPS: {gps}")
                    address = latlon_to_address(*gps)
                    if address:
                        st.info(f"📫 Address: {address}")

        # If HEIC/HEIF, convert to JPG for YOLO
        yolo_path = raw_path
        if raw_path.suffix.lower() in {".heic", ".heif"}:
            try:
                img_rgb = Image.open(raw_path).convert("RGB")
                yolo_path = raw_path.with_suffix(".jpg")
                img_rgb.save(yolo_path, "JPEG", quality=95)
            except Exception as e:
                st.error(f"Failed to convert HEIC to JPG: {e}")

        # Run YOLO inference
        st.write("🔍 Detecting road damages…")
        results = model.predict(source=str(yolo_path), conf=conf_thresh, save=True)

        # Find YOLO's actual saved image (YOLO may rename to image0.jpg etc.)
        save_dir = Path(results[0].save_dir)
        candidates = []
        for pattern in ("*.jpg", "*.jpeg", "*.png", "*.bmp"):
            candidates.extend(save_dir.glob(pattern))

        result_img_path = None
        stem = yolo_path.stem.lower()
        for p in candidates:
            if p.stem.lower() == stem or p.stem.lower().startswith("image0"):
                result_img_path = p
                break
        if result_img_path is None and candidates:
            result_img_path = candidates[0]

        if result_img_path and result_img_path.exists():
            st.image(str(result_img_path), caption="Detection Result", use_container_width=True)

            # Save detection metadata if we have a location
            if gps:
                count = 0
                for box in results[0].boxes:
                    cls_id = int(box.cls[0])
                    conf_val = float(box.conf[0])
                    cls_name = model.names[cls_id]
                    cursor.execute(
                        "INSERT INTO detections (image, lat, lon, address, cls, conf, timestamp) VALUES (?, ?, ?, ?, ?, ?, ?)",
                        (
                            raw_path.name,
                            gps[0],
                            gps[1],
                            address if address else None,
                            cls_name,
                            conf_val,
                            datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                        ),
                    )
                    count += 1
                conn.commit()
                st.success(f"✅ Logged {count} detection(s) to database!")
        else:
            st.error("❌ Could not find result image. Check YOLO output folder.")

# -------------------------------
# VIDEO TAB
# -------------------------------
def run_video_detection(model, video_path: Path, conf: float = 0.5, vid_stride: int = 1):
    """
    Runs YOLOv8 on a video file and returns the path to the annotated video.
    """
    results = model.predict(
        source=str(video_path),
        conf=conf,
        save=True,         # saves annotated video/frames to runs/detect/predict*
        vid_stride=vid_stride,
        stream=False
    )
    save_dir = Path(results[0].save_dir)
    out_video = None
    mp4s = list(save_dir.glob("*.mp4"))
    if mp4s:
        out_video = mp4s[0]
    else:
        mp4s = list(save_dir.rglob("*.mp4"))
        if mp4s:
            out_video = mp4s[0]
    return out_video

with tab_vid:
    st.write("Upload a road video to detect damages frame-by-frame.")
    video_file = st.file_uploader("🎥 Upload Video", type=["mp4", "mov", "avi", "mkv"], key="video_uploader")
    vid_stride = st.slider("Frame Stride (higher = faster, fewer frames)", 1, 10, 1, 1, key="vid_stride")

    # Optional: manual video location to log a summary row
    with st.expander("Optional: Set video location (for logging)"):
        v_lat = st.number_input("Latitude", value=0.0, format="%.6f", key="vid_lat")
        v_lon = st.number_input("Longitude", value=0.0, format="%.6f", key="vid_lon")
        use_video_loc = st.checkbox("Use this location for video summary logging", key="vid_use_loc")
        v_address = None
        if use_video_loc:
            v_address = latlon_to_address(v_lat, v_lon)
            if v_address:
                st.info(f"📫 Address: {v_address}")

    if video_file is not None:
        videos_dir = Path("videos")
        videos_dir.mkdir(parents=True, exist_ok=True)
        raw_video_path = videos_dir / video_file.name
        with open(raw_video_path, "wb") as f:
            f.write(video_file.getbuffer())

        st.video(str(raw_video_path))
        if st.button("Run detection on video"):
            st.info("Processing video… this may take time depending on length and stride.")
            out_path = run_video_detection(model, raw_video_path, conf_thresh, vid_stride)
            if out_path and out_path.exists():
                st.success("✅ Detection complete.")
                st.video(str(out_path))

                # Optional: log a single summary row for the video
                if use_video_loc:
                    cursor.execute(
                        "INSERT INTO detections (image, lat, lon, address, cls, conf, timestamp) VALUES (?, ?, ?, ?, ?, ?, ?)",
                        (
                            raw_video_path.name,
                            v_lat,
                            v_lon,
                            v_address if v_address else None,
                            "VIDEO_SUMMARY",
                            1.0,
                            datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                        ),
                    )
                    conn.commit()
                    st.success("📝 Logged video summary location to database.")
            else:
                st.error("❌ Could not find the annotated video output.")

# -------------------------------
# Map of detections + CSV export
# -------------------------------
st.markdown("---")
st.header("🗺️ Detected Locations Map")

cursor.execute("SELECT image, lat, lon, address, cls, conf, timestamp FROM detections")
rows = cursor.fetchall()

if rows:
    df = pd.DataFrame(rows, columns=["image", "lat", "lon", "address", "class", "confidence", "time"])
    # Map
    map_data = df[["lat", "lon", "class", "confidence", "time", "address"]].to_dict("records")
    st.pydeck_chart(
        pdk.Deck(
            map_style="mapbox://styles/mapbox/streets-v11",
            initial_view_state=pdk.ViewState(
                latitude=map_data[-1]["lat"], longitude=map_data[-1]["lon"], zoom=12, pitch=45
            ),
            layers=[
                pdk.Layer(
                    "ScatterplotLayer",
                    data=map_data,
                    get_position="[lon, lat]",
                    get_color="[255, 0, 0, 160]",
                    get_radius=60,
                    pickable=True,
                ),
            ],
            tooltip={"text": "Class: {class}\nConf: {confidence}\nTime: {time}\n{address}"},
        )
    )

    # CSV export
    st.subheader("⬇️ Export detections")
    st.download_button(
        "Download detections.csv",
        df.to_csv(index=False).encode(),
        "detections.csv",
        "text/csv",
    )
else:
    st.info("No detected locations logged yet.")
