import chromadb

client = chromadb.PersistentClient(path="./my_mastodon_db")
collection = client.get_collection(name="mastodon_posts")

# This might take a moment.
print("Fetching all data from ChromaDB...")
all_data = collection.get(
    # Ask for 750k (or more) to get everything
    limit=750000, 
    include=["documents", "embeddings"]
)

documents = all_data['documents']
embeddings = all_data['embeddings']



from bertopic import BERTopic

print("Data fetched. Starting topic modeling...")

# We tell BERTopic to use our pre-made embeddings
topic_model = BERTopic(embedding_model="disable") 

# This one-line command does it all:
# 1. Runs UMAP to reduce dimensions
# 2. Runs HDBSCAN to find clusters
# 3. Runs a c-TF-IDF to find topic words
topics, probs = topic_model.fit_transform(documents, embeddings)

print("Topic modeling complete!")

# 4. See your topics!
# This shows the most common topics
print(topic_model.get_topic_info())

# This shows the keywords for a specific topic
print(topic_model.get_topic(0))

topic_model.visualize_topics()



