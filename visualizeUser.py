import networkx as nx
from pyvis.network import Network
import pickle
import os
import random

# --- CONFIGURATION ---
CACHE_FILE = "mastodon_network.pkl"
OUTPUT_FILE = "user_explorer.html"

# --- 1. Load Cache ---
if not os.path.exists(CACHE_FILE):
    print("Please run 'build_graph_cache.py' first!")
    exit()

print("Loading graph cache...")
with open(CACHE_FILE, 'rb') as f:
    G = pickle.load(f)

print(f"Graph loaded! ({G.number_of_nodes()} nodes)")

# --- 2. Select User ---
while True:
    print("\n--- Options ---")
    print("1. Enter a User ID")
    print("2. Pick a Random User")
    print("q. Quit")
    choice = input("Choice: ").strip()

    if choice == 'q': break
    
    target_user_node = ""
    
    if choice == '2':
        # Find all nodes that start with "User_"
        user_nodes = [n for n in G.nodes if n.startswith("User_")]
        target_user_node = random.choice(user_nodes)
        print(f"Selected random user: {target_user_node}")
    
    elif choice == '1':
        uid = input("Enter User ID (e.g. 13179): ").strip()
        target_user_node = f"User_{uid}"
        if target_user_node not in G:
            print("❌ User not found in graph!")
            continue

    # --- 3. Extract Subgraph (The Ego Graph) ---
    # Radius 1 = User + Connected Topics
    # Radius 2 = User + Connected Topics + OTHER Users in those topics (Careful, this can be huge!)
    
    radius = input("Enter exploration depth (1=Topics only, 2=Topics+Neighbors): ").strip()
    radius = int(radius) if radius in ['1', '2'] else 1
    
    print(f"Extracting subgraph for {target_user_node}...")
    
    # Get the "Ego Graph" (The node and its neighbors)
    subgraph = nx.ego_graph(G, target_user_node, radius=radius)
    
    # If radius is 2, the graph might be huge if they posted in a popular topic.
    # Let's limit the "Other Users" to avoid browser freeze
    if radius == 2 and subgraph.number_of_nodes() > 500:
        print(f"⚠️ Graph is large ({subgraph.number_of_nodes()} nodes). trimming...")
        # Keep the main user, all topics, and a random sample of other users
        nodes_to_keep = {target_user_node}
        topics = [n for n in subgraph.neighbors(target_user_node)]
        nodes_to_keep.update(topics)
        
        for t in topics:
            # Get neighbors of this topic (other users)
            other_users = list(G.neighbors(t))
            # Take only 20 random other users per topic
            nodes_to_keep.update(random.sample(other_users, min(len(other_users), 20)))
            
        subgraph = G.subgraph(list(nodes_to_keep))

    # --- 4. Visualize ---
    nt = Network(height="750px", width="100%", bgcolor="#222222", font_color="white")
    nt.from_nx(subgraph)
    
    # Highlight the main user in Green so you can find them
    if target_user_node in nt.get_nodes():
        # PyVis logic to update a specific node
        for node in nt.nodes:
            if node['id'] == target_user_node:
                node['color'] = "#00FF00" # Bright Green
                node['size'] = 25
                break

    nt.barnes_hut()
    nt.save_graph(OUTPUT_FILE)
    print(f"✅ Visualization saved to '{OUTPUT_FILE}'")