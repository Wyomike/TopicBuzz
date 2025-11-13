import chromadb
chroma_client = chromadb.Client()

collection = chroma_client.create_collection(name="topicBuzzTest")



collection.add(
    ids=["id1", "id2"],
    documents=[
        "This is a document about pineapple",
        "This is a document about oranges"
    ]
)

results = collection.query(
    query_texts=["This is a query document about hawaii"], # Chroma will embed this for you
    n_results=2 # how many results to return
)

# chroma_client.delete_collection(name="topicBuzzTest")
print(results)