import chromadb

# --- Configuration ---
# 1. PLEASE UPDATE these variables
ORIGINAL_COLLECTION_NAME = "mastodon_posts"  # The name of your existing collection
TEST_COLLECTION_NAME = "my_test_collection"      # The name for your new test collection

try:
    # --- 2. CONNECT TO CHROMA ---
    # Update this line to match how you connect to ChromaDB.
    # It could be:
    # client = chromadb.Client()                             # For an in-memory client
    # client = chromadb.PersistentClient(path="/path/to/db")  # For a persistent client
    # client = chromadb.HttpClient(host='localhost', port=8000) # For a client/server
    
    # Using PersistentClient as a common example:
    chroma_db_path = "/home/wyomike/topicBuzz/my_mastodon_db"
    
    client = chromadb.PersistentClient(path=chroma_db_path)
    print("Successfully connected to ChromaDB.")

    # 3. Get the original collection
    print(f"Accessing original collection: '{ORIGINAL_COLLECTION_NAME}'...")
    original_collection = client.get_collection(name=ORIGINAL_COLLECTION_NAME)

    item_limit = 500
    # 4. Get 100 items from it
    print(f"Fetching {item_limit} items from '{ORIGINAL_COLLECTION_NAME}'...")
    data = original_collection.get(
        limit=item_limit,
        include=["embeddings", "metadatas", "documents"]  # Get all data to clone
    )
    
    item_count = len(data.get('ids', []))
    if item_count == 0:
        print("Original collection is empty or data could not be fetched. Stopping.")
        exit()
        
    print(f"Successfully fetched {item_count} items.")

    # 5. Create the new test collection
    # We'll delete it first to ensure this script can be run multiple times
    try:
        client.delete_collection(name=TEST_COLLECTION_NAME)
        print(f"Removed old test collection: '{TEST_COLLECTION_NAME}'")
    except Exception as e:
        print(f"Old test collection not found (this is OK): {e}")

    print(f"Creating new test collection: '{TEST_COLLECTION_NAME}'...")
    test_collection = client.create_collection(name=TEST_COLLECTION_NAME)

    # 6. Add the 100 items to the new collection
    # The data format from .get() maps perfectly to .add()
    print("Adding fetched items to the new collection...")
    test_collection.add(
        embeddings=data.get('embeddings'),
        documents=data.get('documents'),
        metadatas=data.get('metadatas'),
        ids=data['ids']
    )

    # 7. Verify the count
    new_count = test_collection.count()
    print(f"\n--- SUCCESS ---")
    print(f"Created new collection '{TEST_COLLECTION_NAME}' with {new_count} items.")

except Exception as e:
    print(f"\nAn error occurred: {e}")
    print("Please check your client connection settings and collection names.")