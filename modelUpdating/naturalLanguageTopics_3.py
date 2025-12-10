# # import os
# # import json
# # import time
# # from tqdm import tqdm
# # import google.genai as genai
# # from google.genai import types # Import types for configuration
# # from bertopic import BERTopic
# # from supabase import create_client, Client

# # # --- CONFIGURATION ---
# # SUPABASE_URL = os.environ.get("SUPABASE_URL")
# # SUPABASE_KEY = os.environ.get("SUPABASE_KEY")
# # GOOGLE_API_KEY = os.environ.get("GOOGLE_KEY")

# # MODEL_FILE = "my_online_mastodon_model.pkl"
# # OUTPUT_JSON = "topic_labels.json"
# # BUCKET = "topic_assets"

# # NSFW_KEYWORDS = {
# #     "nsfw", "porn", "nude", "naked", "sex", "18+", "xxx", 
# #     "cum", "dick", "pussy", "hentai", "erotic", "onlyfans",
# #     "boobs", "tits", "cock", "slut", "whore", "bitch", "incest",
# #     "lewd", "horny", "sensual", "fetish", "bondage"
# # }

# # # --- SETUP ---
# # if not SUPABASE_URL or not SUPABASE_KEY or not GOOGLE_API_KEY:
# #     raise ValueError("❌ Missing API Keys (Supabase or Google) in environment variables.")

# # supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
# # client = genai.Client(api_key=GOOGLE_API_KEY)

# # # --- HELPER: Download/Load Model ---
# # def load_remote_model():
# #     """Downloads model from Supabase if not present locally."""
# #     if not os.path.exists(MODEL_FILE):
# #         print(f"☁️ Downloading {MODEL_FILE} from Supabase Storage...")
# #         try:
# #             with open(MODEL_FILE, 'wb') as f:
# #                 res = supabase.storage.from_(BUCKET).download(MODEL_FILE)
# #                 f.write(res)
# #         except Exception as e:
# #             print(f"❌ Error downloading model: {e}")
# #             return None
    
# #     print(f"Loading BERTopic model from {MODEL_FILE}...")
# #     try:
# #         return BERTopic.load(MODEL_FILE)
# #     except Exception as e:
# #         print(f"❌ Error loading pickle: {e}")
# #         return None

# # def get_safe_topic_ids(model, nsfw_set):
# #     """
# #     Returns a list of Topic IDs that do NOT contain any blocklisted words
# #     in their top 10 keywords.
# #     """
# #     safe_ids = []
# #     unsafe_ids = []
    
# #     # get_topics() returns a dictionary: {topic_id: [(word, score), ...]}
# #     all_topics = model.get_topics()
    
# #     print(f"Scanning {len(all_topics)} topics for NSFW content...")
    
# #     for topic_id, words_with_scores in all_topics.items():
# #         # Topic -1 is outliers.
# #         topic_words = {word for word, score in words_with_scores}
        
# #         # Check for intersection
# #         intersection = topic_words.intersection(nsfw_set)
        
# #         if intersection:
# #             # print(f"  [BLOCKED] Topic {topic_id}")
# #             unsafe_ids.append(topic_id)
# #         else:
# #             safe_ids.append(topic_id)
            
# #     print(f"\nResult: {len(safe_ids)} Safe, {len(unsafe_ids)} Unsafe.")
# #     return safe_ids

# # def generate_labels():
# #     # 1. Load Model
# #     topic_model = load_remote_model()
# #     if topic_model is None:
# #         return

# #     # 2. Get Info
# #     info = topic_model.get_topic_info()
# #     print(f"Found {len(info)} topics.")
# #     safe_topics = get_safe_topic_ids(topic_model, nsfw_set=NSFW_KEYWORDS)
    
# #     labels_map = {}

# #     print("Asking Gemini to label topics (with Rate Limit handling)...")
    
# #     for index, row in tqdm(info.iterrows(), total=len(info)):
# #         topic_id = row['Topic']
        
# #         # Skip unsafe topics
# #         if topic_id not in safe_topics:
# #             labels_map[f"Topic_{topic_id}"] = "NSFW Content" 
# #             continue
            
# #         # Handle Outliers
# #         if topic_id == -1: 
# #             labels_map[f"Topic_{topic_id}"] = "Outliers / Noise"
# #             continue

# #         # 3. Extract Data & Handle Missing Docs
# #         keywords = row['Representation']
# #         docs = row['Representative_Docs']

# #         if not isinstance(docs, list) or len(docs) == 0:
# #             try:
# #                 res = supabase.table("posts") \
# #                     .select("content") \
# #                     .eq("cluster_id", int(topic_id)) \
# #                     .limit(3) \
# #                     .execute()
# #                 docs = [r['content'] for r in res.data]
# #             except Exception:
# #                 docs = []

# #         if not docs: 
# #             docs_text = "(No examples available yet)"
# #         else:
# #             docs_text = chr(10).join([f"- {str(d)[:300]}..." for d in docs[:3]])

# #         # 4. Construct Prompt (Unchanged)
# #         prompt = f"""
# #         I have a cluster of social media posts from Mastodon.
        
# #         Keywords: {', '.join(keywords[:10])}
        
# #         Representative Posts:
# #         {docs_text}
        
# #         Based on this, provide a short, specific, natural language label (max 5 words) for this topic.
# #         Do not use quotes. Just the label.
# #         """
        
# #         # --- NEW: Configure Safety Settings to BLOCK_NONE ---
# #         # This prevents Gemini from refusing to label "spicy" but non-pornographic topics
# #         safety_config = [
# #             types.SafetySetting(
# #                 category="HARM_CATEGORY_HATE_SPEECH",
# #                 threshold="BLOCK_NONE",
# #             ),
# #             types.SafetySetting(
# #                 category="HARM_CATEGORY_DANGEROUS_CONTENT",
# #                 threshold="BLOCK_NONE",
# #             ),
# #             types.SafetySetting(
# #                 category="HARM_CATEGORY_SEXUALLY_EXPLICIT",
# #                 threshold="BLOCK_NONE",
# #             ),
# #             types.SafetySetting(
# #                 category="HARM_CATEGORY_HARASSMENT",
# #                 threshold="BLOCK_NONE",
# #             ),
# #         ]

# #         # 5. Call Gemini with RETRY LOGIC
# #         max_retries = 3
# #         attempt = 0
# #         success = False

# #         while attempt < max_retries:
# #             try:
# #                 response = client.models.generate_content(
# #                     model='gemini-2.0-flash-lite-preview-02-05',
# #                     contents=prompt,
# #                     config=types.GenerateContentConfig(
# #                         safety_settings=safety_config
# #                     )
# #                 )
                
# #                 # Check if the response was blocked despite settings
# #                 if not response.text:
# #                     raise ValueError("Empty response (likely safety block)")

# #                 label = response.text.strip()
# #                 labels_map[f"Topic_{topic_id}"] = label
                
# #                 time.sleep(1.5) # Reduced sleep slightly as 4.0 is conservative
# #                 success = True
# #                 break

# #             except Exception as e:
# #                 error_str = str(e)
# #                 if "429" in error_str or "RESOURCE_EXHAUSTED" in error_str:
# #                     print(f"\n   ⏳ Quota limit hit on Topic {topic_id}. Sleeping 60s...")
# #                     time.sleep(60) 
# #                     attempt += 1
# #                 else:
# #                     print(f"\n   ❌ Error on Topic {topic_id}: {e}")
# #                     # Do not break immediately; logic will just try again or fail gracefully
# #                     attempt += 1 
        
# #         # 6. IMPROVED FALLBACK
# #         if not success:
# #             # If API fails, use the top 3 keywords naturally joined
# #             fallback_label = ", ".join(keywords[:3]).title()
# #             print(f"   ⚠️ Failed to generate. Using fallback: {fallback_label}")
# #             labels_map[f"Topic_{topic_id}"] = fallback_label

# # if __name__ == "__main__":
# #     generate_labels()



# import os
# import json
# import time
# from tqdm import tqdm
# from bertopic import BERTopic
# from supabase import create_client, Client

# # --- NEW: Import Local LLM Library ---
# # If you get an import error: pip install llama-cpp-python
# from llama_cpp import Llama 

# # --- CONFIGURATION ---
# SUPABASE_URL = os.environ.get("SUPABASE_URL")
# SUPABASE_KEY = os.environ.get("SUPABASE_KEY")

# MODEL_FILE = "my_online_mastodon_model.pkl"
# OUTPUT_JSON = "topic_labels.json"
# BUCKET = "topic_assets"

# # Converted Windows path to WSL (Linux) path
# # Original: C:\Users\betha\.lmstudio\models\matrixportalx\Meta-Llama-3.1-8B-Instruct-Q3_K_M-GGUF\meta-llama-3.1-8b-instruct-q3_k_m.gguf
# LOCAL_MODEL_PATH = "/home/wyomike/temp/meta-llama-3.1-8b-instruct-q3_k_m.gguf"

# NSFW_KEYWORDS = {
#     "nsfw", "porn", "nude", "naked", "sex", "18+", "xxx", 
#     "cum", "dick", "pussy", "hentai", "erotic", "onlyfans",
#     "boobs", "tits", "cock", "slut", "whore", "bitch", "incest",
#     "lewd", "horny", "sensual", "fetish", "bondage"
# }

# # --- SETUP ---
# if not SUPABASE_URL or not SUPABASE_KEY:
#     raise ValueError("❌ Missing Supabase API Keys.")

# if not os.path.exists(LOCAL_MODEL_PATH):
#     raise FileNotFoundError(f"❌ Cannot find model file at: {LOCAL_MODEL_PATH}\n(Make sure you are pointing to the correct /mnt/c/ path in WSL)")

# supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# # --- LOAD LOCAL LLM ---
# print(f"🚀 Loading Local Llama 3.1 from disk...")
# # n_gpu_layers=-1 tells it to put ALL layers on your GTX 1060
# # n_ctx=4096 sets the context window (reduce to 2048 if you run out of VRAM)
# llm = Llama(
#     model_path=LOCAL_MODEL_PATH,
#     n_gpu_layers=-1, 
#     n_ctx=4096,
#     verbose=False
# )

# # --- HELPER: Download/Load Model ---
# def load_remote_model():
#     """Downloads model from Supabase if not present locally."""
#     if not os.path.exists(MODEL_FILE):
#         print(f"☁️ Downloading {MODEL_FILE} from Supabase Storage...")
#         try:
#             with open(MODEL_FILE, 'wb') as f:
#                 res = supabase.storage.from_(BUCKET).download(MODEL_FILE)
#                 f.write(res)
#         except Exception as e:
#             print(f"❌ Error downloading model: {e}")
#             return None
    
#     print(f"Loading BERTopic model from {MODEL_FILE}...")
#     try:
#         return BERTopic.load(MODEL_FILE)
#     except Exception as e:
#         print(f"❌ Error loading pickle: {e}")
#         return None

# def get_safe_topic_ids(model, nsfw_set):
#     """
#     Returns a list of Topic IDs that do NOT contain any blocklisted words
#     in their top 10 keywords.
#     """
#     safe_ids = []
#     unsafe_ids = []
    
#     all_topics = model.get_topics()
#     print(f"Scanning {len(all_topics)} topics for NSFW content...")
    
#     for topic_id, words_with_scores in all_topics.items():
#         topic_words = {word for word, score in words_with_scores}
#         intersection = topic_words.intersection(nsfw_set)
        
#         if intersection:
#             unsafe_ids.append(topic_id)
#         else:
#             safe_ids.append(topic_id)
            
#     print(f"\nResult: {len(safe_ids)} Safe, {len(unsafe_ids)} Unsafe.")
#     return safe_ids

# def generate_labels():
#     # 1. Load Model
#     topic_model = load_remote_model()
#     if topic_model is None:
#         return

#     # 2. Get Info
#     info = topic_model.get_topic_info()
#     print(f"Found {len(info)} topics.")
#     safe_topics = get_safe_topic_ids(topic_model, nsfw_set=NSFW_KEYWORDS)
    
#     labels_map = {}

#     print("running local generation with Llama 3.1...")
    
#     for index, row in tqdm(info.iterrows(), total=len(info)):
#         topic_id = row['Topic']
        
#         # Skip unsafe topics
#         if topic_id not in safe_topics:
#             labels_map[f"Topic_{topic_id}"] = "NSFW Content" 
#             continue
            
#         # Handle Outliers
#         if topic_id == -1: 
#             labels_map[f"Topic_{topic_id}"] = "Outliers / Noise"
#             continue

#         # 3. Extract Data
#         keywords = row['Representation']
#         docs = row['Representative_Docs']

#         if not isinstance(docs, list) or len(docs) == 0:
#             try:
#                 res = supabase.table("posts") \
#                     .select("content") \
#                     .eq("cluster_id", int(topic_id)) \
#                     .limit(3) \
#                     .execute()
#                 docs = [r['content'] for r in res.data]
#             except Exception:
#                 docs = []

#         if not docs: 
#             docs_text = "(No examples available)"
#         else:
#             docs_text = "\n".join([f"- {str(d)[:200]}..." for d in docs[:3]])

#         # 4. Construct Prompt
#         # Llama 3.1 Instruct works best with a specific chat format.
#         # We make it concise to save context window space.
#         system_msg = "You are a helpful classifier. Create a label (max 5 words) for the topic described by the keywords and posts. Do not use quotes."
#         user_msg = f"""
#         Keywords: {', '.join(keywords[:10])}
#         Posts:
#         {docs_text}
        
#         Label:
#         """
        
#         # 5. Call Local LLM
#         try:
#             response = llm.create_chat_completion(
#                 messages=[
#                     {"role": "system", "content": system_msg},
#                     {"role": "user", "content": user_msg}
#                 ],
#                 temperature=0.3, # Low temperature for consistency
#                 max_tokens=20,   # We only need a short label
#             )
            
#             label = response['choices'][0]['message']['content'].strip().replace('"', '')
#             labels_map[f"Topic_{topic_id}"] = label

#         except Exception as e:
#             print(f"\n ❌ Error on Topic {topic_id}: {e}")
#             # Fallback
#             fallback = ", ".join(keywords[:3]).title()
#             labels_map[f"Topic_{topic_id}"] = fallback

#     # 6. Save locally
#     with open(OUTPUT_JSON, "w") as f:
#         json.dump(labels_map, f, indent=2)

#     # 7. Upload to Supabase
#     print(f"☁️ Uploading {OUTPUT_JSON} to Supabase...")
#     with open(OUTPUT_JSON, "rb") as f:
#         supabase.storage.from_(BUCKET).upload(
#             OUTPUT_JSON, 
#             f, 
#             file_options={"x-upsert": "true"}
#         )
        
#     print(f"Success! Labels saved and uploaded.")

# if __name__ == "__main__":
#     generate_labels()



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