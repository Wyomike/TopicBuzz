import pandas as pd
from mastodon import Mastodon
import json

# --- Configuration ---
# 1. Get your Access Token:
#    - Go to your Mastodon instance (e.g., mastodon.social)
#    - Go to Preferences > Development > New Application
#    - Give it a name (e.g., "My Post Fetcher")
#    - Check only the 'read:statuses' scope
#    - Click "Save" and copy "Your access token"
#
# 2. Set your instance URL and the user you want to track

access_token = json.load(open(r"C:\CS452\TopicBuzz\secrets.json"))["token"]
ACCESS_TOKEN = access_token

INSTANCE_URL = "https://mastodon.social"  # e.g., https://mastodon.social

df = pd.read_csv(r"C:\CS452\TopicBuzz\top10k_mastodon_users.csv")
users = df['handle'].tolist()
USER_TO_FETCH = users[0] # Full handle: @username@instance

# --- Script ---

# 1. Connect to the Mastodon API
try:
    api = Mastodon(
        access_token=ACCESS_TOKEN,
        api_base_url=INSTANCE_URL
    )
    print(f"Successfully connected to {INSTANCE_URL}")
except Exception as e:
    print(f"Error connecting to Mastodon: {e}")
    exit()

# 2. Get the user's Account ID from their handle
try:
    # The API requires a numerical ID, not the username
    account = api.account_lookup(USER_TO_FETCH)
    account_id = account['id']
    print(f"Found account ID for {USER_TO_FETCH}: {account_id}")

except Exception as e:
    print(f"Error finding user {USER_TO_FETCH}: {e}")
    print("Please check that the user handle and instance URL are correct.")
    exit()

# 3. Fetch the user's 10 most recent posts
try:
    # Use the account_statuses() method with the ID and a limit
    posts = api.account_statuses(account_id, limit=10)
    print(f"\n--- 10 Most Recent Posts from {USER_TO_FETCH} ---")

    # 4. Display the posts
    for i, post in enumerate(posts):
        # We use BeautifulSoup to strip any HTML tags from the post content
        from bs4 import BeautifulSoup
        soup = BeautifulSoup(post['content'], 'html.parser')
        
        print(f"\n{i+1}. Post ID: {post['id']} | {post['created_at']}")
        print(f"   Content: {soup.get_text().strip()}")
        print(f"   Link: {post['url']}")

except Exception as e:
    print(f"Error fetching posts: {e}")