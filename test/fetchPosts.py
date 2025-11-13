import chromadb
import re
import time
from mastodon import Mastodon
from datetime import datetime
from pathlib import Path
import json

# --- 1. CONFIGURE YOUR SETTINGS ---
# !! Fill these in !!
MASTODON_SERVER_URL = r"https://mastodon.social"  # e.g., "https://mastodon.social"
MASTODON_ACCESS_TOKEN = json.load(open(r"D:\cs452\TopicBuzz\secrets.json"))["token"]  # The token you just generated
USER_LIST_FILE = "usersAll.txt"
DB_PATH = "./my_mastodon_db"
COLLECTION_NAME = "mastodon_posts"
POSTS_TO_FETCH = 100
# -----------------------------------

# Simple regex to strip HTML tags from post content
def strip_html(text):
    return re.sub(r'<[^<]+?>', '', text)

# Helper function to sleep and respect rate limits
def polite_request(api_call, *args, **kwargs):
    """
    Makes an API call and then waits 1 second.
    This respects the default 300 requests / 5 min (1 req/sec) limit.
    """
    response = api_call(*args, **kwargs)
    time.sleep(1)
    return response

def main():
    print("--- Mastodon Post Fetcher ---")

    # --- 2. Initialize Clients ---
    try:
        # Initialize Mastodon client
        mastodon = Mastodon(
            access_token=MASTODON_ACCESS_TOKEN,
            api_base_url=MASTODON_SERVER_URL
        )
        print(f"Mastodon client connected to {MASTODON_SERVER_URL}")

        # Initialize ChromaDB client
        client = chromadb.PersistentClient(path=DB_PATH)
        collection = client.get_or_create_collection(name=COLLECTION_NAME)
        print(f"ChromaDB client connected to {DB_PATH}")

    except Exception as e:
        print(f"Error during initialization: {e}")
        return

    # --- 3. Read User List ---
    user_file = Path(USER_LIST_FILE)
    if not user_file.exists():
        print(f"Error: User file not found at {USER_LIST_FILE}")
        return

    with open(user_file, 'r') as f:
        usernames = [line.strip() for line in f if line.strip()]
    
    print(f"Found {len(usernames)} users to track.")

    # --- 4. Main Fetch Loop ---
    for username in usernames:
        print(f"\nFetching posts for user: {username}")
        try:
            # First, find the user's account ID
            account = polite_request(mastodon.account_lookup, username)
            if not account:
                print(f"Could not find user {username}. Skipping.")
                continue
            
            user_id = account['id']

            # Mastodon's API is paginated, max 40 posts per request
            # We need to make multiple requests to get 100
            
            # Fetch Page 1 (posts 1-40)
            page1 = polite_request(mastodon.account_statuses, id=user_id, limit=40)
            
            # Fetch Page 2 (posts 41-80)
            page2 = polite_request(mastodon.fetch_next, page1) if page1 else []
            
            # Fetch Page 3 (posts 81-120)
            page3 = polite_request(mastodon.fetch_next, page2) if page2 else []

            # Combine pages and get the most recent 100
            # (or fewer if the user doesn't have 100)
            all_posts = (page1 or []) + (page2 or []) + (page3 or [])
            recent_posts = all_posts[:POSTS_TO_FETCH]

            if not recent_posts:
                print(f"No posts found for {username}. Skipping.")
                continue

            # --- 5. Prepare Data for ChromaDB ---
            ids_batch = []
            docs_batch = []
            meta_batch = []

            for post in recent_posts:
                
                doc_content = ""
                doc_id = str(post['id']) # Use the status ID (reblog or original) as the unique ID
                doc_meta = {}

                if post['reblog']:
                    # This is a REBLOG
                    original_post = post['reblog']
                    
                    # Use the ORIGINAL post's content for the vector
                    doc_content = strip_html(original_post['content'])
                    
                    doc_meta = {
                        "type": "reblog",
                        "reblogger_user_id": str(post['account']['id']), # The user who reblogged
                        "reblog_timestamp": int(post['created_at'].timestamp()), # Time of the reblog
                        "original_post_id": str(original_post['id']),
                        "original_author_id": str(original_post['account']['id']),
                        "language": str(original_post.get('language'))
                    }
                else:
                    # This is an ORIGINAL post
                    doc_content = strip_html(post['content'])
                    
                    doc_meta = {
                        "type": "original",
                        "author_user_id": str(post['account']['id']), # The user who posted
                        "post_timestamp": int(post['created_at'].timestamp()), # Time of the post
                        "language": str(post.get('language'))
                    }

                # Don't add empty posts (e.g., if content stripping failed)
                if doc_content:
                    ids_batch.append(doc_id)
                    docs_batch.append(doc_content)
                    meta_batch.append(doc_meta)

            # --- 6. Store in ChromaDB ---
            if ids_batch:
                collection.upsert(
                    ids=ids_batch,
                    documents=docs_batch,
                    metadatas=meta_batch
                )
                print(f"Successfully added/updated {len(ids_batch)} posts for {username}.")
            else:
                print(f"No new original posts found for {username}.")

        except Exception as e:
            print(f"An error occurred while processing {username}: {e}")
            # Continue to the next user even if one fails
            pass

    print("\n--- All users processed. ---")

if __name__ == "__main__":
    main()