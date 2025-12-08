import streamlit as st
import networkx as nx
from pyvis.network import Network
import streamlit.components.v1 as components
from supabase import create_client, Client
import json
import datetime
import math
import os

# --- CONFIGURATION ---
MAX_NODES = 500  # Safety limit to prevent browser crash on huge results
TIME_SCALE = 1 / 3600 # For color gradient (Hours)

# Load Topic Labels (for pretty names)
LABELS_FILE = "topic_labels.json"
labels_map = {}
if os.path.exists(LABELS_FILE):
    with open(LABELS_FILE, 'r') as f:
        labels_map = json.load(f)

# url = os.environ["SUPABASE_URL"]
# key = os.environ["SUPABASE_KEY"]
# --- SETUP SUPABASE ---
@st.cache_resource
def init_supabase():
    url = os.environ["SUPABASE_URL"]
    key = os.environ["SUPABASE_KEY"]
    return create_client(url, key)

supabase: Client = init_supabase()

# --- PAGE CONFIG ---
st.set_page_config(layout="wide", page_title="Live Topic Search")
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
        # We assume your table has 'content', 'author_user_id', 'cluster_id', and 'post_timestamp'
        try:
            response = supabase.table("mastodon_posts") \
                .select("author_user_id, cluster_id, post_timestamp, content") \
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

    st.success(f"Found {len(data)} posts. Building graph...")

    # 2. Build Graph from Query Results
    G = nx.Graph()
    
    # Track min/max time for this specific batch for coloring
    timestamps = [row['post_timestamp'] for row in data if row['post_timestamp']]
    if timestamps:
        min_ts = min(timestamps)
        max_ts = max(timestamps)
    else:
        min_ts, max_ts = 0, 1

    # Processing loop
    for row in data:
        user_id = row['author_user_id']
        topic_id = row['cluster_id']
        ts = row['post_timestamp'] or 0
        
        if not user_id: continue
        
        # Node IDs
        u_node = f"User_{user_id}"
        
        # Handle Topic Node (Use Label if available)
        if topic_id is not None:
            raw_t_id = f"Topic_{topic_id}"
            t_label = labels_map.get(raw_t_id, f"Topic {topic_id}")
            t_node = raw_t_id
        else:
            # If no topic assigned, link to a "Uncategorized" node
            t_node = "Topic_Unknown"
            t_label = "Uncategorized"

        # Add Nodes
        if u_node not in G:
            G.add_node(u_node, label=f"User {user_id}", group="users", title=f"User ID: {user_id}", color="#97C2FC", size=10)
        
        if t_node not in G:
            G.add_node(t_node, label=t_label, group="topics", title=t_label, color="#FB7E81", size=25)

        # Add/Update Edge
        if G.has_edge(u_node, t_node):
            G[u_node][t_node]['weight'] += 1
            # Keep most recent timestamp
            if ts > G[u_node][t_node]['ts']:
                 G[u_node][t_node]['ts'] = ts
        else:
            G.add_edge(u_node, t_node, weight=1, ts=ts)

    # 3. Generate PyVis Visualization
    nt = Network(height="700px", width="100%", bgcolor="#222222", font_color="white")
    
    # Add Nodes
    for node_id in G.nodes:
        attr = G.nodes[node_id]
        nt.add_node(node_id, label=attr['label'], title=attr['title'], color=attr['color'], size=attr['size'])

    # Add Edges with Coloring
    for u, v, d in G.edges(data=True):
        weight = d['weight']
        ts = d['ts']
        color = get_time_color(ts, max_ts, min_ts)
        
        date_str = datetime.datetime.fromtimestamp(ts).strftime('%Y-%m-%d') if ts > 0 else "Unknown"
        title = f"{weight} posts matching '{search_query}'\nLast Active: {date_str}"
        
        nt.add_edge(u, v, value=weight, title=title, color=color)

    # Physics Options
    nt.set_options(f"""
    var options = {{
      "physics": {{
        "barnesHut": {{
          "gravitationalConstant": -8000,
          "springLength": {node_spacing},
          "springConstant": 0.04,
          "damping": 0.2
        }},
        "minVelocity": 0.75
      }}
    }}
    """)

    # Render
    html_data = nt.generate_html()
    components.html(html_data, height=720, scrolling=False)
    
    # Stats
    st.info(f"Visualizing {G.number_of_nodes()} nodes (Users & Topics) and {G.number_of_edges()} connections based on search results.")

else:
    st.info("👈 Enter a search term in the sidebar to generate a graph from the live database.")