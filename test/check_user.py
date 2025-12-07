import chromadb
from mastodon import Mastodon
from pathlib import Path
import json

# --- Configuration (Copied from your fetch script) ---
# NOTE: Replace with your actual ChromaDB path and credentials
MASTODON_SERVER_URL = r"https://mastodon.social"  
MASTODON_ACCESS_TOKEN = json.load(open(r"D:\cs452\TopicBuzz\secrets.json"))["token"] 
DB_PATH = r"D:\cs452\TopicBuzz\test\my_mastodon_db" # Adjust if needed (e.g., /mnt/d/path/to/db)
COLLECTION_NAME = "mastodon_posts"
# --------------------------------------------------


def check_user_in_db(username_handle: str):
    """
    Fetches the user ID from Mastodon and checks if any posts by that ID
    exist in the ChromaDB collection's metadata.
    """
    print(f"\n--- Checking for user: {username_handle} ---")
    try:
        # 1. Initialize Clients
        mastodon = Mastodon(
            access_token=MASTODON_ACCESS_TOKEN,
            api_base_url=MASTODON_SERVER_URL
        )
        client = chromadb.PersistentClient(path=DB_PATH)
        collection = client.get_collection(name=COLLECTION_NAME)

        # 2. Get the numerical Account ID from the user handle
        # This is the crucial first step.
        account = mastodon.account_lookup(username_handle)
        if not account:
            print(f"ERROR: Mastodon API could not find account for {username_handle}.")
            return False

        author_id = str(account['id'])
        print(f"Resolved to numerical ID: {author_id}")

        # 3. Query ChromaDB by the ID
        # We query the metadata field 'author_user_id' (which is how your fetcher stores it)
        # FIX: Changed query_texts to include a non-empty string to bypass Chroma's internal validation.
        results = collection.query(
            query_texts=["placeholder text"], # <-- FIX: Use non-empty list with placeholder
            where={
                "$or": [
                    # Check for original posts
                    {"author_user_id": author_id},
                    # Check for reblogs (if the reblogger is the target user)
                    {"reblogger_user_id": author_id}
                ]
            },
            # We only need the count, so limit is 1
            n_results=1,
            # include=[] is still correct as we only want the presence/absence check
            include=[] 
        )

        # 4. Check results
        if len(results['ids']) > 0:
            print(f"\nSUCCESS: Posts found for {username_handle} (ID {author_id}).")
            return True
        else:
            print(f"\nNOT FOUND: No posts found for {username_handle} in the database.")
            return False

    except Exception as e:
        print(f"\nAn unexpected error occurred: {e}")
        return False

if __name__ == "__main__":
    # Example 1: A user who should be in the database (Mastodon's main ID is 13179)
    check_user_in_db("@Amane_Shion@misskey.gg")
    
    # Example 2: A likely non-existent user
    check_user_in_db("@ShmooCon@infosec.exchange")