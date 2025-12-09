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

# --- CONFIGURATION ---
CACHE_FILE = "mastodon_network.pkl"
LABELS_FILE = "topic_labels.json"
MAX_PRE_FETCH = 50  # Python sends max 50 neighbors per node to browser
TIME_SCALE = 1 / 3600 # Logarithmic scale factor (Hours)

# Define Blocklist
NSFW_KEYWORDS = {
    "nsfw", "porn", "nude", "naked", "sex", "18+", "xxx", 
    "cum", "dick", "pussy", "hentai", "erotic", "onlyfans",
    "boobs", "tits", "cock", "slut", "whore", "bitch", "incest",
    "lewd", "horny", "sensual", "fetish", "bondage"
}

# --- PAGE CONFIG ---
st.set_page_config(layout="wide", page_title="Mastodon Graph Explorer")

# --- 1. LOAD DATA (Cached) ---
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

data = load_data()
G = data["G"]
labels_map = data["labels"]
MIN_TS = data["min_ts"]
MAX_TS = data["max_ts"]

if G is None:
    st.error(f"Cache file '{CACHE_FILE}' not found! Please run 'build_graph_cache.py' locally first.")
    st.stop()

# --- HELPER FUNCTIONS ---
def get_time_color(ts):
    """Returns a hex color code from Cyan (Old) to Red (New) using Logarithmic Age."""
    if ts <= 0: return "#888888"
    
    age = (MAX_TS - ts) * TIME_SCALE
    max_age = (MAX_TS - MIN_TS) * TIME_SCALE
    
    if max_age == 0: return "#FF0000"
    
    # Logarithmic decay
    decay = math.log(age + 1) / math.log(max_age + 1)
    ratio = max(0.0, min(1.0, 1.0 - decay))
    
    # Cyan (#00FFFF) to Red (#FF0000)
    r = int(ratio * 255)
    g = int((1 - ratio) * 255)
    b = int((1 - ratio) * 255)
    return f"#{r:02x}{g:02x}{b:02x}"

def is_node_allowed(node_id):
    if node_id == "Topic_0": return False
    label = labels_map.get(node_id, G.nodes[node_id].get('label', node_id))
    if label == "[NSFW]": return False
    if isinstance(label, str):
        label_words = set(label.lower().replace("_", " ").split())
        if not NSFW_KEYWORDS.isdisjoint(label_words):
            return False
    return True

def get_node_label(node_id):
    """Returns the friendly label for a node if available, else the ID."""
    if node_id.startswith("Topic_") and node_id in labels_map:
        return labels_map[node_id]
    return G.nodes[node_id].get('label', node_id)

def get_related_entities(graph, node_id, top_n=10):
    """
    Finds nodes that share the most connections with the target node.
    For a User, finds Users with shared Topics.
    For a Topic, finds Topics with shared Users.
    """
    if node_id not in graph:
        return []
    
    # Get direct neighbors (e.g., Topics for a User)
    direct_neighbors = list(graph.neighbors(node_id))
    
    related_scores = {}
    
    for neighbor in direct_neighbors:
        if not is_node_allowed(neighbor): continue

        # Get neighbors of neighbor (e.g., Users for a Topic)
        second_degree_neighbors = list(graph.neighbors(neighbor))
        
        for second_node in second_degree_neighbors:
            if second_node == node_id: continue
            if not is_node_allowed(second_node): continue
                
            # Score = Number of shared connections (Simple Common Neighbors)
            related_scores[second_node] = related_scores.get(second_node, 0) + 1
            
    # Sort by score descending
    sorted_related = sorted(related_scores.items(), key=lambda x: x[1], reverse=True)
    return sorted_related[:top_n]

# --- SIDEBAR CONTROLS ---
st.sidebar.title("🔍 Graph Controls")

# Prepare Topic List for Dropdown
topic_nodes = [n for n in G.nodes if n.startswith("Topic_")]
topic_options = {}

for t in topic_nodes:
    # Get fancy label if available, otherwise ID
    label = labels_map.get(t, G.nodes[t].get('label', t))
    
    # Skip NSFW/Filtered topics in the dropdown
    if not is_node_allowed(t):
        continue
        
    # Format: "Nature Photography (Topic_5)"
    display_name = f"{label} ({t})"
    topic_options[display_name] = t

# Prepare User List for Dropdown
user_nodes = [n for n in G.nodes if n.startswith("User_")]
user_options = {}

for u in user_nodes:
    # Label is usually "User {id}"
    label = G.nodes[u].get('label', u)
    user_options[label] = u

# Search Mode
search_mode = st.sidebar.radio("Search Mode", ["Select Topic", "Select User", "Random Topic"])

target_node = None

if search_mode == "Select User":
    # Sort options for easier finding
    sorted_users = sorted(user_options.keys())
    selected_user = st.sidebar.selectbox("Search User", sorted_users)
    
    if selected_user:
        target_node = user_options[selected_user]

elif search_mode == "Select Topic":
    # Sort options alphabetically
    sorted_options = sorted(topic_options.keys())
    selected_option = st.sidebar.selectbox("Choose a Topic", sorted_options)
    
    if selected_option:
        target_node = topic_options[selected_option]

elif search_mode == "Random Topic":
    if st.sidebar.button("Pick Random Topic"):
        # Pick from the filtered list we created above
        if topic_options:
            random_display = random.choice(list(topic_options.keys()))
            target_node = topic_options[random_display]
            st.session_state['selected_node'] = target_node

if 'selected_node' in st.session_state and not target_node:
    target_node = st.session_state['selected_node']

# Sliders
st.sidebar.markdown("---")
max_neighbors = st.sidebar.slider("Top Neighbors per Node", 1, 50, 5, help="How many strong connections to show per node.")
depth = st.sidebar.slider("Graph Depth", 1, 2, 2, help="1 = Direct connections only. 2 = Friends of friends.")

# --- MAIN GRAPH GENERATION ---
def generate_html(center_node, max_neighbors, depth):
    # 1. Python BFS (Pre-Filtering)
    nodes_to_include = {center_node}
    edges_to_include = []
    
    l1_neighbors = list(G.neighbors(center_node))
    l1_neighbors.sort(key=lambda x: G[center_node][x].get('weight', 1), reverse=True)
    l1_neighbors = l1_neighbors[:MAX_PRE_FETCH]

    for n1 in l1_neighbors:
        if not is_node_allowed(n1): continue
        nodes_to_include.add(n1)
        edges_to_include.append((center_node, n1))
        
        l2_neighbors = list(G.neighbors(n1))
        l2_neighbors.sort(key=lambda x: G[n1][x].get('weight', 1), reverse=True)
        l2_neighbors = l2_neighbors[:MAX_PRE_FETCH]
        
        for n2 in l2_neighbors:
            if not is_node_allowed(n2): continue
            if n2 != center_node:
                nodes_to_include.add(n2)
                edges_to_include.append((n1, n2))

    # 2. Prepare JSON Data
    js_nodes = []
    for nid in nodes_to_include:
        attr = G.nodes[nid]
        group = attr.get('group', 'unknown')
        base_size = attr.get('size', 10)
        
        # Apply Labels
        if group == "topics" and nid in labels_map:
            label = labels_map[nid]
            if len(label) > 20: label = label[:20] + "..."
            title = f"{nid}: {labels_map[nid]}"
        else:
            label = attr.get('label', nid)
            title = label

        node_data = {
            "id": nid,
            "label": label,
            "group": group,
            "value": base_size, # Default VisJS scaling
            "title": title,
            "baseSize": base_size # Used for custom slider scaling
        }
        
        if nid == center_node:
            node_data["color"] = "#00FF00" 
            node_data["size"] = 40
            node_data["baseSize"] = 40
        elif group == "users":
            node_data["color"] = "#97C2FC"
        else:
            node_data["color"] = "#FB7E81"
            
        js_nodes.append(node_data)

    js_edges = []
    for u, v in edges_to_include:
        data = G[u][v]
        weight = data.get('weight', 1)
        ts = data.get('last_timestamp', 0)
        
        edge_color = get_time_color(ts)
        date_str = datetime.datetime.fromtimestamp(ts).strftime('%Y-%m-%d') if ts > 0 else "Unknown"
        tooltip = f"Posts: {weight}\nLast Active: {date_str}"

        js_edges.append({
            "from": u,
            "to": v,
            "value": weight,
            "title": tooltip,
            "color": edge_color
        })

    # 3. Generate HTML with Embedded Logic
    html_string = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <script type="text/javascript" src="https://unpkg.com/vis-network/standalone/umd/vis-network.min.js"></script>
        <style type="text/css">
            body {{ font-family: sans-serif; background-color: #222; color: white; margin: 0; }}
            #mynetwork {{ width: 100%; height: 700px; border: 1px solid #444; }}
            #controls {{ padding: 15px; background-color: #333; display: flex; align-items: center; gap: 20px; flex-wrap: wrap; }}
            .control-group {{ display: flex; align-items: center; gap: 10px; }}
            input[type=range] {{ width: 150px; cursor: pointer; }}
            .label {{ font-weight: bold; font-size: 14px; color: #ddd; }}
            .val {{ font-family: monospace; color: #00FF00; font-weight: bold; width: 30px; }}
            .legend {{ margin-left: auto; font-size: 12px; color: #aaa; display: flex; gap: 10px; align-items: center; }}
            .dot {{ height: 10px; width: 10px; border-radius: 50%; display: inline-block; margin-right: 5px; }}
        </style>
    </head>
    <body>
    <div id="controls">
        <div class="control-group">
            <span class="label">🔍 Top N:</span>
            <input type="range" id="limitSlider" min="1" max="{MAX_PRE_FETCH}" value="{max_neighbors}">
            <span id="limitLabel" class="val">{max_neighbors}</span>
        </div>
        <div class="control-group">
            <span class="label">🕸️ Depth:</span>
            <input type="range" id="depthSlider" min="1" max="10" value="{depth}" step="1">
            <span id="depthLabel" class="val">{depth}</span>
        </div>
        <div class="control-group">
            <span class="label">🔵 Size:</span>
            <input type="range" id="sizeSlider" min="10" max="200" value="100">
            <span id="sizeLabel" class="val">100%</span>
        </div>
        <div class="legend">
            <span><span class="dot" style="background-color: #00FFFF;"></span>Old</span>
            <span><span class="dot" style="background-color: #FF0000;"></span>New</span>
        </div>
    </div>
    <div id="mynetwork"></div>
    <script type="text/javascript">
        const allNodes = {json.dumps(js_nodes)};
        const allEdges = {json.dumps(js_edges)};
        const rootNodeId = "{center_node}";
        
        const adjacency = {{}};
        allEdges.forEach(edge => {{
            if (!adjacency[edge.from]) adjacency[edge.from] = [];
            if (!adjacency[edge.to]) adjacency[edge.to] = [];
            adjacency[edge.from].push(edge);
            adjacency[edge.to].push(edge);
        }});

        function getFilteredData(limit, maxDepth, sizeScale) {{
            const visitedNodes = new Set();
            const edgesToKeep = new Set();
            const queue = [{{ id: rootNodeId, depth: 0 }}];
            visitedNodes.add(rootNodeId);

            while (queue.length > 0) {{
                const {{ id: currentNode, depth: currentDepth }} = queue.shift();
                if (currentDepth >= maxDepth) continue;

                const myEdges = adjacency[currentNode] || [];
                const sortedEdges = myEdges.sort((a, b) => b.value - a.value);
                const topEdges = sortedEdges.slice(0, limit);

                topEdges.forEach(edge => {{
                    const neighbor = (edge.from === currentNode) ? edge.to : edge.from;
                    edgesToKeep.add(edge);
                    if (!visitedNodes.has(neighbor)) {{
                        visitedNodes.add(neighbor);
                        queue.push({{ id: neighbor, depth: currentDepth + 1 }});
                    }}
                }});
            }}

            const filteredEdges = Array.from(edgesToKeep);
            const filteredNodes = allNodes
                .filter(n => visitedNodes.has(n.id))
                .map(n => {{
                    return {{ ...n, size: n.baseSize * (sizeScale / 100), value: undefined }};
                }});
            
            return {{ nodes: filteredNodes, edges: filteredEdges }};
        }}

        const container = document.getElementById('mynetwork');
        const options = {{
            nodes: {{ shape: 'dot', font: {{ color: 'white' }} }},
            edges: {{ smooth: {{ type: 'continuous' }} }},
            physics: {{
                stabilization: false,
                barnesHut: {{ gravitationalConstant: -8000, springConstant: 0.04, springLength: 250, damping: 0.2 }},
                minVelocity: 0.75
            }}
        }};

        let currentLimit = {max_neighbors};
        let currentDepth = {depth};
        let currentSize = 100;

        const initialData = getFilteredData(currentLimit, currentDepth, currentSize);
        const network = new vis.Network(container, initialData, options);

        const limitSlider = document.getElementById('limitSlider');
        const depthSlider = document.getElementById('depthSlider');
        const sizeSlider = document.getElementById('sizeSlider');

        limitSlider.oninput = function() {{
            currentLimit = parseInt(this.value);
            document.getElementById('limitLabel').innerText = currentLimit;
            network.setData(getFilteredData(currentLimit, currentDepth, currentSize));
        }}
        depthSlider.oninput = function() {{
            currentDepth = parseInt(this.value);
            document.getElementById('depthLabel').innerText = currentDepth;
            network.setData(getFilteredData(currentLimit, currentDepth, currentSize));
        }}
        sizeSlider.oninput = function() {{
            currentSize = parseInt(this.value);
            document.getElementById('sizeLabel').innerText = currentSize + "%";
            network.setData(getFilteredData(currentLimit, currentDepth, currentSize));
        }}
    </script>
    </body>
    </html>
    """
    return html_string

# --- RENDER PAGE ---
st.title("Topic Buzz Explorer 🐝")

if target_node:
    display_name = get_node_label(target_node)
    st.subheader(f"Visualizing: {display_name}")
    
    # --- GRAPH ---
    html_data = generate_html(target_node, max_neighbors, depth)
    components.html(html_data, height=720, scrolling=False)
    st.info(f"Exploring **{display_name}**. Use the controls inside the graph to filter connections.")

    # --- METRICS & ANALYSIS ---
    st.markdown("---")
    st.subheader(f"📊 Analysis for {display_name}")
    
    col1, col2 = st.columns(2)
    
    # Column 1: Direct Neighbors (Who/What are they connecting to?)
    with col1:
        st.markdown("#### 🔗 Top Connections")
        neighbors = list(G.neighbors(target_node))
        
        # Sort by edge weight (posts)
        neighbors.sort(key=lambda x: G[target_node][x].get('weight', 1), reverse=True)
        
        # Convert to DataFrame for nice table
        conn_data = []
        for n in neighbors[:15]: # Top 15
            if not is_node_allowed(n): continue
            weight = G[target_node][n].get('weight', 1)
            ts = G[target_node][n].get('last_timestamp', 0)
            date_str = datetime.datetime.fromtimestamp(ts).strftime('%Y-%m-%d') if ts > 0 else "N/A"
            
            conn_data.append({
                "Name": get_node_label(n),
                "Posts": weight,
                "Last Active": date_str
            })
            
        if conn_data:
            st.dataframe(pd.DataFrame(conn_data), hide_index=True)
        else:
            st.write("No connections found.")

    # Column 2: Related Entities (Who else is like this?)
    with col2:
        if target_node.startswith("User_"):
            st.markdown("#### 🤝 Similar Users (Shared Topics)")
        else:
            st.markdown("#### 🔗 Related Topics (Shared Users)")
            
        related = get_related_entities(G, target_node, top_n=15)
        
        related_data = []
        for node_id, score in related:
            related_data.append({
                "Name": get_node_label(node_id),
                "Shared Connections": score
            })
            
        if related_data:
            st.dataframe(pd.DataFrame(related_data), hide_index=True)
        else:
            st.write("No related entities found.")

else:
    st.write("👈 Select a User or Topic from the sidebar to begin.")
    st.markdown("""
    ### How to use:
    1. **Select a Topic** to see who is talking about it.
    2. **Select a User** to see what they are interested in.
    3. **Use the Sliders** inside the graph to filter noise and explore connections.
    """)






# def generate_html(center_node, max_neighbors, depth):
#     # 1. Python BFS (Pre-Filtering)
#     nodes_to_include = {center_node}
#     edges_to_include = []
    
#     l1_neighbors = list(G.neighbors(center_node))
    
#     # --- CHANGE 1: Sort by Recency (last_timestamp) ---
#     l1_neighbors.sort(key=lambda x: G[center_node][x].get('last_timestamp', 0), reverse=True)
#     l1_neighbors = l1_neighbors[:MAX_PRE_FETCH]

#     for n1 in l1_neighbors:
#         if not is_node_allowed(n1): continue
#         nodes_to_include.add(n1)
#         edges_to_include.append((center_node, n1))
        
#         l2_neighbors = list(G.neighbors(n1))
        
#         # --- CHANGE 2: Sort Level 2 by Recency as well ---
#         l2_neighbors.sort(key=lambda x: G[n1][x].get('last_timestamp', 0), reverse=True)
#         l2_neighbors = l2_neighbors[:MAX_PRE_FETCH]
        
#         for n2 in l2_neighbors:
#             if not is_node_allowed(n2): continue
#             if n2 != center_node:
#                 nodes_to_include.add(n2)
#                 edges_to_include.append((n1, n2))

#     # ... rest of the function remains the same ...


# # ... inside the "Metrics & Analysis" section ...

#     # Column 1: Direct Neighbors
#     with col1:
#         st.markdown("#### 🔗 Top Connections (Newest First)") # Updated Title
#         neighbors = list(G.neighbors(target_node))
        
#         # --- CHANGE 3: Sort Table by Recency ---
#         neighbors.sort(key=lambda x: G[target_node][x].get('last_timestamp', 0), reverse=True)
        
#         # Convert to DataFrame
#         conn_data = []
#         for n in neighbors[:15]: 
#              # ... rest of loop ...