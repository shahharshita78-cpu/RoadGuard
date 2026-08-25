import streamlit as st
from ultralytics import YOLO
from pathlib import Path
import os

# ----------------- LOGIN -----------------
def login():
    st.title("🔐 Road Damage Detection - Login")
    username = st.text_input("Username")
    password = st.text_input("Password", type="password")
    if st.button("Login"):
        # Legacy authentication check (credentials removed for security hygiene)
        if username and password:
            st.session_state["logged_in"] = True
            st.session_state["username"] = username
        else:
            st.error("❌ Please enter a username and password")


# ----------------- MAIN APP -----------------
def main_app():
    st.title("🛣️ Road Damage Detection System")
    st.write(f"👋 Welcome, **{st.session_state['username']}**!")

    # Confidence slider
    conf_thresh = st.slider("Confidence Threshold", 0.1, 1.0, 0.5, 0.05)

    # Upload image(s)
    uploaded_files = st.file_uploader(
        "Upload road images", type=["jpg", "png", "jpeg"], accept_multiple_files=True
    )

    if uploaded_files and st.button("Run Detection"):
        model_path = "runs/detect/train6/weights/best.pt"  # adjust to your model path
        if not os.path.exists(model_path):
            st.error("❌ Trained model not found! Check the path.")
            return

        model = YOLO(model_path)

        for uploaded_file in uploaded_files:
            # Save uploaded file temporarily
            temp_path = Path("temp") / uploaded_file.name
            os.makedirs(temp_path.parent, exist_ok=True)
            with open(temp_path, "wb") as f:
                f.write(uploaded_file.getbuffer())

            st.image(str(temp_path), caption="Uploaded Image", use_column_width=True)

            # Run YOLO detection
            results = model.predict(
                source=str(temp_path),
                conf=conf_thresh,
                save=True,
                project="runs/detect",
                name="streamlit_results",
                exist_ok=True,
            )

            # Show detection result
            save_dir = results[0].save_dir
            saved_files = list(Path(save_dir).glob("*.jpg"))

            if saved_files:
                st.image(str(saved_files[0]), caption="Detection Result", use_column_width=True)
                with open(saved_files[0], "rb") as f:
                    st.download_button("⬇️ Download Result", f, file_name="detection_result.jpg")
            else:
                st.warning("⚠️ Could not find result image. Check YOLO output folder.")


# ----------------- APP LOGIC -----------------
if "logged_in" not in st.session_state:
    st.session_state["logged_in"] = False

if not st.session_state["logged_in"]:
    login()
else:
    main_app()
