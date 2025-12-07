import chromadb
from bertopic import BERTopic
from sklearn.cluster import MiniBatchKMeans
from sklearn.decomposition import IncrementalPCA
from bertopic.vectorizers import OnlineCountVectorizer
import fasttext
import numpy as np

# --- 1. Connect to ChromaDB (Standard Setup) ---
path = "/home/wyomike/topicBuzz/my_mastodon_db"
client = chromadb.PersistentClient(path=path)
collection = client.get_collection("mastodon_posts")

lang_model = fasttext.load_model("lid.176.ftz")

def is_english(text):
    # Fasttext returns a label like ('__label__en',)
    predictions = lang_model.predict(text.replace("\n", " "))
    return predictions[0][0] == "__label__en"

# --- 2. Get the Total Count (Without loading data) ---
total_docs = collection.count()
print(f"Total documents in DB: {total_docs}")

# --- 3. Setup the Online Models ---
umap_model = IncrementalPCA(n_components=5)
cluster_model = MiniBatchKMeans(n_clusters=200, random_state=42)
vectorizer_model = OnlineCountVectorizer(stop_words="english", min_df=10)

topic_model = BERTopic(
    embedding_model=None, # We will provide embeddings manually from Chroma
    umap_model=umap_model,
    hdbscan_model=cluster_model,
    vectorizer_model=vectorizer_model
)

# --- 4. The Loop: Fetching Batches from Disk ---
batch_size = 5000  # 5k is safer than 10k for OOM prevention
print(f"Starting online training on {total_docs} documents...")

for offset in range(0, total_docs, batch_size):
    # A. Fetch one "page" of data from ChromaDB
    # We ask for both 'documents' (text) and 'embeddings' (vectors)
    batch_data = collection.get(
        limit=batch_size, 
        offset=offset, 
        include=["documents", "embeddings"]
    )
    
    batch_docs = batch_data['documents']
    batch_embs = batch_data['embeddings']
    
    # Safety check: ensure we actually got data
    if not batch_docs:
        break

    # B. Teach the model this specific batch
    filtered_pairs = [
        (doc, emb) for doc, emb in zip(batch_docs, batch_embs) 
        if is_english(doc)
    ]
    
    if not filtered_pairs: 
        continue # Skip if batch has no English
        
    # Unzip back into separate lists
    clean_docs, clean_embs = zip(*filtered_pairs)

    topic_model.partial_fit(clean_docs, np.array(clean_embs))
    
    print(f"Processed batch {offset} to {offset + len(batch_docs)}")

# --- 5. Clean up and Save ---
# print("Reducing topics...")
# topic_model.reduce_topics(batch_docs, nr_topics="auto") 
# Note: reduce_topics requires a representative list of docs. 
# We reuse the last 'batch_docs' here as a proxy, which is standard for online methods.

topic_model.save("my_online_mastodon_model", serialization="pickle")
print("Model saved successfully!")