import chromadb
import pprint

DB_PATH = "./my_mastodon_db"
COLLECTION_NAME = "mastodon_posts" # <--- Change this if needed

client = chromadb.PersistentClient(path=DB_PATH)

print(f"\n--- 📈 All Items in Collection: '{COLLECTION_NAME}' ---")

try:
    collection = client.get_collection(name=COLLECTION_NAME)
    
    # .get() with no arguments fetches everything
    all_items = collection.get()
    
    print(f"Found {len(all_items['ids'])} items.")
    
    # Use pprint to make the output readable
    # pprint.pprint(all_items)

except Exception as e:
    print(f"Could not get collection '{COLLECTION_NAME}'. Error: {e}")
    print("Are you sure that collection exists? Try listing collections first.")

# try:
#     #access at a specific username
#     username = "example_user"  # <--- Change this to a valid username
#     user_items = collection.get(where={"username": username})
# except Exception as e:
#     print(f"Could not get items for username '{username}'. Error: {e}")
#     print("Are you sure that username exists in the collection?")