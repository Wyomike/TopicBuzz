import os
import json
import time
from tqdm import tqdm
import google.genai as genai
from bertopic import BERTopic
from supabase import create_client, Client

# --- CONFIGURATION ---
SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY")
GOOGLE_API_KEY = os.environ.get("GOOGLE_KEY")

MODEL_FILE = "my_online_mastodon_model.pkl"
OUTPUT_JSON = "topic_labels.json"
BUCKET = "topic_assets"

NSFW_KEYWORDS = {
    "nsfw", "porn", "nude", "naked", "sex", "18+", "xxx", 
    "cum", "dick", "pussy", "hentai", "erotic", "onlyfans",
    "boobs", "tits", "cock", "slut", "whore", "bitch", "incest",
    "lewd", "horny", "sensual", "fetish", "bondage"
}

# --- SETUP ---
if not SUPABASE_URL or not SUPABASE_KEY or not GOOGLE_API_KEY:
    raise ValueError("❌ Missing API Keys (Supabase or Google) in environment variables.")

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
client = genai.Client(api_key=GOOGLE_API_KEY)

# --- HELPER: Download/Load Model ---
def load_remote_model():
    """Downloads model from Supabase if not present locally."""
    if not os.path.exists(MODEL_FILE):
        print(f"☁️ Downloading {MODEL_FILE} from Supabase Storage...")
        try:
            with open(MODEL_FILE, 'wb') as f:
                res = supabase.storage.from_(BUCKET).download(MODEL_FILE)
                f.write(res)
        except Exception as e:
            print(f"❌ Error downloading model: {e}")
            return None
    
    print(f"Loading BERTopic model from {MODEL_FILE}...")
    try:
        return BERTopic.load(MODEL_FILE)
    except Exception as e:
        print(f"❌ Error loading pickle: {e}")
        return None

def get_safe_topic_ids(model, nsfw_set):
    """
    Returns a list of Topic IDs that do NOT contain any blocklisted words
    in their top 10 keywords.
    """
    safe_ids = []
    unsafe_ids = []
    
    # get_topics() returns a dictionary: {topic_id: [(word, score), ...]}
    all_topics = model.get_topics()
    
    print(f"Scanning {len(all_topics)} topics for NSFW content...")
    
    for topic_id, words_with_scores in all_topics.items():
        # Topic -1 is outliers.
        topic_words = {word for word, score in words_with_scores}
        
        # Check for intersection
        intersection = topic_words.intersection(nsfw_set)
        
        if intersection:
            # print(f"  [BLOCKED] Topic {topic_id}")
            unsafe_ids.append(topic_id)
        else:
            safe_ids.append(topic_id)
            
    print(f"\nResult: {len(safe_ids)} Safe, {len(unsafe_ids)} Unsafe.")
    return safe_ids

def generate_labels():
    # 1. Load Model
    topic_model = load_remote_model()
    if topic_model is None:
        return

    # 2. Get Info
    info = topic_model.get_topic_info()
    print(f"Found {len(info)} topics.")
    safe_topics = get_safe_topic_ids(topic_model, nsfw_set=NSFW_KEYWORDS)
    
    labels_map = {}

    print("Asking Gemini to label topics (with Rate Limit handling)...")
    
    for index, row in tqdm(info.iterrows(), total=len(info)):
        topic_id = row['Topic']
        
        # Skip unsafe topics
        if topic_id not in safe_topics:
            labels_map[f"Topic_{topic_id}"] = "NSFW Content" 
            continue
            
        # Handle Outliers
        if topic_id == -1: 
            labels_map[f"Topic_{topic_id}"] = "Outliers / Noise"
            continue

        # 3. Extract Data & Handle Missing Docs
        keywords = row['Representation']
        docs = row['Representative_Docs']

        if not isinstance(docs, list) or len(docs) == 0:
            try:
                res = supabase.table("posts") \
                    .select("content") \
                    .eq("cluster_id", int(topic_id)) \
                    .limit(3) \
                    .execute()
                docs = [r['content'] for r in res.data]
            except Exception:
                docs = []

        if not docs: 
            docs_text = "(No examples available yet)"
        else:
            docs_text = chr(10).join([f"- {str(d)[:300]}..." for d in docs[:3]])

        # 4. Construct Prompt
        prompt = f"""
        I have a cluster of social media posts from Mastodon.
        
        Keywords: {', '.join(keywords[:10])}
        
        Representative Posts:
        {docs_text}
        
        Based on this, provide a short, specific, natural language label (max 5 words) for this topic.
        Do not use quotes. Just the label.
        """
        
        # 5. Call Gemini with RETRY LOGIC
        max_retries = 3
        attempt = 0
        success = False

        while attempt < max_retries:
            try:
                response = client.models.generate_content(
                    model='gemini-2.5-flash',
                    contents=prompt
                )
                label = response.text.strip()
                labels_map[f"Topic_{topic_id}"] = label
                
                # Success! Increase sleep slightly to prevent rapid-fire hitting limits
                time.sleep(4.0) 
                success = True
                break

            except Exception as e:
                error_str = str(e)
                # Check for Rate Limit (429) or Resource Exhausted
                if "429" in error_str or "RESOURCE_EXHAUSTED" in error_str:
                    print(f"\n   ⏳ Quota limit hit on Topic {topic_id}. Sleeping 60s to refill bucket...")
                    time.sleep(60) 
                    attempt += 1
                else:
                    print(f"\n   ❌ Non-quota error on Topic {topic_id}: {e}")
                    break
        
        # If we failed after retries, use fallback
        if not success:
            labels_map[f"Topic_{topic_id}"] = f"Topic {topic_id}"

    # 6. Save locally
    with open(OUTPUT_JSON, "w") as f:
        json.dump(labels_map, f, indent=2)

    # 7. Upload to Supabase
    print(f"☁️ Uploading {OUTPUT_JSON} to Supabase...")
    with open(OUTPUT_JSON, "rb") as f:
        supabase.storage.from_(BUCKET).upload(
            OUTPUT_JSON, 
            f, 
            file_options={"x-upsert": "true"}
        )
        
    print(f"Success! Labels saved and uploaded.")

if __name__ == "__main__":
    generate_labels()