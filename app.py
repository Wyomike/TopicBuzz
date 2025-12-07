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

@st.cache_resource
def load_data():
    data = {"G": None, "labels": {}, "min_ts": 0, "max_ts": 1}
    
    if os.path.exists(CACHE_FILE):
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
            
    if os.path.exists(LABELS_FILE):
        with open(LABELS_FILE, 'r') as f:
            data["labels"] = json.load(f)
            
    return data
# ```

# ### How to create the Multi-Page Structure

# 1.  **Keep `app.py` (above):** This is your "Home" page.
# 2.  **Create a folder** named `pages` in the same directory.
# 3.  **Create `pages/1_Graph_Explorer.py`:** Copy your **original** graph logic (the massive script we just built) into this file.
# 4.  **Create `pages/2_Topic_List.py`:** (Optional) A simple page to list all topics and their keywords.

# **Example Directory Structure:**
# ```text
# /topic_buzz/
# ├── app.py                   # Landing Page
# ├── mastodon_network.pkl     # Data
# ├── topic_labels.json        # Data
# └── pages/
#     ├── 1_Graph_Explorer.py  # The interactive graph code
#     └── 2_Topic_List.py      # New simple page
# ```

# ### Code for `pages/1_Graph_Explorer.py`
# *(This is just your previous `app.py` code, but you need to import `load_data` from the main app or duplicate the function).*

# It is often cleaner to put the `load_data` function in a separate file (e.g., `utils.py`) and import it in both `app.py` and `pages/1_Graph_Explorer.py` to ensure the cache is shared efficiently.

# **Example `utils.py`:**
# ```python
# import streamlit as st
# import pickle
# import os
# import json

# @st.cache_resource
# def load_data():
#     # ... (paste the load_data logic here) ...
#     return data
# ```

# Then in every page:
# ```python
# from utils import load_data
# data = load_data()