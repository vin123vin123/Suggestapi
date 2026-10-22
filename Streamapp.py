import streamlit as st
import requests
from PIL import Image, ImageDraw, ImageFont
import sqlite3
import io
import os
from datetime import datetime

# --- DATABASE SETUP ---
DB_FILE = "sports_app.db"
IMAGE_DIR = "stored_images"

if not os.path.exists(IMAGE_DIR):
    os.makedirs(IMAGE_DIR)

def init_db():
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS modified_photos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            player_name TEXT,
            caption_text TEXT,
            file_path TEXT,
            created_at TEXT
        )
    ''')
    conn.commit()
    conn.close()

init_db()

# --- APP INTERFACE ---
st.title("🏆 Sports Image Customizer & Poster")
st.write("Fetch player photos from RapidAPI, modify them, and save them directly to your database storage.")

# --- STEP 1: RAPIDAPI CONFIGURATION ---
st.sidebar.header("🔑 API Credentials")
rapidapi_key = st.sidebar.text_input("Enter RapidAPI Key", type="password", value="YOUR_RAPIDAPI_KEY_HERE")

# Mock data button for testing without a live key
use_mock_data = st.sidebar.checkbox("Use Sample Live Image (No API Key Required)", value=True)

player_image_url = None
player_name = "Unknown Player"

if use_mock_data:
    # A generic high-quality placeholder sports image link
    player_image_url = "https://unsplash.com"
    player_name = "Lionel Messi"
    st.info(f"Using sample configuration for **{player_name}**")
else:
    if rapidapi_key and rapidapi_key != "YOUR_RAPIDAPI_KEY_HERE":
        st.subheader("🤖 Fetch from Sports API")
        # Example using API-Football to get a specific player profile image
        api_url = "https://rapidapi.com"
        headers = {
            "X-RapidAPI-Key": rapidapi_key,
            "X-RapidAPI-Host": "://rapidapi.com"
        }
        querystring = {"id":"154","season":"2023"} # ID 154 is Messi in API-Football
        
        if st.button("Fetch Player Photo"):
            try:
                response = requests.get(api_url, headers=headers, params=querystring)
                data = response.json()
                player_data = data["response"][0]["player"]
                player_image_url = player_data["photo"]
                player_name = player_data["name"]
                st.success(f"Successfully loaded image for {player_name}!")
            except Exception as e:
                st.error(f"Failed to fetch data: {e}. Check your API Key or subscription.")

# --- STEP 2: IMAGE MODIFICATION ENGINE ---
if player_image_url:
    st.header("🎨 Modify the Image")
    
    # Download image into server memory
    img_response = requests.get(player_image_url)
    original_image = Image.open(io.BytesIO(img_response.content))
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.write("🔧 **Adjustment Controls**")
        flip_image = st.checkbox("Flip Image Horizontally")
        rotate_deg = st.slider("Rotate Image (Degrees)", 0, 360, 0, step=90)
        
        # Text Overlay Options
        add_text = st.checkbox("Add Text Overlay / Banner", value=True)
        custom_text = st.text_input("Banner Text:", value=f"{player_name} - MVP")
        text_color = st.color_picker("Pick Text Color", "#FFFFFF")
        
    with col2:
        # Processing image adjustments via Pillow
        modified_img = original_image.copy()
        
        if flip_image:
            modified_img = modified_img.transpose(Image.FLIP_LEFT_RIGHT)
        if rotate_deg > 0:
            modified_img = modified_img.rotate(rotate_deg, expand=True)
            
        if add_text and custom_text:
            draw = ImageDraw.Draw(modified_img)
            # Draw a simple text banner at the bottom boundary
            w, h = modified_img.size
            draw.rectangle([(0, h - 40), (w, h)], fill=(0, 0, 0, 180))
            draw.text((10, h - 30), custom_text, fill=text_color)
            
        st.write("🖼️ **Live Preview**")
        st.image(modified_img, use_container_width=True)

    # --- STEP 3: ACTION BUTTONS (DOWNLOAD & DB SAVE) ---
    st.header("💾 Actions & Distribution")
    
    # Prepare image buffer for native download
    img_buffer = io.BytesIO()
    modified_img.save(img_buffer, format="PNG")
    img_bytes = img_buffer.getvalue()
    
    col_btn1, col_btn2 = st.columns(2)
    
    with col_btn1:
        # Client side downloading action
        st.download_button(
            label="⬇️ Download Modified Image",
            data=img_bytes,
            file_name=f"modified_{player_name.lower().replace(' ', '_')}.png",
            mime="image/png"
        )
        
    with col_btn2:
        # Server side Database saving action
        if st.button("🚀 Store in Subdomain DB & File Server"):
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"img_{timestamp}.png"
            full_save_path = os.path.join(IMAGE_DIR, filename)
            
            # 1. Save the file to disk space
            modified_img.save(full_save_path)
            
            # 2. Store only the string metadata/path in SQL database
            conn = sqlite3.connect(DB_FILE)
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO modified_photos (player_name, caption_text, file_path, created_at) VALUES (?, ?, ?, ?)",
                (player_name, custom_text, full_save_path, datetime.now().isoformat())
            )
            conn.commit()
            conn.close()
            
            st.success(f"Stored successfully! File written to `{full_save_path}` and indexed in SQLite.")

# --- STEP 4: DISPLAY STORED IMAGES FROM DATABASE ---
st.header("🗄️ Currently Stored Assets in DB")
conn = sqlite3.connect(DB_FILE)
cursor = conn.cursor()
cursor.execute("SELECT player_name, caption_text, file_path, created_at FROM modified_photos ORDER BY id DESC")
records = cursor.fetchall()
conn.close()

if records:
    for rec in records:
        with st.expander(f"📦 {rec[0]} - Stored at {rec[3][:16]}"):
            st.write(f"**Caption Overlay:** {rec[1]}")
            st.write(f"**DB Pointer Path:** `{rec[2]}`")
            if os.path.exists(rec[2]):
                st.image(rec[2], width=250)
            else:
                st.error("Image file missing from server directory storage.")
else:
    st.info("No records found in database yet. Modify an image above and save it to begin testing.")
