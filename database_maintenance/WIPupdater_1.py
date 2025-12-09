import pandas as pd
from mastodon import Mastodon, MastodonNotFoundError, MastodonRatelimitError, MastodonAPIError, MastodonNetworkError
import json
import time
import os
from bs4 import BeautifulSoup
from datetime import datetime, timedelta, timezone
from tqdm import tqdm
from sentence_transformers import SentenceTransformer
from supabase import create_client, Client

# --- Configuration ---
SECRETS_PATH = "secrets.json"  # Adjust path if needed
CSV_PATH = "/home/wyomike/temp/topicBuzz/top1k_mastodon_users.csv" # Adjust path if needed
STATE_FILE = "fetcher_state.txt"
INSTANCE_URL = "https://mastodon.social"

# Database Configuration
SUPABASE_URL = os.environ.get("SUPABASE_URL") 
SUPABASE_KEY = os.environ.get("SUPABASE_KEY") 

# Tuning
SLEEP_BETWEEN_USERS = 1.0  # Seconds to wait between users
UPSERT_BATCH_SIZE = 20     # How many posts to accumulate before writing to DB

MAX_DB_ROWS = 100000

# --- 1. Setup & Connection ---
print("⏳ Loading embedding model...")
model = SentenceTransformer('all-MiniLM-L6-v2')

print("🔌 Connecting to Supabase...")
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

def load_secrets():
    """Loads access token from json file."""
    try:
        path = SECRETS_PATH
        if not os.path.exists(path):
            path = r"C:\CS452\TopicBuzz\secrets.json"
        
        if not os.path.exists(path):
            print(f"❌ Error: Cannot find secrets.json at {path}")
            return None
            
        with open(path) as f:
            return json.load(f)["token"]
    except Exception as e:
        print(f"❌ Error loading secrets: {e}")
        return None

access_token = load_secrets()
if not access_token: exit()

try:
    api = Mastodon(
        access_token=access_token,
        api_base_url=INSTANCE_URL,
        request_timeout=15 
    )
    print(f"✅ Successfully connected to {INSTANCE_URL}")
except Exception as e:
    print(f"❌ Error connecting to Mastodon: {e}")
    exit()

# --- 2. Helper Functions ---
def get_users_list():
    """Loads users from CSV."""
    path = CSV_PATH
    if not os.path.exists(path):
        path = r"C:\CS452\TopicBuzz\top10k_mastodon_users.csv"
    
    if not os.path.exists(path):
        print(f"❌ Error: Cannot find CSV at {path}")
        return []

    df = pd.read_csv(path)
    return df['handle'].tolist()

def get_start_index():
    if os.path.exists(STATE_FILE):
        with open(STATE_FILE, 'r') as f:
            try:
                return int(f.read().strip())
            except:
                return 0
    return 0

def save_state(index):
    with open(STATE_FILE, 'w') as f:
        f.write(str(index))

def clean_content(html_content):
    """Strips HTML for embedding generation."""
    if not html_content: return ""
    return BeautifulSoup(html_content, 'html.parser').get_text().strip()

def get_unix_timestamp(dt_obj):
    """Converts a timezone-aware datetime to UNIX timestamp (int)."""
    try:
        return int(dt_obj.timestamp())
    except:
        return int(time.time())

def process_and_upsert(post_buffer):
    """Generates embeddings and upserts a batch of posts to Supabase."""
    if not post_buffer:
        return

    # Filter for valid English content
    valid_batch = [p for p in post_buffer if p.get('language') == 'en' and p.get('content')]
    
    if not valid_batch:
        return

    tqdm.write(f"   ⚡ Generating embeddings for {len(valid_batch)} posts...")
    
    # 1. Generate Embeddings
    clean_texts = [clean_content(p['content']) for p in valid_batch]
    embeddings = model.encode(clean_texts)

    # 2. Prepare Rows
    rows_to_insert = []
    for i, post in enumerate(valid_batch):
        reblog = post.get('reblog')
        actual_post = reblog if reblog else post
        
        # Mastodon.py returns datetime objects
        eff_ts = get_unix_timestamp(post['created_at'])
        
        # Determine User IDs (Handle missing account data gracefully)
        author_id = str(actual_post['account']['id']) if actual_post.get('account') else None
        reblogger_id = str(post['account']['id']) if reblog and post.get('account') else None

        if not author_id: continue # Skip if data is malformed

        row = {
            "id": str(post['id']),
            "content": post['content'], 
            "embedding": embeddings[i].tolist(),
            "effective_timestamp": eff_ts,
            "type": "reblog" if reblog else "original",
            "language": post.get('language'),
            "author_user_id": author_id,
            "reblogger_user_id": reblogger_id,
            "post_timestamp": get_unix_timestamp(actual_post['created_at']),
            "reblog_timestamp": eff_ts if reblog else None
        }
        rows_to_insert.append(row)

    # 3. Upsert
    if rows_to_insert:
        try:
            supabase.table("posts").upsert(rows_to_insert).execute()
            tqdm.write(f"   💾 Saved {len(rows_to_insert)} posts to DB.")
        except Exception as e:
            tqdm.write(f"   ❌ Database error: {e}")

# --- 3. Main Fetch Loop ---
users = get_users_list()
print(f"📚 Loaded {len(users)} users.")

start_index = get_start_index()
print(f"🔄 Resuming from user #{start_index}...")

# Calculate 24 hour cutoff (UTC)
cutoff_date = datetime.now(timezone.utc) - timedelta(days=1)
print(f"🕒 Fetching posts newer than: {cutoff_date.strftime('%Y-%m-%d %H:%M:%S UTC')}")

post_buffer = []

for i in tqdm(range(start_index, len(users)), initial=start_index, total=len(users), unit="user", desc="Processing Users"):
    handle = users[i]
    
    try:
        # Retry loop for server errors
        max_retries = 3
        account_id = None
        
        for attempt in range(max_retries):
            try:
                user_search = api.account_lookup(handle)
                account_id = user_search['id']
                break 
            except MastodonNotFoundError:
                tqdm.write(f"   ⚠️ User not found: {handle}. Skipping.")
                break 
            except MastodonRatelimitError:
                tqdm.write("   ⏳ Rate limit hit! Sleeping 60s...")
                time.sleep(60)
                continue
            except (MastodonAPIError, MastodonNetworkError) as e:
                error_code = e.args[1] if len(e.args) > 1 and isinstance(e.args[1], int) else 0
                if error_code >= 500 or isinstance(e, MastodonNetworkError):
                    if attempt < max_retries - 1:
                        wait = 15 * (attempt + 1)
                        tqdm.write(f"   🔥 Server error ({error_code}) for {handle}. Waiting {wait}s...")
                        time.sleep(wait)
                        continue
                tqdm.write(f"   ❌ Lookup failed for {handle}: {e}")
                break
        
        if not account_id:
            save_state(i + 1)
            continue

        # B. Fetch Statuses
        recent_posts = []
        max_id = None
        keep_fetching = True
        
        while keep_fetching:
            try:
                batch = api.account_statuses(account_id, limit=40, max_id=max_id)
                
                if not batch:
                    break
                
                batch_fresh = []
                for p in batch:
                    created_at = p['created_at']
                    if created_at.tzinfo is None:
                        created_at = created_at.replace(tzinfo=timezone.utc)
                    
                    if created_at > cutoff_date:
                        batch_fresh.append(p)

                recent_posts.extend(batch_fresh)
                
                if len(batch_fresh) < len(batch):
                    keep_fetching = False
                else:
                    max_id = batch[-1]['id']
                    time.sleep(0.2) 

            except MastodonRatelimitError:
                tqdm.write("   ⏳ Rate limit on statuses! Sleeping 60s...")
                time.sleep(60)
                continue
            except Exception as e:
                tqdm.write(f"   ⚠️ Error fetching statuses for {handle}: {e}")
                break

        # C. Add to Buffer
        if recent_posts:
            tqdm.write(f"   📄 {handle}: Found {len(recent_posts)} new posts.")
            post_buffer.extend(recent_posts)

        # D. Flush Buffer if full
        if len(post_buffer) >= UPSERT_BATCH_SIZE:
            process_and_upsert(post_buffer)
            post_buffer = [] # Clear buffer
            save_state(i + 1) # Save progress only after successful write

    except KeyboardInterrupt:
        print("\n🛑 Stopped by user.")
        break
    except Exception as e:
        tqdm.write(f"   ❌ Unexpected error processing {handle}: {e}")

    # Advance state if buffer wasn't flushed (user processed, but buffer not full yet)
    if len(post_buffer) < UPSERT_BATCH_SIZE:
        save_state(i + 1)
        
    time.sleep(SLEEP_BETWEEN_USERS) 

if post_buffer:
    process_and_upsert(post_buffer)
    save_state(len(users))

print("\n🎉 Finished processing all users!")