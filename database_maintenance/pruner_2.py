from tqdm import tqdm
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

print("🔌 Connecting to Supabase...")
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

def prune_database():
    """Client-side pruning to keep DB size manageable."""
    tqdm.write("✂️ Checking database size for pruning...")
    try:
        result = supabase.table("posts").select("id", count="exact", head=True).execute()
        total_rows = result.count
        
        if total_rows > MAX_DB_ROWS:
            excess = total_rows - MAX_DB_ROWS
            tqdm.write(f"   Database has {total_rows} rows. Pruning {excess} old entries...")
            
            PRUNE_BATCH_SIZE = 50
            while excess > 0:
                batch_limit = min(excess, PRUNE_BATCH_SIZE)
                oldest = supabase.table("posts").select("id").order("effective_timestamp", desc=False).limit(batch_limit).execute()
                
                if not oldest.data: break
                    
                ids_to_delete = [row['id'] for row in oldest.data]
                supabase.table("posts").delete().in_("id", ids_to_delete).execute()
                
                excess -= len(ids_to_delete)
                tqdm.write(f"   - Pruned {len(ids_to_delete)} rows. {excess} remaining...")
            tqdm.write("✅ Pruning complete.")
        else:
            tqdm.write(f"   Database size OK ({total_rows} rows).")
            
    except Exception as e:
        tqdm.write(f"⚠️ Pruning failed: {e}")
# Ensure pruning happens even if loop ends naturally
prune_database()