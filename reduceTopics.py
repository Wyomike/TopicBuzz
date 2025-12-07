import chromadb
from bertopic import BERTopic
import random
import math
import numpy as np # Needed for array handling
import fasttext

lang_model = fasttext.load_model("lid.176.ftz")

def is_english(text):
    # Fasttext returns a label like ('__label__en',)
    predictions = lang_model.predict(text.replace("\n", " "))
    return predictions[0][0] == "__label__en"

# 1. Connect to DB
path = "/home/wyomike/topicBuzz/my_mastodon_db"
client = chromadb.PersistentClient(path=path)
collection = client.get_collection("mastodon_posts")

# 2. Get ALL IDs
print("Fetching all IDs from database...")
all_data = collection.get(include=[]) 
all_ids = all_data['ids']
print(f"Found {len(all_ids)} total IDs.")

# 3. Pick the Random Sample
SAMPLE_SIZE = 50000
if len(all_ids) < SAMPLE_SIZE:
    sampled_ids = all_ids
else:
    sampled_ids = random.sample(all_ids, SAMPLE_SIZE)

print(f"Randomly selected {len(sampled_ids)} IDs.")

# 4. Fetch Documents AND Embeddings (Batched)
print("Fetching text and embeddings...")

sample_docs = []
sample_embs = [] # Store embeddings too
SQL_BATCH_SIZE = 2000

total_chunks = math.ceil(len(sampled_ids) / SQL_BATCH_SIZE)

for i in range(total_chunks):
    start_idx = i * SQL_BATCH_SIZE
    end_idx = start_idx + SQL_BATCH_SIZE
    batch_ids = sampled_ids[start_idx:end_idx]
    
    # CRITICAL CHANGE: Added "embeddings" to include list
    batch_data = collection.get(
        ids=batch_ids,
        include=["documents", "embeddings"] 
    )
    filtered_pairs = [
        (doc, emb) for doc, emb in zip(batch_data['documents'], batch_data['embeddings']) 
        if is_english(doc)
    ]
    
    sample_docs.extend([pair[0] for pair in filtered_pairs])
    sample_embs.extend([pair[1] for pair in filtered_pairs])
    
    if i % 5 == 0:
        print(f"  Fetched batch {i+1}/{total_chunks}")

print(f"Successfully loaded {len(sample_docs)} documents and embeddings.")

# 5. Load Model
print("Loading model...")
topic_model = BERTopic.load("/home/wyomike/topicBuzz/my_online_mastodon_model")

# --- THE FIX STARTS HERE ---
print("Aligning model state with the new sample...")

# A. Convert list to numpy array for BERTopic
sample_embs_np = np.array(sample_embs)

# B. Calculate the current topics for this sample
# We pass embeddings so it doesn't try to download a model to calculate them
current_topics, _ = topic_model.transform(sample_docs, sample_embs_np)

# C. Force overwrite the internal state
# This makes len(topic_model.topics_) == 50,000, matching sample_docs
topic_model.topics_ = current_topics

print("State aligned. reducing topics...")

# 6. Reduce Topics
# Now the lengths match, so this will succeed
new_topic_model = topic_model.reduce_topics(sample_docs, nr_topics="auto")

# 7. Save & Visualize
print("Saving reduced model...")
new_topic_model.save("my_mastodon_model_reduced", serialization="pickle")

# fig = new_topic_model.visualize_topics()
# fig.write_html("reduced_map_random.html")
# print("Done! Open 'reduced_map_random.html'.")





topic_model = BERTopic.load("my_mastodon_model_reduced")

# List of NSFW topics identified manually TODO - loop through bag of words and throw out those which have nsfw terms
nsfw_topics = [7, 8, 19, 20, 55, 58, 71]

# Get the dataframe of document info
df = topic_model.get_document_info(docs)

# Filter out the NSFW rows
clean_df = df[~df['Topic'].isin(nsfw_topics)]

# If you want to visualize ONLY safe topics, you can filter the visual
# (Note: visualize_topics() takes a 'topics' argument to inclusion list)
safe_topics = [t for t in topic_model.get_topics().keys() if t not in nsfw_topics]
fig = topic_model.visualize_topics(topics=safe_topics)
fig.write_html("safe_topics_map.html")