import chromadb

client = chromadb.PersistentClient(path="/home/wyomike/topicBuzz/my_mastodon_db")
name = "mastodon_posts"
# name = "my_test_collection"
collection = client.get_collection(name=name)

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
from sklearn.feature_extraction.text import CountVectorizer

print("Data fetched. Starting topic modeling...")

vectorizer_model = CountVectorizer(stop_words="english")

# We tell BERTopic to use our pre-made embeddings
from umap import UMAP
umap_model = UMAP(n_neighbors=15, n_components=5, min_dist=0.0, metric='cosine', low_memory=True)
topic_model = BERTopic(embedding_model=None, vectorizer_model=vectorizer_model, umap_model=umap_model) 

raw_documents = all_data['documents']

# 2. Clean HTML entities
print("Cleaning HTML entities...")
clean_documents = [html.unescape(doc) for doc in raw_documents]

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
print("\nKeywords for Topic 0:")
print(topic_model.get_topic(0))

fig = topic_model.visualize_topics()
fig.write_html("my_topics_visualization.html")
print("Visualization saved to my_topics_visualization.html")
# topic_model.visualize_topics()

# TODO - will use this to save model proper eventually
topic_model.save("my_mastodon_model", serialization="pickle")
print("Model saved successfully!")

df_results = pd.DataFrame({
    "Document": documents,
    "Topic": topics,
    "Probability": probs 
})

# Save to CSV
df_results.to_csv("mastodon_topic_assignments.csv", index=False)
print("Topic assignments saved to CSV.")



# # 1. Load the model TODO - get in separate file
# # valid for pickle serialization
# loaded_model = BERTopic.load("my_mastodon_model") 

# # 2. Inspect the topics immediately
# freq = loaded_model.get_topic_info()
# print(freq.head())

# # 3. If you want to visualize again later
# fig = loaded_model.visualize_topics()
# fig.write_html("new_visualization.html")
