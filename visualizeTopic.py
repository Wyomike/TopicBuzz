import networkx as nx
from pyvis.network import Network
import pickle
import os
import random

# --- CONFIGURATION ---
CACHE_FILE = "mastodon_network.pkl"
OUTPUT_FILE = "topic_explorer.html"

# --- 1. Load Cache ---
if not os.path.exists(CACHE_FILE):
    print("Please run 'build_graph_cache.py' first!")
    exit()

print("Loading graph cache...")
with open(CACHE_FILE, 'rb') as f:
    G = pickle.load(f)

print(f"Graph loaded! ({G.number_of_nodes()} nodes)")

# --- 2. Select Topic ---
while True:
    print("\n--- Options ---")
    print("1. Enter a Topic ID")
    print("2. Pick a Random Topic")
    print("q. Quit")
    choice = input("Choice: ").strip()

    if choice == 'q': break
    
    target_topic_node = ""
    
    if choice == '2':
        # Find all nodes that start with "Topic_"
        topic_nodes = [n for n in G.nodes if n.startswith("Topic_")]
        target_topic_node = random.choice(topic_nodes)
        
        # Get pretty label if available
        label = G.nodes[target_topic_node].get('label', target_topic_node)
        print(f"Selected random topic: {label}")
    
    elif choice == '1':
        tid = input("Enter Topic ID (e.g. 5): ").strip()
        target_topic_node = f"Topic_{tid}"
        if target_topic_node not in G:
            print("❌ Topic not found in graph!")
            continue

    # --- 3. Extract Subgraph ---
    print(f"\nExploring: {target_topic_node}")
    print("1. View Participants (Users in this topic)")
    print("2. View Ecosystem (Users + Other Topics they visit)")
    depth = input("Select Depth (1 or 2): ").strip()
    radius = int(depth) if depth in ['1', '2'] else 1
    
    print(f"Extracting subgraph...")
    
    # Get the "Ego Graph" centered on the topic
    subgraph = nx.ego_graph(G, target_topic_node, radius=radius)
    
    # Pruning for Radius 2 (Ecosystem) to prevent browser crash
    # If a topic has 1000 users, and each visits 10 other topics, that's 10,000 nodes.
    MAX_NODES = 1000
    if subgraph.number_of_nodes() > MAX_NODES:
        print(f"⚠️ Graph is massive ({subgraph.number_of_nodes()} nodes). trimming...")
        
        # Priority 1: Keep the main Topic
        nodes_to_keep = {target_topic_node}
        
        # Priority 2: Keep its direct Users (Neighbors)
        direct_users = list(G.neighbors(target_topic_node))
        
        # If too many users, sample them
        if len(direct_users) > 300:
            direct_users = random.sample(direct_users, 300)
        
        nodes_to_keep.update(direct_users)
        
        # Priority 3 (Only if Radius=2): Keep 'Related Topics' connected to those users
        if radius == 2:
            related_topics = []
            for u in direct_users:
                # Find other topics this user visited
                topics_visited = [n for n in G.neighbors(u) if n.startswith("Topic_") and n != target_topic_node]
                related_topics.extend(topics_visited)
            
            # Keep top 50 most frequent related topics
            from collections import Counter
            common_related = [t for t, c in Counter(related_topics).most_common(50)]
            nodes_to_keep.update(common_related)
            
        subgraph = G.subgraph(list(nodes_to_keep))

    # --- 4. Visualize ---
    nt = Network(height="750px", width="100%", bgcolor="#222222", font_color="white")
    nt.from_nx(subgraph)
    
    # Highlight the main Topic in Red/Gold
    if target_topic_node in nt.get_nodes():
        for node in nt.nodes:
            if node['id'] == target_topic_node:
                node['color'] = "#FFD700" # Gold
                node['size'] = 40
                break

    # Physics settings for a nice spread
    nt.barnes_hut(gravity=-4000, central_gravity=0.1, spring_length=150)
    
    nt.save_graph(OUTPUT_FILE)
    print(f"✅ Visualization saved to '{OUTPUT_FILE}'")