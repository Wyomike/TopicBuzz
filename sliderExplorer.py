# import networkx as nx
# import pickle
# import os
# import json
# import random

# # --- CONFIGURATION ---
# CACHE_FILE = "mastodon_network.pkl"
# LABELS_FILE = "topic_labels.json"
# OUTPUT_FILE = "interactive_graph.html"
# MAX_PRE_FETCH = 50  # Hard limit for HTML file size (Python sends max 50 neighbors per node)

# # Define Blocklist
# NSFW_KEYWORDS = {
#     "nsfw", "porn", "nude", "naked", "sex", "18+", "xxx", 
#     "cum", "dick", "pussy", "hentai", "erotic", "onlyfans",
#     "boobs", "tits", "cock", "slut", "whore", "bitch", "incest",
#     "lewd", "horny", "sensual", "fetish", "bondage"
# }

# # --- 1. Load Cache ---
# if not os.path.exists(CACHE_FILE):
#     print("Please run 'build_graph_cache.py' first!")
#     exit()

# print("Loading graph cache...")
# with open(CACHE_FILE, 'rb') as f:
#     G = pickle.load(f)

# # --- NEW: Load Labels ---
# labels_map = {}
# if os.path.exists(LABELS_FILE):
#     print(f"Loading labels from {LABELS_FILE}...")
#     with open(LABELS_FILE, 'r') as f:
#         labels_map = json.load(f)
# else:
#     print("⚠️ 'topic_labels.json' not found. Topics will show as IDs.")

# # --- Helper: Filter Logic ---
# def is_node_allowed(node_id):
#     """Returns False if node is Topic_0 or contains NSFW keywords."""
    
#     # 1. Explicitly block the Noise Topic
#     if node_id == "Topic_0":
#         return False
    
#     # 2. Check Label Content
#     # Use fancy label if available, otherwise use internal label or ID
#     label = labels_map.get(node_id, G.nodes[node_id].get('label', node_id))
    
#     # Check for explicit [NSFW] tag from generate_labels.py
#     if label == "[NSFW]":
#         return False
        
#     # Check keywords
#     if isinstance(label, str):
#         # Convert label to set of words for checking
#         # Replaces underscores with spaces to handle IDs like "19_nsfw_porn"
#         label_words = set(label.lower().replace("_", " ").split())
#         if not NSFW_KEYWORDS.isdisjoint(label_words):
#             return False
            
#     return True

# # --- 2. Input Selection ---
# print(f"\nGraph Loaded: {G.number_of_nodes()} nodes.")
# target_node = None

# while not target_node:
#     print("\nSearch Options:")
#     print("1. Search by User ID (e.g., 13179)")
#     print("2. Search by Topic ID (e.g., 5)")
#     print("3. Random Topic")
    
#     choice = input("Enter choice: ").strip()
    
#     if choice == '1':
#         uid = input("User ID: ").strip()
#         node_id = f"User_{uid}"
#         if node_id in G: target_node = node_id
    
#     elif choice == '2':
#         tid = input("Topic ID: ").strip()
#         node_id = f"Topic_{tid}"
#         if node_id in G: target_node = node_id
        
#     elif choice == '3':
#         topics = [n for n in G.nodes if n.startswith("Topic_")]
#         # Filter random selection to only safe topics
#         safe_topics = [t for t in topics if is_node_allowed(t)]
        
#         if not safe_topics:
#             print("No safe topics found!")
#             continue
            
#         target_node = random.choice(safe_topics)
#         # Show label in console if we have it
#         display_name = labels_map.get(target_node, target_node)
#         print(f"Selected: {display_name} ({target_node})")

#     if not target_node:
#         print("❌ Node not found. Try again.")
#     elif not is_node_allowed(target_node):
#         print(f"❌ Node '{target_node}' is filtered (NSFW or Noise). Pick another.")
#         target_node = None

# # --- 3. Extract Subgraph (Radius 2 with Pre-Pruning) ---
# print(f"Extracting ecosystem for {target_node}...")

# # We do a custom BFS to ensure we prioritize 'heavy' edges
# nodes_to_include = {target_node}
# edges_to_include = []

# # Step A: Get Neighbors of Center (Level 1)
# l1_neighbors = list(G.neighbors(target_node))
# l1_neighbors.sort(key=lambda x: G[target_node][x].get('weight', 1), reverse=True)
# l1_neighbors = l1_neighbors[:MAX_PRE_FETCH]

# for n1 in l1_neighbors:
#     # FILTER: Skip bad nodes
#     if not is_node_allowed(n1):
#         continue

#     nodes_to_include.add(n1)
#     edges_to_include.append((target_node, n1))
    
#     # Step B: Get Neighbors of Level 1 (Level 2)
#     l2_neighbors = list(G.neighbors(n1))
#     l2_neighbors.sort(key=lambda x: G[n1][x].get('weight', 1), reverse=True)
#     l2_neighbors = l2_neighbors[:MAX_PRE_FETCH]
    
#     for n2 in l2_neighbors:
#         # FILTER: Skip bad nodes
#         if not is_node_allowed(n2):
#             continue
            
#         if n2 != target_node:
#             nodes_to_include.add(n2)
#             edges_to_include.append((n1, n2))

# print(f"Subgraph stats: {len(nodes_to_include)} nodes, {len(edges_to_include)} edges.")

# # --- 4. Prepare Data for HTML ---
# js_nodes = []
# for nid in nodes_to_include:
#     attr = G.nodes[nid]
#     group = attr.get('group', 'unknown')
#     base_size = attr.get('size', 10)
    
#     # --- NEW: Label Logic ---
#     # If it's a topic and we have a mapping, use the fancy name
#     if group == "topics" and nid in labels_map:
#         label = labels_map[nid]
#         # Wrap really long labels for the visual node
#         if len(label) > 20:
#             label = label[:20] + "..."
#         title = f"{nid}: {labels_map[nid]}" # Full detail on hover
#     else:
#         label = attr.get('label', nid)
#         title = label

#     node_data = {
#         "id": nid,
#         "label": label,
#         "group": group,
#         "value": base_size,
#         "title": title,
#         "baseSize": base_size # Store original size for scaling
#     }
    
#     if nid == target_node:
#         node_data["color"] = "#00FF00" # Green for center
#         node_data["size"] = 40
#         node_data["baseSize"] = 40
#     elif group == "users":
#         node_data["color"] = "#97C2FC" # Blue
#     else:
#         node_data["color"] = "#FB7E81" # Red
        
#     js_nodes.append(node_data)

# js_edges = []
# for u, v in edges_to_include:
#     weight = G[u][v].get('weight', 1)
#     js_edges.append({
#         "from": u,
#         "to": v,
#         "value": weight,
#         "title": f"{weight} posts"
#     })

# # --- 5. Generate HTML with Strict BFS Logic & Depth Slider ---
# html_content = f"""
# <!DOCTYPE html>
# <html>
# <head>
#     <title>Interactive Graph: {target_node}</title>
#     <script type="text/javascript" src="https://unpkg.com/vis-network/standalone/umd/vis-network.min.js"></script>
#     <style type="text/css">
#         body {{ font-family: sans-serif; background-color: #222; color: white; margin: 0; }}
#         #mynetwork {{ width: 100%; height: 85vh; border: 1px solid #444; }}
#         #controls {{ padding: 15px; background-color: #333; display: flex; align-items: center; gap: 30px; flex-wrap: wrap; }}
#         .control-group {{ display: flex; align-items: center; gap: 10px; }}
#         input[type=range] {{ width: 200px; cursor: pointer; }}
#         .label {{ font-weight: bold; font-size: 16px; color: #ddd; }}
#         .val {{ font-family: monospace; color: #00FF00; font-weight: bold; width: 30px; }}
#     </style>
# </head>
# <body>

# <div id="controls">
#     <div class="control-group">
#         <span class="label">🔍 Top N:</span>
#         <input type="range" id="limitSlider" min="1" max="{MAX_PRE_FETCH}" value="5">
#         <span id="limitLabel" class="val">5</span>
#     </div>
    
#     <div class="control-group">
#         <span class="label">🕸️ Depth:</span>
#         <input type="range" id="depthSlider" min="1" max="10" value="2" step="1">
#         <span id="depthLabel" class="val">2</span>
#     </div>

#     <div class="control-group">
#         <span class="label">🔵 Size:</span>
#         <input type="range" id="sizeSlider" min="10" max="200" value="100">
#         <span id="sizeLabel" class="val">100%</span>
#     </div>
    
#     <span style="margin-left: auto; color: #888; font-size: 14px;">Showing strongly connected paths from root</span>
# </div>

# <div id="mynetwork"></div>

# <script type="text/javascript">
#     // --- Data ---
#     const allNodes = {json.dumps(js_nodes)};
#     const allEdges = {json.dumps(js_edges)};
#     const rootNodeId = "{target_node}";

#     // --- Helper: Group edges by node for fast lookup ---
#     const adjacency = {{}};
#     allEdges.forEach(edge => {{
#         if (!adjacency[edge.from]) adjacency[edge.from] = [];
#         if (!adjacency[edge.to]) adjacency[edge.to] = [];
#         adjacency[edge.from].push(edge);
#         adjacency[edge.to].push(edge);
#     }});

#     // --- Filtering Logic: Breadth-First Search from Root ---
#     function getFilteredData(limit, maxDepth, sizeScale) {{
#         const visitedNodes = new Set();
#         const edgesToKeep = new Set();
#         // Queue tracks: {{ id, depth }}
#         const queue = [{{ id: rootNodeId, depth: 0 }}];
        
#         visitedNodes.add(rootNodeId);

#         // BFS Traversal
#         while (queue.length > 0) {{
#             const {{ id: currentNode, depth: currentDepth }} = queue.shift();
            
#             // STRICT DEPTH LIMIT based on Slider
#             if (currentDepth >= maxDepth) continue;
            
#             // Get all edges connected to current node
#             const myEdges = adjacency[currentNode] || [];
            
#             // Sort by weight descending (Strongest links first)
#             const sortedEdges = myEdges.sort((a, b) => b.value - a.value);
            
#             // Keep top N strongest edges
#             const topEdges = sortedEdges.slice(0, limit);
            
#             topEdges.forEach(edge => {{
#                 // Determine neighbor
#                 const neighbor = (edge.from === currentNode) ? edge.to : edge.from;
                
#                 // Add edge to graph
#                 edgesToKeep.add(edge);
                
#                 // If neighbor not visited, add to queue
#                 if (!visitedNodes.has(neighbor)) {{
#                     visitedNodes.add(neighbor);
#                     queue.push({{ id: neighbor, depth: currentDepth + 1 }});
#                 }}
#             }});
#         }}

#         // Convert sets to arrays for Vis.js
#         const filteredEdges = Array.from(edgesToKeep);
        
#         // Filter nodes and APPLY SIZE SCALING
#         // WE USE 'size' directly to bypass auto-scaling normalization issues with 'value'
#         const filteredNodes = allNodes
#             .filter(n => visitedNodes.has(n.id))
#             .map(n => {{
#                 // Clone node and explicitly set size, removing value to avoid conflicts
#                 return {{ 
#                     ...n, 
#                     size: n.baseSize * (sizeScale / 100),
#                     value: undefined 
#                 }};
#             }});
        
#         return {{ nodes: filteredNodes, edges: filteredEdges }};
#     }}

#     // --- Initialize Network ---
#     const container = document.getElementById('mynetwork');
#     const options = {{
#         nodes: {{
#             shape: 'dot',
#             font: {{ color: 'white' }}
#             // Removed scaling options to rely on explicit size
#         }},
#         edges: {{
#             color: {{ color: '#888', highlight: '#fff' }},
#             smooth: {{ type: 'continuous' }}
#         }},
#         physics: {{
#             stabilization: false,
#             barnesHut: {{
#                 gravitationalConstant: -8000,
#                 springConstant: 0.04,
#                 springLength: 250, 
#                 damping: 0.2
#             }},
#             minVelocity: 0.75
#         }}
#     }};

#     // Initial State
#     let currentLimit = 5;
#     let currentDepth = 2;
#     let currentSize = 100;

#     const initialData = getFilteredData(currentLimit, currentDepth, currentSize);
#     const network = new vis.Network(container, initialData, options);

#     // --- Slider Logic ---
#     const limitSlider = document.getElementById('limitSlider');
#     const limitLabel = document.getElementById('limitLabel');
    
#     const depthSlider = document.getElementById('depthSlider');
#     const depthLabel = document.getElementById('depthLabel');

#     const sizeSlider = document.getElementById('sizeSlider');
#     const sizeLabel = document.getElementById('sizeLabel');

#     function updateGraph() {{
#         const newData = getFilteredData(currentLimit, currentDepth, currentSize);
#         // Use setData to update smoothly, keeping positions if possible
#         network.setData(newData);
#     }}

#     limitSlider.oninput = function() {{
#         currentLimit = parseInt(this.value);
#         limitLabel.innerText = currentLimit;
#         updateGraph();
#     }}
    
#     depthSlider.oninput = function() {{
#         currentDepth = parseInt(this.value);
#         depthLabel.innerText = currentDepth;
#         updateGraph();
#     }}

#     sizeSlider.oninput = function() {{
#         currentSize = parseInt(this.value);
#         sizeLabel.innerText = currentSize + "%";
#         updateGraph();
#     }}
# </script>

# </body>
# </html>
# """

# # --- 6. Save ---
# with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
#     f.write(html_content)

# print(f"\n✅ Interactive graph saved to '{OUTPUT_FILE}'")
# print(f"   Open this file in your browser.")



import networkx as nx
import pickle
import os
import json
import random
import datetime
import math

# --- CONFIGURATION ---
CACHE_FILE = "mastodon_network.pkl"
LABELS_FILE = "topic_labels.json"
OUTPUT_FILE = "interactive_graph.html"
MAX_PRE_FETCH = 50  # Hard limit for HTML file size (Python sends max 50 neighbors per node)

# Define Blocklist
NSFW_KEYWORDS = {
    "nsfw", "porn", "nude", "naked", "sex", "18+", "xxx", 
    "cum", "dick", "pussy", "hentai", "erotic", "onlyfans",
    "boobs", "tits", "cock", "slut", "whore", "bitch", "incest",
    "lewd", "horny", "sensual", "fetish", "bondage"
}

# --- 1. Load Cache ---
if not os.path.exists(CACHE_FILE):
    print("Please run 'build_graph_cache.py' first!")
    exit()

print("Loading graph cache...")
with open(CACHE_FILE, 'rb') as f:
    G = pickle.load(f)

# --- 2. Pre-calculate Time Range for Gradient ---
all_timestamps = [d['last_timestamp'] for u, v, d in G.edges(data=True) if 'last_timestamp' in d and d['last_timestamp'] > 0]

if all_timestamps:
    MIN_TS = min(all_timestamps)
    MAX_TS = max(all_timestamps)
else:
    MIN_TS, MAX_TS = 0, 1

print(f"Time range: {datetime.datetime.fromtimestamp(MIN_TS)} to {datetime.datetime.fromtimestamp(MAX_TS)}")

def get_time_color(ts):
    """Returns a hex color code from Cyan (Old) to Red (New) using Logarithmic Age."""
    if ts <= 0: return "#888888" # Grey for unknown
    
    # Calculate Age (Time elapsed since post)
    age = MAX_TS - ts
    max_age = MAX_TS - MIN_TS
    
    if max_age == 0: return "#FF0000" # Only one timestamp exists, treat as new
    
    # Logarithmic scaling
    # This emphasizes recent differences (hours/days) while compressing older history
    # age + 1 prevents log(0)
    # decay goes from 0.0 (Newest) to 1.0 (Oldest)
    days = 1/86400  # 1 day in seconds
    decay = math.log(days * age + 1) / math.log(days * max_age + 1)
    
    # Invert so 1.0 = New (Red), 0.0 = Old (Cyan)
    ratio = 1.0 - decay
    
    # Interpolate between Cyan (#00FFFF) and Red (#FF0000)
    # R: 0 -> 255
    # G: 255 -> 0
    # B: 255 -> 0
    r = int(ratio * 255)
    g = int((1 - ratio) * 255)
    b = int((1 - ratio) * 255)
    
    return f"#{r:02x}{g:02x}{b:02x}"

# --- 3. Load Labels ---
labels_map = {}
if os.path.exists(LABELS_FILE):
    with open(LABELS_FILE, 'r') as f:
        labels_map = json.load(f)
else:
    print("⚠️ 'topic_labels.json' not found. Topics will show as IDs.")

# --- Helper: Filter Logic ---
def is_node_allowed(node_id):
    if node_id == "Topic_0": return False
    label = labels_map.get(node_id, G.nodes[node_id].get('label', node_id))
    if label == "[NSFW]": return False
    if isinstance(label, str):
        label_words = set(label.lower().replace("_", " ").split())
        if not NSFW_KEYWORDS.isdisjoint(label_words):
            return False
    return True

# --- 4. Input Selection ---
print(f"\nGraph Loaded: {G.number_of_nodes()} nodes.")
target_node = None

while not target_node:
    print("\nSearch Options:")
    print("1. Search by User ID (e.g., 13179)")
    print("2. Search by Topic ID (e.g., 5)")
    print("3. Random Topic")
    
    choice = input("Enter choice: ").strip()
    
    if choice == '1':
        uid = input("User ID: ").strip()
        node_id = f"User_{uid}"
        if node_id in G: target_node = node_id
    elif choice == '2':
        tid = input("Topic ID: ").strip()
        node_id = f"Topic_{tid}"
        if node_id in G: target_node = node_id
    elif choice == '3':
        topics = [n for n in G.nodes if n.startswith("Topic_")]
        safe_topics = [t for t in topics if is_node_allowed(t)]
        if not safe_topics: continue
        target_node = random.choice(safe_topics)
        display_name = labels_map.get(target_node, target_node)
        print(f"Selected: {display_name} ({target_node})")

    if not target_node: print("❌ Node not found. Try again.")
    elif not is_node_allowed(target_node):
        print(f"❌ Node '{target_node}' is filtered. Pick another.")
        target_node = None

# --- 5. Extract Subgraph ---
print(f"Extracting ecosystem for {target_node}...")
nodes_to_include = {target_node}
edges_to_include = []

# Get Neighbors (Level 1)
l1_neighbors = list(G.neighbors(target_node))
l1_neighbors.sort(key=lambda x: G[target_node][x].get('weight', 1), reverse=True)
l1_neighbors = l1_neighbors[:MAX_PRE_FETCH]

for n1 in l1_neighbors:
    if not is_node_allowed(n1): continue
    nodes_to_include.add(n1)
    edges_to_include.append((target_node, n1))
    
    # Get Neighbors (Level 2)
    l2_neighbors = list(G.neighbors(n1))
    l2_neighbors.sort(key=lambda x: G[n1][x].get('weight', 1), reverse=True)
    l2_neighbors = l2_neighbors[:MAX_PRE_FETCH]
    
    for n2 in l2_neighbors:
        if not is_node_allowed(n2): continue
        if n2 != target_node:
            nodes_to_include.add(n2)
            edges_to_include.append((n1, n2))

# --- 6. Prepare Data for HTML ---
js_nodes = []
for nid in nodes_to_include:
    attr = G.nodes[nid]
    group = attr.get('group', 'unknown')
    base_size = attr.get('size', 10)
    
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
        "value": base_size, # VisJS uses this for default scaling
        "title": title,
        "baseSize": base_size # We store this for custom scaling slider
    }
    
    if nid == target_node:
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

# --- 7. Generate HTML ---
html_content = f"""
<!DOCTYPE html>
<html>
<head>
    <title>Interactive Graph: {target_node}</title>
    <script type="text/javascript" src="https://unpkg.com/vis-network/standalone/umd/vis-network.min.js"></script>
    <style type="text/css">
        body {{ font-family: sans-serif; background-color: #222; color: white; margin: 0; }}
        #mynetwork {{ width: 100%; height: 85vh; border: 1px solid #444; }}
        #controls {{ padding: 15px; background-color: #333; display: flex; align-items: center; gap: 30px; flex-wrap: wrap; }}
        .control-group {{ display: flex; align-items: center; gap: 10px; }}
        input[type=range] {{ width: 200px; cursor: pointer; }}
        .label {{ font-weight: bold; font-size: 16px; color: #ddd; }}
        .val {{ font-family: monospace; color: #00FF00; font-weight: bold; width: 30px; }}
        .legend {{ margin-left: auto; font-size: 14px; color: #aaa; display: flex; gap: 15px; align-items: center; }}
        .dot {{ height: 10px; width: 10px; border-radius: 50%; display: inline-block; margin-right: 5px; }}
    </style>
</head>
<body>

<div id="controls">
    <div class="control-group">
        <span class="label">🔍 Top N:</span>
        <input type="range" id="limitSlider" min="1" max="{MAX_PRE_FETCH}" value="5">
        <span id="limitLabel" class="val">5</span>
    </div>
    
    <div class="control-group">
        <span class="label">🕸️ Depth:</span>
        <input type="range" id="depthSlider" min="1" max="10" value="2" step="1">
        <span id="depthLabel" class="val">2</span>
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
    const rootNodeId = "{target_node}";

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
                return {{ 
                    ...n, 
                    size: n.baseSize * (sizeScale / 100),
                    value: undefined 
                }};
            }});
        
        return {{ nodes: filteredNodes, edges: filteredEdges }};
    }}

    const container = document.getElementById('mynetwork');
    const options = {{
        nodes: {{ shape: 'dot', font: {{ color: 'white' }} }},
        edges: {{ smooth: {{ type: 'continuous' }} }},
        physics: {{
            stabilization: false,
            barnesHut: {{
                gravitationalConstant: -8000,
                springConstant: 0.04,
                springLength: 250, 
                damping: 0.2
            }},
            minVelocity: 0.75
        }}
    }};

    let currentLimit = 5;
    let currentDepth = 2;
    let currentSize = 100;

    const initialData = getFilteredData(currentLimit, currentDepth, currentSize);
    const network = new vis.Network(container, initialData, options);

    const limitSlider = document.getElementById('limitSlider');
    const limitLabel = document.getElementById('limitLabel');
    const depthSlider = document.getElementById('depthSlider');
    const depthLabel = document.getElementById('depthLabel');
    const sizeSlider = document.getElementById('sizeSlider');
    const sizeLabel = document.getElementById('sizeLabel');

    function updateGraph() {{
        const newData = getFilteredData(currentLimit, currentDepth, currentSize);
        network.setData(newData);
    }}

    limitSlider.oninput = function() {{
        currentLimit = parseInt(this.value);
        limitLabel.innerText = currentLimit;
        updateGraph();
    }}
    
    depthSlider.oninput = function() {{
        currentDepth = parseInt(this.value);
        depthLabel.innerText = currentDepth;
        updateGraph();
    }}

    sizeSlider.oninput = function() {{
        currentSize = parseInt(this.value);
        sizeLabel.innerText = currentSize + "%";
        updateGraph();
    }}
</script>
</body>
</html>
"""

# --- 7. Save ---
with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
    f.write(html_content)

print(f"\n✅ Interactive graph saved to '{OUTPUT_FILE}'")
print(f"   Open this file in your browser.")