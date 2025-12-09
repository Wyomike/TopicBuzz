import os
import time
import numpy as np
from supabase import create_client, Client
from bertopic import BERTopic
import shutil
import gzip
import json

# --- CONFIGURATION ---
SUPABASE_URL = os.environ.get("SUPABASE_URL") 
SUPABASE_KEY = os.environ.get("SUPABASE_KEY") 
MODEL_FILE = "my_online_mastodon_model.pkl"
COMPRESSED_FILE = "my_online_mastodon_model.pkl.gz"  # New filename for cloud
BUCKET = "topic_assets"
BATCH_SIZE = 500 

# --- 1. Connect to Supabase ---
if not SUPABASE_URL or not SUPABASE_KEY:
    raise ValueError("❌ Missing Supabase credentials in environment variables.")

print(f"Connecting to Supabase at {SUPABASE_URL}...")
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# --- 2. Load Model from Storage ---
def load_remote_model():
    # Check if we already have the raw model
    if os.path.exists(MODEL_FILE):
        return BERTopic.load(MODEL_FILE)

    print(f"☁️ Downloading {COMPRESSED_FILE} from Supabase...")
    try:
        # 1. Download the compressed file
        with open(COMPRESSED_FILE, 'wb') as f:
            res = supabase.storage.from_(BUCKET).download(COMPRESSED_FILE)
            f.write(res)
        
        # 2. Decompress it
        print("   -> Decompressing...")
        with gzip.open(COMPRESSED_FILE, 'rb') as f_in:
            with open(MODEL_FILE, 'wb') as f_out:
                shutil.copyfileobj(f_in, f_out)
        
        # 3. Load the raw model
        return BERTopic.load(MODEL_FILE)

    except Exception as e:
        print(f"⚠️ Could not load remote model: {e}")
        return None

topic_model = load_remote_model()
if topic_model is None:
    print("Exiting: Could not load model. Check Supabase Storage.")
    exit()

# --- 3. Main Loop ---
print("Starting bulk topic assignment...")
total_processed = 0
start_time = time.time()

while True:
    # --- START OF MAIN TRY BLOCK ---
    try:
        # A. Fetch Batch (Posts with no cluster_id yet)
        # Note: We do NOT use offset here. As we fix rows, they leave this query view.
        # We always fetch the 'top' 500 remaining.
        print(f"\nFetching next {BATCH_SIZE} unclustered posts...")
        
        response = supabase.table("posts") \
            .select("id, content, embedding") \
            .is_("cluster_id", "null") \
            .not_.is_("embedding", "null") \
            .limit(BATCH_SIZE) \
            .execute()
        
        posts = response.data
        
        if not posts:
            print("✅ No more unclustered posts found.")
            break

        # B. Prepare Data
        docs = [p['content'] for p in posts]
        ids = [p['id'] for p in posts]
        
        # FIX: Parse stringified vectors into actual lists
        parsed_embeddings = []
        for p in posts:
            emb = p['embedding']
            if isinstance(emb, str):
                try:
                    # It's a string "[0.1, 0.2]", so we parse it
                    parsed_embeddings.append(json.loads(emb))
                except json.JSONDecodeError:
                    # Fallback: manually strip brackets if json fails
                    clean_emb = emb.strip("[]")
                    parsed_embeddings.append([float(x) for x in clean_emb.split(",")])
            else:
                # It's already a list (standard behavior)
                parsed_embeddings.append(emb)

        # Convert to numpy array with explicit float64
        embeddings = np.array(parsed_embeddings, dtype=np.float64)

        # C. Predict Topics (using existing embeddings)
        print(f"   -> Predicting topics for {len(docs)} docs...")
        topics, _ = topic_model.transform(docs, embeddings)

        # D. Update Supabase
        print("   -> Updating database...")
        update_count = 0
        
        for pid, tid in zip(ids, topics):
            # Inner Try/Except: If one row fails (e.g. network blip), don't crash the whole batch
            try:
                supabase.table("posts").update({
                    "cluster_id": int(tid)
                }).eq("id", pid).execute()
                update_count += 1
            except Exception as row_error:
                print(f"      ⚠️ Failed to update post {pid}: {row_error}")

        total_processed += update_count
        elapsed = time.time() - start_time
        print(f"   -> Batch complete. Total processed: {total_processed} (Time: {elapsed:.0f}s)")

    # --- CATCH BLOCK FOR THE MAIN LOOP ---
    except Exception as e:
        print(f"❌ Critical Batch Error: {e}")
        print("   -> Sleeping for 10 seconds before retry...")
        time.sleep(10) 

print("✅ Done! All documents have been assigned a 'cluster_id'.")