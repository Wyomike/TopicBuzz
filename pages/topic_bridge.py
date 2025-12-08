import streamlit as st
import networkx as nx
import pickle
import os
import json
from pyvis.network import Network
import streamlit.components.v1 as components

# --- CONFIGURATION ---
CACHE_FILE = "mastodon_network.pkl"
LABELS_FILE = "topic_labels.json"

# --- PAGE CONFIG ---
st.set_page_config(layout="wide", page_title="Topic Pathfinder")
st.title("🔗 Topic Pathfinder")
st.markdown("Find the **strongest social bridge** between two topics through shared users.")

# --- 1. LOAD DATA ---
@st.cache_resource
def load_data():
    data = {"G": None, "labels": {}}
    
    if os.path.exists(CACHE_FILE):
        with open(CACHE_FILE, 'rb') as f:
            data["G"] = pickle.load(f)
            
    if os.path.exists(LABELS_FILE):
        with open(LABELS_FILE, 'r') as f:
            data["labels"] = json.load(f)
            
    return data

data = load_data()
G = data["G"]
labels_map = data["labels"]

if G is None:
    st.error(f"Cache file '{CACHE_FILE}' not found!")
    st.stop()

# --- HELPER: Compute Costs ---
# We invert the weight so that High Posts = Low Cost (Short Path)
# This trick lets Dijkstra's algorithm find the "Strongest" path
for u, v, d in G.edges(data=True):
    weight = d.get('weight', 1)
    # Avoid division by zero, prioritize heavy weights
    # 1 post = cost 1.0
    # 100 posts = cost 0.01
    d['cost'] = 1 / weight 

# --- HELPER: Labeling ---
def get_label(node_id):
    if node_id.startswith("Topic_") and node_id in labels_map:
        return f"{labels_map[node_id]} ({node_id})"
    if node_id.startswith("User_"):
        return f"User {node_id.replace('User_', '')}"
    return node_id

# --- SIDEBAR SELECTION ---
st.sidebar.header("Select Path Endpoints")

# Filter for Topic Nodes only
topic_nodes = [n for n in G.nodes if n.startswith("Topic_")]
topic_options = {get_label(n): n for n in topic_nodes}
sorted_options = sorted(topic_options.keys())

start_label = st.sidebar.selectbox("Start Topic", sorted_options, index=0)
end_label = st.sidebar.selectbox("End Topic", sorted_options, index=len(sorted_options)-1)

start_node = topic_options[start_label]
end_node = topic_options[end_label]

# --- MAIN LOGIC ---

if st.sidebar.button("Find Connection"):
    if start_node == end_node:
        st.warning("Start and End topics are the same!")
        st.stop()

    try:
        # Find path using our inverted 'cost' weight
        path = nx.shortest_path(G, source=start_node, target=end_node, weight='cost')
        
        # Calculate total "strength" (Sum of posts in path)
        total_posts = 0
        
        # Display the Path Breakdown
        st.subheader("The Strongest Link")
        
        # Visualization Pipeline
        steps = []
        
        # Create a container for the explanation
        with st.container():
            col_list = st.columns(len(path))
            
            for i, node in enumerate(path):
                # Calculate edge weight to previous node
                posts_in = 0
                posts_out = 0
                
                if i > 0:
                    prev = path[i-1]
                    posts_in = G[prev][node]['weight']
                    total_posts += posts_in
                    steps.append(f"⬅️ {posts_in} posts")

                # Display Node
                is_user = node.startswith("User_")
                clean_name = get_label(node)
                
                if is_user:
                    # User Card
                    st.markdown(f"""
                    <div style="text-align: center; border: 1px solid #444; border-radius: 10px; padding: 10px; background-color: #222;">
                        <div style="font-size: 20px;">👤</div>
                        <div style="font-size: 14px; color: #97C2FC;">{clean_name}</div>
                    </div>
                    """, unsafe_allow_html=True)
                    
                    # Show arrow logic
                    if i < len(path)-1:
                         st.markdown(f"<div style='text-align:center; font-size: 20px; color: #aaa;'>⬇</div>", unsafe_allow_html=True)
                         
                else:
                    # Topic Card
                    color = "#00FF00" if i == 0 or i == len(path)-1 else "#FB7E81"
                    st.markdown(f"""
                    <div style="text-align: center; border: 2px solid {color}; border-radius: 10px; padding: 10px; background-color: #333;">
                        <div style="font-size: 20px;">📚</div>
                        <div style="font-size: 14px; font-weight: bold;">{clean_name.split('(')[0]}</div>
                    </div>
                    """, unsafe_allow_html=True)
                    
                    if i < len(path)-1:
                         st.markdown(f"<div style='text-align:center; font-size: 20px; color: #aaa;'>⬇</div>", unsafe_allow_html=True)

        # --- GRAPH VISUALIZATION ---
        st.divider()
        st.subheader("Network Visualization")
        
        # Extract subgraph for PyVis
        # We include the path AND the direct neighbors of everyone in the path 
        # to show "context" (optional, can just show path)
        path_subgraph = G.subgraph(path)
        
        nt = Network(height="500px", width="100%", bgcolor="#222222", font_color="white")
        
        # Add nodes with special highlighting
        for node in path:
            attr = G.nodes[node]
            label = get_label(node).split('(')[0] # Short label
            
            if node == start_node or node == end_node:
                nt.add_node(node, label=label, color="#00FF00", size=30, title="Endpoint")
            elif node.startswith("User_"):
                nt.add_node(node, label=label, color="#97C2FC", size=15, title="Connector")
            else:
                nt.add_node(node, label=label, color="#FB7E81", size=20, title="Intermediate Topic")

        # Add edges
        for i in range(len(path) - 1):
            u = path[i]
            v = path[i+1]
            weight = G[u][v]['weight']
            nt.add_edge(u, v, value=weight, title=f"{weight} posts", color="#FFFF00") # Yellow path

        # Physics
        nt.barnes_hut()
        
        # Save and Render
        path_html = "path_graph.html"
        nt.save_graph(path_html)
        
        # Read file back to embed
        with open(path_html, 'r', encoding='utf-8') as f:
            html_string = f.read()
            
        components.html(html_string, height=520)

    except nx.NetworkXNoPath:
        st.error(f"No path found between **{start_label}** and **{end_label}**. These communities might be completely disconnected.")

else:
    st.info("👈 Select two topics from the sidebar and click **Find Connection**.")