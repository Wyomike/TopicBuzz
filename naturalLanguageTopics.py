import google.genai as genai
from bertopic import BERTopic
import json
import os
import time
from tqdm import tqdm

NSFW_KEYWORDS = {
    "nsfw", "porn", "nude", "naked", "sex", "18+", "xxx", 
    "cum", "dick", "pussy", "hentai", "erotic", "onlyfans",
    "boobs", "tits", "cock", "slut", "whore", "bitch", "incest",
    "lewd", "horny", "sensual", "fetish", "bondage"
}

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
        # Topic -1 is outliers. We usually keep it, but check its content too.
        
        # Extract just the words from the tuples
        topic_words = {word for word, score in words_with_scores}
        
        # Check for intersection
        # If the intersection is NOT empty, it contains a bad word
        intersection = topic_words.intersection(nsfw_set)
        
        if intersection:
            print(f"  [BLOCKED] Topic {topic_id}")
            unsafe_ids.append(topic_id)
        else:
            safe_ids.append(topic_id)
            
    print(f"\nResult: {len(safe_ids)} Safe, {len(unsafe_ids)} Unsafe.")
    return safe_ids

# --- CONFIGURATION ---
MODEL_PATH = "my_mastodon_model_reduced"
OUTPUT_JSON = "topic_labels.json"
API_KEY = json.load(open("config.json"))["googleKey"] # Replace or set env var

# --- SETUP ---
client = genai.Client(api_key=API_KEY)
# model = client.models.get() # Fast and cheap

def generate_labels():
    if not os.path.exists(MODEL_PATH):
        print("Model not found!")
        return

    print("Loading BERTopic model...")
    topic_model = BERTopic.load(MODEL_PATH)
    
    # Get the master table of topic info
    info = topic_model.get_topic_info()
    print(f"Found {len(info)} topics.")
    safe_topics = get_safe_topic_ids(topic_model, nsfw_set=NSFW_KEYWORDS)
    
    # Dictionary to map "Topic_5" -> "Nature Photography"
    labels_map = {}

    print("Asking Gemini to label topics...")
    
    for index, row in tqdm(info.iterrows(), total=len(info)):
        if row['Topic'] not in safe_topics:
            labels_map[f"Topic_{row['Topic']}"] = "NSFW"  # TODO - check if this is actually the bag of words
            continue
        topic_id = row['Topic']
        
        # Handle Outliers
        if topic_id == 0:
            labels_map[f"Topic_{topic_id}"] = "Outliers / Noise"
            continue

        # 1. Get Bag of Words
        # row['Representation'] is a list of keywords like ['cat', 'meow', 'feline']
        keywords = row['Representation']
        
        # 2. Get Representative Docs
        # row['Representative_Docs'] is a list of actual posts
        docs = row['Representative_Docs']
        
        # 3. Construct Prompt
        # We take top 10 keywords and top 3 docs to save tokens
        prompt = f"""
        I have a cluster of social media posts from Mastodon.
        
        Keywords: {', '.join(keywords[:10])}
        
        Representative Posts:
        {chr(10).join([f"- {d[:300]}..." for d in docs[:3]])}
        
        Based on this, provide a short, specific, natural language label (max 5 words) for this topic.
        Do not use quotes. Just the label.
        """
        
        try:
            # 4. Call Gemini
            response = client.models.generate_content(
                model='gemini-2.5-flash',
                contents=prompt
            )
            label = response.text.strip()
            
            # 5. Store result
            labels_map[f"Topic_{topic_id}"] = label
            
            # Sleep briefly to respect rate limits if needed
            time.sleep(1.0)
            
        except Exception as e:
            print(f"Error labeling Topic {topic_id}: {e}")
            labels_map[f"Topic_{topic_id}"] = f"Topic {topic_id}"

    # Save to JSON
    with open(OUTPUT_JSON, "w") as f:
        json.dump(labels_map, f, indent=2)
        
    print(f"Success! Labels saved to {OUTPUT_JSON}")

if __name__ == "__main__":
    generate_labels()