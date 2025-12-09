import os
import shutil
import gzip
import supabase
from bertopic import BERTopic


# --- CONFIGURATION ---
SUPABASE_URL = os.environ.get("SUPABASE_URL") # Ensure these are in your .bashrc or .env
SUPABASE_KEY = os.environ.get("SUPABASE_KEY") 

# MODEL_PATH = "my_online_mastodon_model.pkl"
LABELS_PATH = "topic_labels.json"
STATE_FILE = "training_state.json" # Tracks the last timestamp we processed

MODEL_FILE = "/home/wyomike/temp/topicBuzz/modelUpdating/my_online_mastodon_model.pkl"
COMPRESSED_FILE = "my_online_mastodon_model.pkl.gz"  # New filename for cloud
BUCKET = "topic_assets"
supabase = supabase.create_client(SUPABASE_URL, SUPABASE_KEY)


with open(MODEL_FILE, 'rb') as f_in:
    with gzip.open(COMPRESSED_FILE, 'wb') as f_out:
        shutil.copyfileobj(f_in, f_out)

# 3. Upload the COMPRESSED file
print(f"☁️ Uploading {COMPRESSED_FILE} to Supabase...")
with open(COMPRESSED_FILE, 'rb') as f:
    supabase.storage.from_(BUCKET).upload(
        path=COMPRESSED_FILE, 
        file=f, 
        file_options={"x-upsert": "true"}
    )
print("uploaded?")

# Clean up local files to save space
# if os.path.exists(MODEL_FILE): os.remove(MODEL_FILE)
# if os.path.exists(COMPRESSED_FILE): os.remove(COMPRESSED_FILE)

# model = BERTopic.load("/home/wyomike/temp/topicBuzz/modelUpdating/my_online_mastodon_model.pkl")

# save_remote_model(model)