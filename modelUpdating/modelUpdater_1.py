import os
import json
import shutil
import numpy as np
import gzip
from supabase import create_client, Client, ClientOptions
from bertopic import BERTopic
from sentence_transformers import SentenceTransformer
from sklearn.cluster import MiniBatchKMeans
from sklearn.decomposition import IncrementalPCA
from bertopic.vectorizers import OnlineCountVectorizer

# --- CONFIGURATION ---
SUPABASE_URL = os.environ.get("SUPABASE_URL") 
SUPABASE_KEY = os.environ.get("SUPABASE_KEY") 

MODEL_FILE = "my_online_mastodon_model.pkl"
COMPRESSED_FILE = "my_online_mastodon_model.pkl.gz"
BUCKET = "topic_assets"
LABELS_PATH = "topic_labels.json"
STATE_FILE = "training_state.json"
EMBEDDING_MODEL_NAME = "all-MiniLM-L6-v2" 

# --- HELPER: Robust Model Loader ---
def load_remote_model():
    # 1. Try loading local file first
    if os.path.exists(MODEL_FILE):
        print(f"📂 Found local file {MODEL_FILE}. Attempting load...")
        try:
            return BERTopic.load(MODEL_FILE)
        except Exception as e:
            print(f"⚠️ Local file exists but is corrupt: {e}")
            print("   -> Deleting local file and forcing download.")
            os.remove(MODEL_FILE)

    # 2. Download from Supabase
    print(f"☁️ Downloading {COMPRESSED_FILE} from Supabase...")
    try:
        # Download
        with open(COMPRESSED_FILE, 'wb') as f:
            res = supabase.storage.from_(BUCKET).download(COMPRESSED_FILE)
            f.write(res)
        
        # Decompress
        print("   -> Decompressing...")
        with gzip.open(COMPRESSED_FILE, 'rb') as f_in:
            with open(MODEL_FILE, 'wb') as f_out:
                shutil.copyfileobj(f_in, f_out)
        
        # Load
        return BERTopic.load(MODEL_FILE)

    except Exception as e:
        print(f"❌ Critical: Could not load model from cloud: {e}")
        # Check if the file is 0 bytes (common error)
        if os.path.exists(COMPRESSED_FILE):
            size = os.path.getsize(COMPRESSED_FILE)
            print(f"   -> Downloaded file size: {size / 1024:.2f} KB")
        return None

def save_remote_model(model):
    print("💾 Saving and compressing model...")
    model.save(MODEL_FILE, serialization="pickle")
    
    with open(MODEL_FILE, 'rb') as f_in:
        with gzip.open(COMPRESSED_FILE, 'wb') as f_out:
            shutil.copyfileobj(f_in, f_out)
    
    print(f"☁️ Uploading {COMPRESSED_FILE} to Supabase...")
    with open(COMPRESSED_FILE, 'rb') as f:
        supabase.storage.from_(BUCKET).upload(
            path=COMPRESSED_FILE, 
            file=f, 
            file_options={"x-upsert": "true"}
        )
    
    # Cleanup
    if os.path.exists(MODEL_FILE): os.remove(MODEL_FILE)
    if os.path.exists(COMPRESSED_FILE): os.remove(COMPRESSED_FILE)

# --- 1. Setup ---
if not SUPABASE_URL or not SUPABASE_KEY:
    raise ValueError("Missing Supabase credentials.")

options = ClientOptions(
    postgrest_client_timeout=600,
    storage_client_timeout=600
)

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY, options=options)
embedding_model = SentenceTransformer(EMBEDDING_MODEL_NAME)

# --- 2. Load State ---
print("📥 Checking for previous state...")
last_processed_ts = 0

try:
    # Attempt download
    try:
        res = supabase.storage.from_(BUCKET).download(STATE_FILE)
        with open(STATE_FILE, 'wb') as f:
            f.write(res)
    except Exception:
        print("   -> No remote state found. Starting fresh.")

    # Attempt read
    if os.path.exists(STATE_FILE):
        with open(STATE_FILE, 'r') as f:
            content = f.read().strip()
            if content:
                state = json.loads(content)
                last_processed_ts = state.get('last_timestamp', 0)

    print(f"   -> Resuming from timestamp: {last_processed_ts}")

except Exception as e:
    print(f"   ⚠️ Error reading state: {e}. Defaulting to 0.")
    last_processed_ts = 0

# --- 3. Load Model ---
topic_model = load_remote_model()

if topic_model is None:
    print("✨ Creating NEW model structure (Start from Scratch)...")
    # Initialize fresh model
    umap_model = IncrementalPCA(n_components=5)
    cluster_model = MiniBatchKMeans(n_clusters=200, random_state=42)
    vectorizer_model = OnlineCountVectorizer(stop_words="english", min_df=10)
    
    topic_model = BERTopic(
        embedding_model=None, 
        umap_model=umap_model,
        hdbscan_model=cluster_model,
        vectorizer_model=vectorizer_model
    )
else:
    print("✅ Model loaded successfully!")

# --- 4. Training Loop ---
BATCH_SIZE = 1000
total_processed = 0
new_max_ts = last_processed_ts

while True:
    try:
        response = supabase.table("posts") \
            .select("content, post_timestamp") \
            .gt("post_timestamp", last_processed_ts) \
            .order("post_timestamp", desc=False) \
            .limit(BATCH_SIZE) \
            .execute()
        
        posts = response.data
        if not posts:
            print("✅ No more new data.")
            break

        # Filter empty content (CRITICAL FIX for Scipy crash)
        # We strip whitespace and ensure len > 0
        batch_docs = []
        batch_timestamps = []
        
        for p in posts:
            content = p.get('content')
            if content and isinstance(content, str) and len(content.strip()) > 0:
                batch_docs.append(content)
                batch_timestamps.append(p['post_timestamp'])

        if not batch_docs:
            # If batch was empty/invalid, just move the cursor forward so we don't get stuck
            last_processed_ts = max([p['post_timestamp'] for p in posts])
            continue

        current_batch_max = max(batch_timestamps)
        last_processed_ts = current_batch_max
        new_max_ts = max(new_max_ts, current_batch_max)

        print(f"🧠 Processing {len(batch_docs)} posts...")
        
        # Generate Embeddings
        embeddings = embedding_model.encode(batch_docs, show_progress_bar=False)
        
        # Train (with float64 cast)
        topic_model.partial_fit(batch_docs, np.array(embeddings).astype(np.float64))
        
        total_processed += len(batch_docs)
        print(f"   -> Success. Total new: {total_processed}")

    except Exception as e:
        print(f"❌ Batch Error: {e}")
        break

# --- 5. Save ---
if total_processed > 0:
    print(f"💾 Saving updated assets to Supabase...")

    # Labels
    labels_map = {}
    info_df = topic_model.get_topic_info()
    for index, row in info_df.iterrows():
        topic_id = row['Topic']
        labels_map[f"Topic_{topic_id}"] = "Outliers" if topic_id == -1 else row['Name']

    # Uploads
    save_remote_model(topic_model)

    print("   -> Uploading labels...")
    with open(LABELS_PATH, "w") as f:
        json.dump(labels_map, f)
    with open(LABELS_PATH, "rb") as f:
        supabase.storage.from_(BUCKET).upload(LABELS_PATH, f, file_options={"x-upsert": "true"})

    print(f"   -> Updating state to {new_max_ts}...")
    with open(STATE_FILE, "w") as f:
        json.dump({"last_timestamp": new_max_ts}, f)
    with open(STATE_FILE, "rb") as f:
        supabase.storage.from_(BUCKET).upload(STATE_FILE, f, file_options={"x-upsert": "true"})

    print("✅ Done!")
else:
    print("💤 No changes made.")