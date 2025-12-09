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

OUTLIER_ID = "Topic_0" 

if G.has_node(OUTLIER_ID):
    G.remove_node(OUTLIER_ID)

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

if st.sidebar.button("Find Connection"):
    if start_node == end_node:
        st.warning("Start and End topics are the same!")
        st.stop()

    try:
        # 1. Calculate STRONGEST Path (Weighted by activity)
        path_strongest = nx.shortest_path(G, source=start_node, target=end_node, weight='cost')
        
        # 2. Calculate SHORTEST Path (Fewest hops/intermediaries)
        path_shortest = nx.shortest_path(G, source=start_node, target=end_node) # No weight = BFS

        # Create Tabs for the two views
        tab1, tab2 = st.tabs(["💪 Strongest Connection", "⚡ Shortest Connection"])

        # ==========================================
        # TAB 1: STRONGEST CONNECTION (Your original logic)
        # ==========================================
        with tab1:
            st.subheader("Strongest Social Bridge (Most Activity)")
            st.caption("This path follows the users with the highest post counts.")

            # --- Visualization Pipeline (Strongest) ---
            steps = []
            total_posts = 0
            
            with st.container():
                col_list = st.columns(len(path_strongest))
                
                for i, node in enumerate(path_strongest):
                    # Calculate edge weight to previous node
                    posts_in = 0
                    if i > 0:
                        prev = path_strongest[i-1]
                        posts_in = G[prev][node]['weight']
                        total_posts += posts_in

                    # Display Node
                    clean_name = get_label(node)
                    is_user = node.startswith("User_")
                    
                    with col_list[i]:
                        if is_user:
                            st.markdown(f"""
                            <div style="text-align: center; border: 1px solid #444; border-radius: 10px; padding: 10px; background-color: #222;">
                                <div style="font-size: 20px;">👤</div>
                                <div style="font-size: 14px; color: #97C2FC;">{clean_name}</div>
                            </div>
                            """, unsafe_allow_html=True)
                            if i < len(path_strongest)-1:
                                st.markdown(f"<div style='text-align:center; font-size: 20px; color: #aaa;'></div>", unsafe_allow_html=True)
                        else:
                            color = "#00FF00" if i == 0 or i == len(path_strongest)-1 else "#FB7E81"
                            st.markdown(f"""
                            <div style="text-align: center; border: 2px solid {color}; border-radius: 10px; padding: 10px; background-color: #333;">
                                <div style="font-size: 20px;">📚</div>
                                <div style="font-size: 14px; font-weight: bold;">{clean_name.split('(')[0]}</div>
                            </div>
                            """, unsafe_allow_html=True)
                            if i < len(path_strongest)-1:
                                st.markdown(f"<div style='text-align:center; font-size: 20px; color: #aaa;'></div>", unsafe_allow_html=True)

            # --- PyVis Graph (Strongest) ---
            st.divider()
            nt = Network(height="500px", width="100%", bgcolor="#222222", font_color="white")
            
            for node in path_strongest:
                attr = G.nodes[node]
                label = get_label(node).split('(')[0]
                if node == start_node or node == end_node:
                    nt.add_node(node, label=label, color="#00FF00", size=30)
                elif node.startswith("User_"):
                    nt.add_node(node, label=label, color="#97C2FC", size=15)
                else:
                    nt.add_node(node, label=label, color="#FB7E81", size=20)

            for i in range(len(path_strongest) - 1):
                u = path_strongest[i]
                v = path_strongest[i+1]
                weight = G[u][v]['weight']
                nt.add_edge(u, v, value=weight, title=f"{weight} posts", color="#FFFF00")

            nt.barnes_hut()
            nt.save_graph("strongest_graph.html")
            with open("strongest_graph.html", 'r', encoding='utf-8') as f:
                components.html(f.read(), height=520)

        # ==========================================
        # TAB 2: SHORTEST CONNECTION (New Logic)
        # ==========================================
        with tab2:
            st.subheader("Shortest Connection Graph (Fewest Hops)")
            st.caption("This path finds the quickest way to connect topics, even if the users aren't very active.")

            # --- Visualization Pipeline (Shortest) ---
            with st.container():
                col_list_s = st.columns(len(path_shortest))
                for i, node in enumerate(path_shortest):
                    clean_name = get_label(node)
                    is_user = node.startswith("User_")
                    
                    with col_list_s[i]:
                        if is_user:
                             st.markdown(f"""
                            <div style="text-align: center; border: 1px solid #444; border-radius: 10px; padding: 10px; background-color: #222;">
                                <div style="font-size: 20px;">👤</div>
                                <div style="font-size: 12px; color: #97C2FC;">{clean_name}</div>
                            </div>""", unsafe_allow_html=True)
                        else:
                             st.markdown(f"""
                            <div style="text-align: center; border: 2px solid #888; border-radius: 10px; padding: 10px; background-color: #333;">
                                <div style="font-size: 20px;">📚</div>
                                <div style="font-size: 12px; font-weight: bold;">{clean_name.split('(')[0]}</div>
                            </div>""", unsafe_allow_html=True)
                    
                        # if i < len(path_shortest)-1:
                        #         st.markdown(f"<div style='text-align:center; font-size: 20px; color: #aaa;'>➜</div>", unsafe_allow_html=True)

            # --- PyVis Graph (Shortest) ---
            st.divider()
            nt_short = Network(height="500px", width="100%", bgcolor="#222222", font_color="white")
            
            for node in path_shortest:
                attr = G.nodes[node]
                label = get_label(node).split('(')[0]
                if node == start_node or node == end_node:
                    nt_short.add_node(node, label=label, color="#00FF00", size=30)
                elif node.startswith("User_"):
                    nt_short.add_node(node, label=label, color="#97C2FC", size=15)
                else:
                    nt_short.add_node(node, label=label, color="#FB7E81", size=20)

            for i in range(len(path_shortest) - 1):
                u = path_shortest[i]
                v = path_shortest[i+1]
                weight = G[u][v]['weight']
                # Use CYAN for the shortest path to distinguish it
                nt_short.add_edge(u, v, value=1, title=f"{weight} posts", color="#00FFFF")

            nt_short.barnes_hut()
            nt_short.save_graph("shortest_graph.html")
            with open("shortest_graph.html", 'r', encoding='utf-8') as f:
                components.html(f.read(), height=520)

    except nx.NetworkXNoPath:
        st.error(f"No path found between **{start_label}** and **{end_label}**. These communities might be completely disconnected.")

else:
    st.info("👈 Select two topics from the sidebar and click **Find Connection**.")