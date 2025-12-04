import chromadb
import networkx as nx
from pyvis.network import Network
import random

# --- CONFIGURATION ---
CHROMA_PATH = "/home/wyomike/topicBuzz/my_mastodon_db"
COLLECTION_NAME = "mastodon_posts"
OUTPUT_FILE = "user_topic_network.html"

# Limit the graph size for performance/readability
MAX_USERS = 2000  # Number of users to visualize
BATCH_SIZE = 5000 # Memory safety batch size

# --- 1. Connect ---
print("Connecting to DB...")
client = chromadb.PersistentClient(path=CHROMA_PATH)
collection = client.get_collection(COLLECTION_NAME)

total_docs = collection.count()
print(f"Database contains {total_docs} documents.")

# --- 2. Build Edge List (Batched) ---
# Structure: (User_ID, Topic_ID)
edges = []
topic_counts = {}

print("Building network connections...")

for offset in range(0, total_docs, BATCH_SIZE):
    # Fetch just a slice of metadata
    batch = collection.get(
        limit=BATCH_SIZE, 
        offset=offset, 
        include=["metadatas"]
    )
    
    for meta in batch["metadatas"]:
        if not meta: continue
        
        user_id = meta.get("author_user_id")
        topic_id = meta.get("cluster_id")
        
        # Validation: Ensure we have both IDs and ignore "Outlier" topic (-1)
        if user_id and topic_id is not None and topic_id != -1:
            edges.append((user_id, topic_id))
            topic_counts[topic_id] = topic_counts.get(topic_id, 0) + 1
            
    # Optional progress indicator
    if offset % 50000 == 0:
        print(f"  Processed {offset}/{total_docs} docs...")

print(f"Found {len(edges)} total connections.")

# --- 3. Filter for Visualization ---
# To prevent a hairball graph, we sample a subset of users
unique_users = list(set(uid for uid, tid in edges))

if len(unique_users) > MAX_USERS:
    print(f"Sampling {MAX_USERS} users from {len(unique_users)} total...")
    selected_users = set(random.sample(unique_users, MAX_USERS))
    filtered_edges = [(u, t) for u, t in edges if u in selected_users]
else:
    filtered_edges = edges

print(f"Graphing {len(filtered_edges)} connections...")

# --- 4. Create NetworkX Graph ---
G = nx.Graph()

for user_id, topic_id in filtered_edges:
    # Add User Node (Blue, smaller)
    G.add_node(user_id, label=f"User {user_id}", title=f"User: {user_id}", color="#97C2FC", size=10, group="users")
    
    # Add Topic Node (Red, larger based on popularity)
    topic_node_id = f"Topic_{topic_id}"
    
    # Scale size: topics with more posts get bigger circles
    # Cap at size 50 so they don't cover the whole screen
    size = max(20, min(50, topic_counts.get(topic_id, 10) / 10)) 
    
    G.add_node(topic_node_id, label=f"Topic {topic_id}", title=f"Topic {topic_id} ({topic_counts.get(topic_id,0)} posts)", color="#FB7E81", size=size, group="topics")
    
    # Add Edge
    G.add_edge(user_id, topic_node_id)

# --- 5. Visualize with PyVis ---
print("Generating interactive HTML...")
nt = Network(height="750px", width="100%", bgcolor="#222222", font_color="white", select_menu=True)

# Import from NetworkX
nt.from_nx(G)

# Physics options for better layout (BarnesHut is good for large graphs)
# gravity: negative repels nodes so they don't bunch up
# central_gravity: pulls disconnected parts back to center
# nt.barnes_hut(gravity=-10000, central_gravity=0.3, spring_length=100)
nt.toggle_physics(False) # Turn off physics because boy that takes a while to load

# Save
nt.save_graph(OUTPUT_FILE)
print(f"Done! Open '{OUTPUT_FILE}' in your browser to explore the network.")