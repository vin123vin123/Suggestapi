import streamlit as st
import requests
from PIL import Image, ImageDraw
import sqlite3
import io
import os
from datetime import datetime

# --- DATABASE & STORAGE SETUP ---
DB_FILE = "sports_app.db"
IMAGE_DIR = "stored_images"

if not os.path.exists(IMAGE_DIR):
    os.makedirs(IMAGE_DIR)

def init_db():
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    # Table for storing customized creations
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS modified_photos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            player_name TEXT,
            caption_text TEXT,
            file_path TEXT,
            created_at TEXT
        )
    ''')
    # Cache table to store raw API data so we never fetch the same player twice
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS api_cache (
            player_id TEXT PRIMARY KEY,
            player_name TEXT,
            image_url TEXT,
            cached_at TEXT
        )
    ''')
    conn.commit()
    conn.close()

init_db()

# --- SAFE API FETCHING FUNCTIONS (THE CACHE LAYER) ---
@st.cache_data(ttl=3600)  # Strategy 1: In-memory cache for 1 hour to prevent rapid refresh hits
def fetch_from_rapidapi(player_id, api_key):
    """Fetches player image while checking the Database Cache first to protect free limits."""
    
    # Strategy 2: Persistent DB Cache Check
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("SELECT player_name, image_url FROM api_cache WHERE player_id = ?", (str(player_id),))
    row = cursor.fetchone()
    conn.close()
    
    if row:
        st.toast("⚡ Retrieved instantly from DB cache (0 API calls used!)", icon="🛡️")
        return {"name": row[0], "photo": row[1], "source": "Database Cache"}

    # If not in cache, execute the live API call
    api_url = "https://rapidapi.com"
    headers = {
        "X-RapidAPI-Key": api_key,
        "X-RapidAPI-Host": "://rapidapi.com"
    }
    querystring = {"id": str(player_id), "season": "2026"}
    
    try:
        response = requests.get(api_url, headers=headers, params=querystring, timeout=10)
        data = response.json()
        
        player_data = data["response"][0]["player"]
        p_name = player_data["name"]
        p_photo = player_data["photo"]
        
        # Save to cache so next time it is free
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        cursor.execute(
            "INSERT OR REPLACE INTO api_cache (player_id, player_name, image_url, cached_at) VALUES (?, ?, ?, ?)",
            (str(player_id), p_name, p_photo, datetime.now().isoformat())
        )
        conn.commit()
        conn.close()
        
        st.toast("🌐 Live API request executed.", icon="📡")
        return {"name": p_name, "photo": p_photo, "source": "Live RapidAPI"}
        
    except Exception as e:
        st.error(f"API Error or player not found. Error detail: {e}")
        return None

# --- APP INTERFACE ---
st.title("🏆 Safe-Limit Sports Image Customizer")
st.write("This app uses a double-caching layer architecture to guarantee your RapidAPI free tiers don't run out.")

# --- STEP 1: API CONFIGURATION & CALL PROTECTION ---
st.sidebar.header("🔑 API Credentials & Safety")
rapidapi_key = st.sidebar.text_input("Enter RapidAPI Key", type="password", value="YOUR_RAPIDAPI_KEY_HERE")
use_mock_data = st.sidebar.checkbox("Use Sample Image Mode", value=True)

player_image_url = None
player_name = "Unknown Player"

if use_mock_data:
    player_image_url = "https://unsplash.com"
    player_name = "Lionel Messi"
    st.info(f"Using sample configuration for **{player_name}** (0 API overhead)")
else:
    if rapidapi_key and rapidapi_key != "YOUR_RAPIDAPI_KEY_HERE":
        st.subheader("🤖 Fetch from Sports API")
        
        # Player ID input (e.g., 154 for Messi)
        target_player_id = st.text_input("Enter Football Player ID to Fetch:", value="154")
        
        if st.button("Fetch Player Photo Securely"):
            with st.spinner("Checking cache and processing request..."):
                result = fetch_from_rapidapi(target_player_id, rapidapi_key)
                if result:
                    player_image_url = result["photo"]
                    player_name = result["name"]
                    st.success(f"Loaded {player_name} via {result['source']}")
    else:
        st.warning("Please enter your RapidAPI Key in the sidebar or check 'Use Sample Image Mode' to try it out.")

# --- STEP 2: IMAGE MODIFICATION ENGINE (SECURED FROM CRASHES) ---
if player_image_url:
    st.header("🎨 Modify the Image")
    
    try:
        # Add headers to masquerade as a browser to avoid 403 Forbidden image downloads
        download_headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        }
        
        # Safe request download
        img_response = requests.get(player_image_url, headers=download_headers, timeout=10)
        
        if img_response.status_code == 200:
            original_image = Image.open(io.BytesIO(img_response.content))
            
            col1, col2 = st.columns(2)
            
            with col1:
                st.write("🔧 **Adjustment Controls**")
                flip_image = st.checkbox("Flip Image Horizontally")
                rotate_deg = st.slider("Rotate Image (Degrees)", 0, 360, 0, step=90)
                
                add_text = st.checkbox("Add Text Overlay / Banner", value=True)
                custom_text = st.text_input("Banner Text:", value=f"{player_name} - MVP")
                text_color = st.color_picker("Pick Text Color", "#FFFFFF")
                
            with col2:
                modified_img = original_image.copy()
                
                if flip_image:
                    modified_img = modified_img.transpose(Image.FLIP_LEFT_RIGHT)
                if rotate_deg > 0:
                    modified_img = modified_img.rotate(rotate_deg, expand=True)
                    
                if add_text and custom_text:
                    draw = ImageDraw.Draw(modified_img)
                    w, h = modified_img.size
                    draw.rectangle([(0, h - 40), (w, h)], fill=(0, 0, 0, 180))
                    draw.text((10, h - 30), custom_text, fill=text_color)
                    
                st.write("🖼️ **Live Preview**")
                st.image(modified_img, use_container_width=True)

            # --- STEP 3: ACTION BUTTONS (DOWNLOAD & DB SAVE) ---
            st.header("💾 Actions & Distribution")
            
            img_buffer = io.BytesIO()
            modified_img.save(img_buffer, format="PNG")
            img_bytes = img_buffer.getvalue()
            
            col_btn1, col_btn2 = st.columns(2)
            
            with col_btn1:
                st.download_button(
                    label="⬇️ Download Modified Image",
                    data=img_bytes,
                    file_name=f"modified_{player_name.lower().replace(' ', '_')}.png",
                    mime="image/png"
                )
                
            with col_btn2:
                if st.button("🚀 Store in Subdomain DB & File Server"):
                    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                    filename = f"img_{timestamp}.png"
                    full_save_path = os.path.join(IMAGE_DIR, filename)
                    
                    modified_img.save(full_save_path)
                    
                    conn = sqlite3.connect(DB_FILE)
                    cursor = conn.cursor()
                    cursor.execute(
                        "INSERT INTO modified_photos (player_name, caption_text, file_path, created_at) VALUES (?, ?, ?, ?)",
                        (player_name, custom_text, full_save_path, datetime.now().isoformat())
                    )
                    conn.commit()
                    conn.close()
                    
                    st.success(f"Stored successfully! Indexed in SQLite. View history below.")
        
        else:
            st.error(f"Could not download the file image asset. Server responded with Status Code: {img_response.status_code}")
            if img_response.status_code == 403:
                st.info("The image hosting provider is rejecting automated requests. Use sample mode or cross-verify image URLs.")

    except Exception as image_err:
        st.error(f"Error decoding image file data: {image_err}")

# --- STEP 4: DISPLAY STORED IMAGES FROM DATABASE ---
st.header("🗄️ Currently Stored Assets in DB")
conn = sqlite3.connect(DB_FILE)
cursor = conn.cursor()
cursor.execute("SELECT player_name, caption_text, file_path, created_at FROM modified_photos ORDER BY id DESC")
records = cursor.fetchall()
conn.close()

if records:
    for rec in records:
        with st.expander(f"📦 {rec[0]} - Custom Banner: '{rec[1]}'"):
            st.write(f"**DB Pointer Path:** `{rec[2]}`")
            if os.path.exists(rec[2]):
                st.image(rec[2], width=250)
            else:
                st.error("Image file missing from server storage folder.")
else:
    st.info("No records found in database yet. Modify an image above and save it to begin testing.")
