from bertopic import BERTopic

# 1. Load the model
print("Loading model...")
topic_model = BERTopic.load("my_online_mastodon_model")

# 2. See the Topic Overview
# This dataframe shows the Topic ID, Count, and Name (keywords)
freq = topic_model.get_topic_info()

print(f"Number of topics found: {len(freq)}")
print("\nTop 10 Topics:")
print(freq.head(10))

# 3. Generate a Bar Chart (The safest visualization)
print("\nGenerating bar chart...")
fig = topic_model.visualize_barchart(top_n_topics=16)
fig.write_html("mastodon_topics_barchart.html")
print("Saved to 'mastodon_topics_barchart.html'. Open this in your browser!")

# 4. Generate the Intertopic Distance Map
# (This might take 10-20 seconds to compute the first time)
print("Generating map...")
try:
    fig_map = topic_model.visualize_topics()
    fig_map.write_html("mastodon_topics_map.html")
    print("Saved to 'mastodon_topics_map.html'.")
except Exception as e:
    print(f"Could not generate map (likely too few topics): {e}")