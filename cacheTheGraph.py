# import chromadb
# import networkx as nx
# import pickle
# import os

# # --- CONFIGURATION ---
# CHROMA_PATH = "/home/wyomike/topicBuzz/my_mastodon_db"
# COLLECTION_NAME = "mastodon_posts"
# CACHE_FILE = "mastodon_network.pkl"
# BATCH_SIZE = 10000

# # --- 1. Connect ---
# print("Connecting to DB...")
# client = chromadb.PersistentClient(path=CHROMA_PATH)
# collection = client.get_collection(COLLECTION_NAME)
# total_docs = collection.count()

# # --- 2. Build Graph with Weights ---
# print(f"Building weighted graph from {total_docs} docs...")
# G = nx.Graph()
# topic_counts = {}

# for offset in range(0, total_docs, BATCH_SIZE):
#     batch = collection.get(
#         limit=BATCH_SIZE, 
#         offset=offset, 
#         include=["metadatas"]
#     )
    
#     for meta in batch["metadatas"]:
#         if not meta: continue
        
#         user_id = meta.get("author_user_id")
#         topic_id = meta.get("cluster_id")
        
#         if user_id and topic_id is not None and topic_id != -1:
#             u_node = f"User_{user_id}"
#             t_node = f"Topic_{topic_id}"
            
#             # Ensure nodes exist
#             if u_node not in G:
#                 G.add_node(u_node, label=f"User {user_id}", group="users", color="#97C2FC", size=10)
            
#             if t_node not in G:
#                 G.add_node(t_node, label=f"Topic {topic_id}", group="topics", color="#FB7E81", size=20)
            
#             # --- NEW: Edge Weight Logic ---
#             if G.has_edge(u_node, t_node):
#                 # Increment weight if connection exists
#                 G[u_node][t_node]['weight'] += 1
#             else:
#                 # Initialize new connection
#                 G.add_edge(u_node, t_node, weight=1)
            
#             # Track counts for node sizing
#             topic_counts[topic_id] = topic_counts.get(topic_id, 0) + 1

#     if offset % 50000 == 0:
#         print(f"  Processed {offset}/{total_docs}...")

# # Resize topics based on total popularity
# print("Resizing topic nodes...")
# for topic_id, count in topic_counts.items():
#     t_node = f"Topic_{topic_id}"
#     if t_node in G:
#         G.nodes[t_node]['size'] = max(20, min(60, count / 5))
#         G.nodes[t_node]['title'] = f"Topic {topic_id}: {count} posts"

# # --- 3. Save Cache ---
# print(f"Saving graph to '{CACHE_FILE}'...")
# with open(CACHE_FILE, 'wb') as f:
#     pickle.dump(G, f)

# print(f"Done! Weighted graph cached.")



import chromadb
import networkx as nx
import pickle
import os

# --- CONFIGURATION ---
CHROMA_PATH = "/home/wyomike/topicBuzz/my_mastodon_db"
COLLECTION_NAME = "mastodon_posts"
CACHE_FILE = "mastodon_network.pkl"
BATCH_SIZE = 10000

# --- 1. Connect ---
print("Connecting to DB...")
client = chromadb.PersistentClient(path=CHROMA_PATH)
collection = client.get_collection(COLLECTION_NAME)
total_docs = collection.count()

# --- 2. Build Graph with Weights & Time ---
print(f"Building weighted temporal graph from {total_docs} docs...")
G = nx.Graph()
topic_counts = {}

for offset in range(0, total_docs, BATCH_SIZE):
    batch = collection.get(
        limit=BATCH_SIZE, 
        offset=offset, 
        include=["metadatas"]
    )
    
    for meta in batch["metadatas"]:
        if not meta: continue
        
        user_id = meta.get("author_user_id")
        topic_id = meta.get("cluster_id")
        
        # Try to get timestamp, handle reblogs if necessary
        ts = meta.get("post_timestamp")
        if ts is None:
            ts = meta.get("reblog_timestamp", 0)
        
        if user_id and topic_id is not None and topic_id != -1:
            u_node = f"User_{user_id}"
            t_node = f"Topic_{topic_id}"
            
            # Ensure nodes exist
            if u_node not in G:
                G.add_node(u_node, label=f"User {user_id}", group="users", color="#97C2FC", size=10)
            
            if t_node not in G:
                G.add_node(t_node, label=f"Topic {topic_id}", group="topics", color="#FB7E81", size=20)
            
            # --- Edge Logic: Weight + Time ---
            if G.has_edge(u_node, t_node):
                # Increment weight
                G[u_node][t_node]['weight'] += 1
                # Keep the MOST RECENT timestamp
                if ts > G[u_node][t_node]['last_timestamp']:
                    G[u_node][t_node]['last_timestamp'] = ts
            else:
                # Initialize new connection
                G.add_edge(u_node, t_node, weight=1, last_timestamp=ts)
            
            # Track counts
            topic_counts[topic_id] = topic_counts.get(topic_id, 0) + 1

    if offset % 50000 == 0:
        print(f"  Processed {offset}/{total_docs}...")

# Resize topics
print("Resizing topic nodes...")
for topic_id, count in topic_counts.items():
    t_node = f"Topic_{topic_id}"
    if t_node in G:
        G.nodes[t_node]['size'] = max(20, min(60, count / 5))
        G.nodes[t_node]['title'] = f"Topic {topic_id}: {count} posts"

# --- 3. Save Cache ---
print(f"Saving graph to '{CACHE_FILE}'...")
with open(CACHE_FILE, 'wb') as f:
    pickle.dump(G, f)

print(f"Done! Graph cached.")