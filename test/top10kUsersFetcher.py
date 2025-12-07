import requests
from bs4 import BeautifulSoup
import pandas as pd
import re
import time

def fetch_page(url):
    """Downloads the HTML content from a URL."""
    try:
        response = requests.get(url)
        response.raise_for_status() # Raise an error for bad responses (404, 500, etc.)
        return response.text
    except requests.RequestException as e:
        print(f"Error fetching the page: {e}")
        return None

def parse_data(html_content):
    """Parses the HTML and extracts user data."""
    if html_content is None:
        return []

    soup = BeautifulSoup(html_content, 'html.parser')
    user_list = []

    # --- THIS IS THE CORRECTED SECTION ---
    
    # 1. Find all 'div' tags with the class 'AccountCard'
    # This is the main container for each user.
    user_cards = soup.find_all('div', class_='AccountCard') 

    for card in user_cards:
        try:
            # 2. Find the handle in the 'div' with class 'text-xs opacity-50'
            handle_tag = card.find('div', class_='text-xs opacity-50')
            handle = handle_tag.text.strip() if handle_tag else None

            # 3. Find the follower count in the 'div' with class 'text-4xl'
            followers_tag = card.find('div', class_='text-4xl __className_a8383b')
            
            followers = 0
            if followers_tag and followers_tag.contents:
                # The text is the first child node, e.g., "852,911"
                # We strip it, remove commas, and convert to an integer
                followers_text = str(followers_tag.contents[0]).strip().replace(',', '')
                if followers_text.isdigit():
                    followers = int(followers_text)

            if handle:
                user_list.append({
                    'handle': handle,
                    'followers': followers
                })
        except Exception as e:
            print(f"Error parsing a card: {e}")
    # --- END OF CORRECTED SECTION ---
            
    return user_list

def main():
    df = pd.DataFrame(columns=['handle', 'followers'])
    for i in range(150):
        url = f"https://most-followed-mastodon-accounts.stefanhayden.com/?page={i+1}"
        print(f"Fetching data from {url}...")
        
        html = fetch_page(url)
        users = parse_data(html)
        
        if users:
            print(f"Successfully scraped {len(users)} users.")
            
            # Convert to a pandas DataFrame for easy viewing
            df2 = pd.DataFrame(users)
            df2 = df2.sort_values(by='followers', ascending=False)
            
            # print("\n--- Top 10 Scraped Users ---")
            # print(df.head(10))
            df = pd.concat([df, df2], ignore_index=True)
        else:
            print("No users were found.")

        time.sleep(2)

    df.to_csv("top10k_mastodon_users.csv", index=False)
    

if __name__ == "__main__":
    # You'll need to install these libraries first:
    # pip install requests beautifulsoup4 pandas
    main()