import chromadb
from bertopic import BERTopic
import numpy as np
import time

# --- CONFIGURATION ---
CHROMA_PATH = "/home/wyomike/topicBuzz/my_mastodon_db"
COLLECTION_NAME = "mastodon_posts"
MODEL_PATH = "my_mastodon_model_reduced" # Using the clean/reduced model
BATCH_SIZE = 2000  # Conservative batch size for read/write operations

# --- SETUP ---
print(f"Connecting to ChromaDB at {CHROMA_PATH}...")
client = chromadb.PersistentClient(path=CHROMA_PATH)
collection = client.get_collection(COLLECTION_NAME)

print(f"Loading BERTopic model from {MODEL_PATH}...")
topic_model = BERTopic.load(MODEL_PATH)

# Get total count to track progress
total_docs = collection.count()
print(f"Total documents to process: {total_docs}")

# --- MAIN LOOP ---
print("Starting bulk topic assignment...")
start_time = time.time()

for offset in range(0, total_docs, BATCH_SIZE):
    try:
        # 1. Fetch Batch (Include metadatas so we don't overwrite/lose existing ones!)
        batch_data = collection.get(
            limit=BATCH_SIZE,
            offset=offset,
            include=["documents", "embeddings", "metadatas"]
        )
        
        ids = batch_data['ids']
        docs = batch_data['documents']
        embeddings = batch_data['embeddings']
        metadatas = batch_data['metadatas']
        
        if not ids:
            break

        # 2. Predict Topics
        # We pass embeddings to speed this up massively (skips re-calculating them)
        # Note: We convert to numpy array as BERTopic expects it
        topics, _ = topic_model.transform(docs, np.array(embeddings))
        
        # 3. Prepare Metadata Updates
        updated_metadatas = []
        
        for i, topic_id in enumerate(topics):
            # Get existing metadata or create empty dict if None
            meta = metadatas[i] if metadatas[i] is not None else {}
            
            # Add the new cluster ID
            # We convert to int just to be safe for JSON serialization
            meta['cluster_id'] = int(topic_id)
            
            # OPTIONAL: Add the topic label string if you want it readable in DB
            meta['cluster_label'] = topic_model.get_topic_info(topic_id).Name.values[0]
            
            updated_metadatas.append(meta)

        # 4. Update ChromaDB
        # We ONLY update metadatas. Documents and embeddings remain untouched.
        collection.update(
            ids=ids,
            metadatas=updated_metadatas
        )
        
        # Progress Log
        processed_count = offset + len(ids)
        percent = (processed_count / total_docs) * 100
        elapsed = time.time() - start_time
        print(f"[{percent:.1f}%] Processed {processed_count}/{total_docs} docs... (Time: {elapsed:.0f}s)")

    except Exception as e:
        print(f"❌ Error processing batch starting at offset {offset}: {e}")
        # Optional: Decide if you want to 'continue' or 'break' here
        # continue 

print("✅ Done! All documents have been assigned a 'cluster_id'.")