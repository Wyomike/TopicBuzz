import streamlit as st
import networkx as nx
import pickle
import os
import json
import random
import datetime
import math
import pandas as pd
import streamlit.components.v1 as components
from supabase import create_client, Client

# --- PAGE CONFIG ---
st.set_page_config(layout="wide", page_title="Topic Buzz Explorer")

# --- NAVIGATION SETUP ---
# Streamlit automatically handles pages if they are in a 'pages/' directory.
# This main file (app.py) serves as the landing page.

st.title("Topic Buzz Explorer 🐝")

st.markdown("""
## Welcome to the Mastodon Topic Explorer

This application visualizes the complex web of interactions between users and topics on the Fediverse.

### 🗺️ **Graph Explorer**
Dive into the network. Visualize how users connect to topics and discover community hubs.
* **Search** by User ID or Topic.
* **Filter** by connection strength and depth.
* **Analyze** related entities.

### 📊 **Topic Analytics** (Coming Soon)
Deep dive into specific topic trends, keyword clouds, and sentiment analysis over time.

### 👤 **User Profiler** (Coming Soon)
Analyze individual user behavior, their "topic fingerprint," and activity timeline.

---

**👈 Select a page from the sidebar to get started.**
""")

# --- SHARED DATA LOADER ---
# We keep the data loading logic here so it can be imported by pages if needed,
# OR we can trust Streamlit's cache to handle it across pages if we use the same function signature.

CACHE_FILE = "mastodon_network.pkl"
LABELS_FILE = "topic_labels.json"

SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY")

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

CACHE_FILE = "mastodon_network.pkl"
BUCKET = "topic_assets"

@st.cache_resource
def ensure_local_file(filename):
    """
    Checks if a file exists locally. If not, attempts to download it 
    from Supabase Storage and save it to disk.
    """
    if os.path.exists(filename):
        return True
        
    print(f"☁️ File {filename} not found locally. Downloading from Supabase...")
    try:
        # 1. Get the bytes from Supabase
        file_bytes = supabase.storage.from_(BUCKET).download(filename)
        
        # 2. Save bytes to local disk
        with open(filename, "wb") as f: # 'wb' = Write Binary
            f.write(file_bytes)
            
        print(f"✅ Downloaded {filename}")
        return True
    except Exception as e:
        st.error(f"❌ Failed to download {filename} from bucket '{BUCKET}': {e}")
        return False

@st.cache_resource
def load_data():
    data = {"G": None, "labels": {}, "min_ts": 0, "max_ts": 1}
    
    # 1. LOAD GRAPH (Pickle)
    if ensure_local_file(CACHE_FILE):
        try:
            with open(CACHE_FILE, 'rb') as f:
                data["G"] = pickle.load(f)
                
            # Pre-calculate Time Range
            G = data["G"]
            timestamps = [
                d['last_timestamp'] 
                for u, v, d in G.edges(data=True) 
                if 'last_timestamp' in d and d['last_timestamp'] > 0
            ]
            if timestamps:
                data["min_ts"] = min(timestamps)
                data["max_ts"] = max(timestamps)
        except Exception as e:
            st.error(f"Error loading pickle file: {e}")

    # 2. LOAD LABELS (JSON)
    if ensure_local_file(LABELS_FILE):
        try:
            with open(LABELS_FILE, 'r') as f:
                data["labels"] = json.load(f)
        except Exception as e:
            st.warning(f"Could not load labels (check JSON format): {e}")
            
    return data

# Trigger the load immediately so files are ready for other pages
if __name__ == "__main__":
    load_data()