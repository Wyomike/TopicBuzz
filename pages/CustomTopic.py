import streamlit as st
import networkx as nx
from pyvis.network import Network
import streamlit.components.v1 as components
from supabase import create_client, Client
import json
import datetime
import math
import os

st.set_page_config(layout="wide", page_title="Live Topic Search")

# --- CONFIGURATION ---
MAX_NODES = 500  # Safety limit to prevent browser crash on huge results
TIME_SCALE = 1 / 3600 # For color gradient (Hours)

# Load Topic Labels (for pretty names)
LABELS_FILE = "topic_labels.json"
labels_map = {}
if os.path.exists(LABELS_FILE):
    with open(LABELS_FILE, 'r') as f:
        labels_map = json.load(f)

# --- SETUP SUPABASE ---
@st.cache_resource
def init_supabase():
    url = os.environ["SUPABASE_URL"]
    key = os.environ["SUPABASE_KEY"]
    return create_client(url, key)

supabase: Client = init_supabase()

# --- PAGE CONFIG ---
st.title("🔎 Live Topic Search")
st.markdown("Search the **Supabase** database for specific content and visualize the community discussing it.")

# --- SIDEBAR INPUTS ---
st.sidebar.header("Search Parameters")
search_query = st.sidebar.text_input("Search Content", placeholder="e.g. 'Elon', 'Climate', 'Python'")
limit = st.sidebar.slider("Max Posts to Fetch", 50, 2000, 500)

# Visual Controls (Embedded in logic later, but setup values here)
st.sidebar.markdown("---")
st.sidebar.write("**Graph Settings**")
node_spacing = st.sidebar.slider("Node Spacing", 50, 500, 250)

# --- HELPER: Time Color ---
def get_time_color(timestamp, max_ts, min_ts):
    """Calculates color from Cyan (Old) to Red (New)."""
    if not timestamp: return "#888888"
    
    # Simple normalization if range is valid
    if max_ts == min_ts: return "#FF0000"
    
    age = (max_ts - timestamp) * TIME_SCALE
    max_age = (max_ts - min_ts) * TIME_SCALE
    
    try:
        decay = math.log(age + 1) / math.log(max_age + 1)
        ratio = max(0.0, min(1.0, 1.0 - decay))
    except ValueError:
        ratio = 0.5

    r = int(ratio * 255)
    g = int((1 - ratio) * 255)
    b = int((1 - ratio) * 255)
    return f"#{r:02x}{g:02x}{b:02x}"

# --- MAIN LOGIC ---

if search_query:
    with st.spinner(f"Searching database for '{search_query}'..."):
        # 1. Query Supabase
        try:
            response = supabase.table("posts") \
                .select("author_user_id, post_timestamp, content") \
                .ilike("content", f"%{search_query}%") \
                .limit(limit) \
                .execute()
            
            data = response.data
        except Exception as e:
            st.error(f"Database Error: {e}")
            st.stop()

    if not data:
        st.warning("No posts found matching that query.")
        st.stop()

    st.success(f"Found {len(data)} posts. Building Star Graph...")

    # 2. Aggregation (Group by User)
    # We need to count posts per user to determine edge weight
    user_stats = {} # { user_id: {'count': int, 'max_ts': int} }
    
    all_timestamps = []

    for row in data:
        uid = row['author_user_id']
        ts = row['post_timestamp'] or 0
        all_timestamps.append(ts)

        if uid not in user_stats:
            user_stats[uid] = {'count': 0, 'max_ts': 0}
        
        user_stats[uid]['count'] += 1
        if ts > user_stats[uid]['max_ts']:
            user_stats[uid]['max_ts'] = ts

    # Calc min/max for coloring
    if all_timestamps:
        min_ts = min(all_timestamps)
        max_ts = max(all_timestamps)
    else:
        min_ts, max_ts = 0, 1

    # 3. Build Graph
    G = nx.Graph()
    
    # Create the CENTRAL TOPIC NODE
    central_id = "CENTER_TOPIC"
    G.add_node(central_id, 
               label=search_query.upper(), 
               title=f"Search Query: {search_query}", 
               color="#FF4B4B",  # Streamlit Red
               size=40,
               shape="star") # Make it stand out

    # Add User Nodes and Edges
    for uid, stats in user_stats.items():
        user_node_id = f"User_{uid}"
        count = stats['count']
        last_active_ts = stats['max_ts']
        
        # Color based on recency
        edge_color = get_time_color(last_active_ts, max_ts, min_ts)
        
        # User Node
        G.add_node(user_node_id, 
                   label=f"User {uid}", 
                   title=f"User {uid}\nPosts: {count}", 
                   color="#97C2FC", 
                   size=15)
        
        # Edge (User -> Center)
        # Width/Value scales with post count
        date_str = datetime.datetime.fromtimestamp(last_active_ts).strftime('%Y-%m-%d %H:%M') if last_active_ts > 0 else "Unknown"
        edge_title = f"{count} posts about '{search_query}'\nLast active: {date_str}"
        
        G.add_edge(central_id, user_node_id, 
                   value=count, 
                   title=edge_title, 
                   color=edge_color)

    # 4. Generate PyVis Visualization
    nt = Network(height="700px", width="100%", bgcolor="#222222", font_color="white")
    
    # Copy NX nodes to PyVis
    for node_id in G.nodes:
        attr = G.nodes[node_id]
        # shape is optional, safely get it
        shape = attr.get('shape', 'dot') 
        nt.add_node(node_id, label=attr['label'], title=attr['title'], color=attr['color'], size=attr['size'], shape=shape)

    # Copy NX edges to PyVis
    for u, v, d in G.edges(data=True):
        nt.add_edge(u, v, value=d['value'], title=d['title'], color=d['color'])

    # Physics Options (Optimized for Star Topology)
    nt.set_options(f"""
    var options = {{
      "physics": {{
        "barnesHut": {{
          "gravitationalConstant": -10000,
          "centralGravity": 0.3,
          "springLength": {node_spacing},
          "springConstant": 0.05,
          "damping": 0.09
        }},
        "minVelocity": 0.75
      }}
    }}
    """)

    # Render
    html_data = nt.generate_html()
    components.html(html_data, height=720, scrolling=False)
    
    # Stats
    st.info(f"Visualizing {len(user_stats)} users discussing '{search_query}'.")

else:
    st.info("👈 Enter a search term in the sidebar to generate a graph from the live database.")