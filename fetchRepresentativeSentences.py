from bertopic import BERTopic
import pandas as pd

# 1. Load your reduced model
topic_model = BERTopic.load("my_mastodon_model_reduced")

# 2. Get the info table
info_df = topic_model.get_topic_info()

# 3. Save it to CSV so you can read it easily in Excel/Sheets
# This CSV will have columns: Topic, Count, Name, Representation, Representative_Docs
info_df.to_csv("topic_representatives.csv", index=False)
print("Saved representative docs to 'topic_representatives.csv'")

# 4. Preview in terminal (Truncated)
print(info_df[['Topic', 'Name', 'Representative_Docs']].head())