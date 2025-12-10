import streamlit as st
import networkx as nx
from pyvis.network import Network
import streamlit.components.v1 as components
from supabase import create_client, Client
from sentence_transformers import SentenceTransformer # NEW IMPORT
import json
import datetime
import math
import os

st.set_page_config(layout="wide", page_title="Semantic Topic Search")

# --- CONFIGURATION ---
MAX_NODES = 500
TIME_SCALE = 1 / 3600
LABELS_FILE = "topic_labels.json"

# --- LOAD RESOURCES ---
@st.cache_resource
def load_resources():
    # Load Supabase
    url = os.environ["SUPABASE_URL"]
    key = os.environ["SUPABASE_KEY"]
    sb = create_client(url, key)
    
    # Load Embedding Model (Cached so it only loads once)
    # This runs locally on your machine/server
    model = SentenceTransformer('all-MiniLM-L6-v2')
    
    return sb, model

supabase, model = load_resources()

# Load Labels
labels_map = {}
if os.path.exists(LABELS_FILE):
    with open(LABELS_FILE, 'r') as f:
        labels_map = json.load(f)

# --- HELPER: Time Color ---
def get_time_color(timestamp, max_ts, min_ts):
    if not timestamp: return "#888888"
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

# --- UI ---
st.title("🧠 Semantic Topic Search")
st.markdown("Search based on **meaning**, not just keywords.")

st.sidebar.header("Search Parameters")
search_query = st.sidebar.text_input("Concept Search", placeholder="e.g. 'Space exploration costs'")
limit = st.sidebar.slider("Max Posts", 50, 500, 200)
threshold = st.sidebar.slider("Similarity Threshold", 0.0, 1.0, 0.3, help="0.0 = Match anything, 1.0 = Exact match only")
node_spacing = st.sidebar.slider("Node Spacing", 50, 500, 250)

if search_query:
    with st.spinner(f"Vectorizing query & searching database..."):
        
        # 1. Vectorize the User's Query
        # We convert the text input into a list of 384 floats
        query_vector = model.encode(search_query).tolist()

        # 2. Call the RPC function in Supabase
        try:
            response = supabase.rpc(
                "match_posts", 
                {
                    "query_embedding": query_vector,
                    "match_threshold": threshold,
                    "match_count": limit
                }
            ).execute()
            
            data = response.data
        except Exception as e:
            st.error(f"Database Error: {e}")
            st.stop()

    if not data:
        st.warning("No posts found with that semantic meaning. Try lowering the threshold.")
        st.stop()

    st.success(f"Found {len(data)} semantically related posts.")

    # 3. Build Graph (Logic is identical to previous script)
    G = nx.Graph()
    timestamps = [row['post_timestamp'] for row in data if row['post_timestamp']]
    min_ts = min(timestamps) if timestamps else 0
    max_ts = max(timestamps) if timestamps else 1

    for row in data:
        user_id = row['author_user_id']
        topic_id = row['cluster_id']
        ts = row['post_timestamp'] or 0
        
        if not user_id: continue
        
        u_node = f"User_{user_id}"
        if topic_id is not None and topic_id != 0:
            raw_t_id = f"Topic_{topic_id}"
            t_label = labels_map.get(raw_t_id, f"Topic {topic_id}")
            t_node = raw_t_id
        else:
            t_node = "Topic_Unknown"
            t_label = "Uncategorized"

        if u_node not in G:
            G.add_node(u_node, label=f"User {user_id}", title=f"User ID: {user_id}", color="#97C2FC", size=10)
        
        if t_node not in G:
            G.add_node(t_node, label=t_label, title=t_label, color="#FB7E81", size=25)

        if G.has_edge(u_node, t_node):
            G[u_node][t_node]['weight'] += 1
            if ts > G[u_node][t_node]['ts']: G[u_node][t_node]['ts'] = ts
        else:
            G.add_edge(u_node, t_node, weight=1, ts=ts)

    # 4. Render PyVis
    nt = Network(height="700px", width="100%", bgcolor="#222222", font_color="white")
    
    for node_id in G.nodes:
        attr = G.nodes[node_id]
        nt.add_node(node_id, label=attr['label'], title=attr['title'], color=attr['color'], size=attr['size'])

    for u, v, d in G.edges(data=True):
        weight = d['weight']
        ts = d['ts']
        color = get_time_color(ts, max_ts, min_ts)
        date_str = datetime.datetime.fromtimestamp(ts).strftime('%Y-%m-%d') if ts > 0 else "Unknown"
        title = f"{weight} posts related to search\nLast Active: {date_str}"
        nt.add_edge(u, v, value=weight, title=title, color=color)

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
    
    html_data = nt.generate_html()
    components.html(html_data, height=720, scrolling=False)

else:
    st.info("👈 Enter a concept (e.g., 'artificial intelligence dangers') to search semantically.")