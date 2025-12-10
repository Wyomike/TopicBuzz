import os
import json
import time
from tqdm import tqdm
from bertopic import BERTopic
from supabase import create_client, Client
from openai import OpenAI 

# --- CONFIGURATION ---
SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY")

MODEL_FILE = "my_online_mastodon_model.pkl"
OUTPUT_JSON = "topic_labels.json"
BUCKET = "topic_assets"
OLLAMA_MODEL_NAME = "my-llama"  # The name you created with 'ollama create'

NSFW_KEYWORDS = {
    "nsfw", "porn", "nude", "naked", "sex", "18+", "xxx", 
    "cum", "dick", "pussy", "hentai", "erotic", "onlyfans",
    "boobs", "tits", "cock", "slut", "whore", "bitch", "incest",
    "lewd", "horny", "sensual", "fetish", "bondage"
}

# --- SETUP ---
if not SUPABASE_URL or not SUPABASE_KEY:
    raise ValueError("❌ Missing Supabase API Keys.")

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# Point to local Ollama server
client = OpenAI(
    base_url='http://localhost:11434/v1',
    api_key='ollama', # Required but unused
)

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

    # 2. Get Info & Safe List
    info = topic_model.get_topic_info()
    print(f"Found {len(info)} topics.")
    
    # --- RESTORED LOGIC: Filter topics before LLM ---
    safe_topics = get_safe_topic_ids(topic_model, nsfw_set=NSFW_KEYWORDS)
    
    labels_map = {}

    print(f"🚀 Labeling topics via Ollama ({OLLAMA_MODEL_NAME})...")
    
    for index, row in tqdm(info.iterrows(), total=len(info)):
        topic_id = row['Topic']
        
        # Check 1: Is it NSFW?
        if topic_id not in safe_topics:
            labels_map[f"Topic_{topic_id}"] = "NSFW Content" 
            continue
            
        # Check 2: Is it Outliers?
        if topic_id == -1: 
            labels_map[f"Topic_{topic_id}"] = "Outliers / Noise"
            continue

        # 3. Extract Data & Handle Missing Docs (Supabase Fallback)
        keywords = row['Representation']
        docs = row['Representative_Docs']

        if not isinstance(docs, list) or len(docs) == 0:
            try:
                # Fallback: Fetch real posts from DB if model has none
                res = supabase.table("posts") \
                    .select("content") \
                    .eq("cluster_id", int(topic_id)) \
                    .limit(3) \
                    .execute()
                docs = [r['content'] for r in res.data]
            except Exception:
                docs = []

        if not docs: 
            docs_text = "(No examples available)"
        else:
            docs_text = "\n".join([f"- {str(d)[:200]}..." for d in docs[:3]])

        # 4. Construct Prompt
        system_msg = "You are a helpful classifier. Create a label (max 5 words) for the topic described by the keywords and posts. Do not use quotes."
        user_msg = f"""
        Keywords: {', '.join(keywords[:10])}
        Posts:
        {docs_text}
        
        Label:
        """
        
        # 5. Call Local Ollama
        try:
            response = client.chat.completions.create(
                model=OLLAMA_MODEL_NAME, 
                messages=[
                    {"role": "system", "content": system_msg},
                    {"role": "user", "content": user_msg}
                ],
                temperature=0.3, 
                max_tokens=20,   
            )
            
            label = response.choices[0].message.content.strip().replace('"', '')
            labels_map[f"Topic_{topic_id}"] = label

        except Exception as e:
            print(f"\n ❌ Error on Topic {topic_id}: {e}")
            # Fallback
            fallback = ", ".join(keywords[:3]).title()
            labels_map[f"Topic_{topic_id}"] = fallback

    # 6. Save locally
    with open(f"../{OUTPUT_JSON}", "w") as f:
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