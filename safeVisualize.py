from bertopic import BERTopic
import os

# 1. Configuration
MODEL_PATH = "my_mastodon_model_reduced"
OUTPUT_HTML = "safe_topics_map.html"

# Define your "Blocklist"
# Since BERTopic keywords are lowercase/cleaned, keep these lowercase.
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
            print(f"  [BLOCKED] Topic {topic_id}: Found {intersection}")
            unsafe_ids.append(topic_id)
        else:
            safe_ids.append(topic_id)
            
    print(f"\nResult: {len(safe_ids)} Safe, {len(unsafe_ids)} Unsafe.")
    return safe_ids

# 2. Load the model
if not os.path.exists(MODEL_PATH):
    print(f"Error: Model not found at {MODEL_PATH}")
    exit()

print("Loading model...")
topic_model = BERTopic.load(MODEL_PATH)

# 3. Filter
safe_topics = get_safe_topic_ids(topic_model, NSFW_KEYWORDS)

# 4. Visualize ONLY the safe topics
print(f"Generating visualization for {len(safe_topics)} topics...")

# The visualize_topics function accepts a 'topics' list. 
# It will only draw the IDs we pass it.
try:
    fig = topic_model.visualize_topics(topics=safe_topics)
    
    # 5. Save
    fig.write_html(OUTPUT_HTML)
    print(f"Success! Clean map saved to '{OUTPUT_HTML}'")
    
except Exception as e:
    print(f"Visualization failed (maybe 0 topics left?): {e}")