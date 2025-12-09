import os
import networkx as nx
import pickle
from supabase import create_client, Client

# --- CONFIGURATION ---
SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY")
CACHE_FILE = "mastodon_network.pkl"
BUCKET = "topic_assets"
PAGE_SIZE = 5000  # Fetch 5k rows at a time (adjust if hitting timeouts)

# --- 1. Connect ---
if not SUPABASE_URL or not SUPABASE_KEY:
    raise ValueError("❌ Missing Supabase credentials in environment variables.")

print(f"Connecting to Supabase at {SUPABASE_URL}...")
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# --- 2. Build Graph with Weights & Time ---
print("Building weighted temporal graph...")
G = nx.Graph()
topic_counts = {}

offset = 0
total_processed = 0

while True:
    # Fetch batch of posts that have a cluster assigned
    # We only need 3 columns to build the graph, so we select only those.
    print(f"  Fetching rows {offset} to {offset + PAGE_SIZE}...")
    
    try:
        response = supabase.table("posts") \
            .select("author_user_id, cluster_id, post_timestamp") \
            .neq("cluster_id", -1) \
            .not_.is_("cluster_id", "null") \
            .not_.is_("author_user_id", "null") \
            .range(offset, offset + PAGE_SIZE - 1) \
            .execute()
        
        batch = response.data
        
        if not batch:
            break
            
        for row in batch:
            user_id = row.get("author_user_id")
            topic_id = row.get("cluster_id")
            ts = row.get("post_timestamp", 0)
            
            # Create node IDs
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
            
            # Track counts for sizing later
            topic_counts[topic_id] = topic_counts.get(topic_id, 0) + 1

        total_processed += len(batch)
        offset += PAGE_SIZE
        
        # Safety break for huge DBs (remove if you want 100% of data)
        # if total_processed > 100000:
        #     print("  Limit reached (100k), stopping fetch.")
        #     break

    except Exception as e:
        print(f"❌ Error fetching batch: {e}")
        break

print(f"Graph built! Nodes: {len(G.nodes)}, Edges: {len(G.edges)}")

# --- 3. Resize Topics ---
print("Resizing topic nodes...")
for topic_id, count in topic_counts.items():
    t_node = f"Topic_{topic_id}"
    if t_node in G:
        # Scale size: Min 20, Max 60
        G.nodes[t_node]['size'] = max(20, min(60, count / 5))
        G.nodes[t_node]['title'] = f"Topic {topic_id}: {count} posts"

# --- 4. Save and Upload ---
print(f"Saving graph to '{CACHE_FILE}'...")
with open(CACHE_FILE, 'wb') as f:
    pickle.dump(G, f)

print(f"☁️ Uploading {CACHE_FILE} to Supabase Storage...")
try:
    with open(CACHE_FILE, 'rb') as f:
        supabase.storage.from_(BUCKET).upload(
            CACHE_FILE, 
            f, 
            file_options={"x-upsert": "true"}
        )
    print("✅ Done! Graph cached and uploaded.")
except Exception as e:
    print(f"❌ Upload failed: {e}")



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

# # --- 2. Build Graph with Weights & Time ---
# print(f"Building weighted temporal graph from {total_docs} docs...")
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
        
#         # Try to get timestamp, handle reblogs if necessary
#         ts = meta.get("post_timestamp")
#         if ts is None:
#             ts = meta.get("reblog_timestamp", 0)
        
#         if user_id and topic_id is not None and topic_id != -1:
#             u_node = f"User_{user_id}"
#             t_node = f"Topic_{topic_id}"
            
#             # Ensure nodes exist
#             if u_node not in G:
#                 G.add_node(u_node, label=f"User {user_id}", group="users", color="#97C2FC", size=10)
            
#             if t_node not in G:
#                 G.add_node(t_node, label=f"Topic {topic_id}", group="topics", color="#FB7E81", size=20)
            
#             # --- Edge Logic: Weight + Time ---
#             if G.has_edge(u_node, t_node):
#                 # Increment weight
#                 G[u_node][t_node]['weight'] += 1
#                 # Keep the MOST RECENT timestamp
#                 if ts > G[u_node][t_node]['last_timestamp']:
#                     G[u_node][t_node]['last_timestamp'] = ts
#             else:
#                 # Initialize new connection
#                 G.add_edge(u_node, t_node, weight=1, last_timestamp=ts)
            
#             # Track counts
#             topic_counts[topic_id] = topic_counts.get(topic_id, 0) + 1

#     if offset % 50000 == 0:
#         print(f"  Processed {offset}/{total_docs}...")

# # Resize topics
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

# print(f"Done! Graph cached.")