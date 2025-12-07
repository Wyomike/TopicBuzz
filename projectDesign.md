# TOPIC BUZZ

## General overview

The goal of topic buzz is to analyze trends in a way that we can see where ideas are coming from and who cares about them. Because I usually don't. 

This can be helpful if you're out of the loop on something and want to know where it came from. While I'm not quite certain how this will all work quite yet, an idea is that we try to identify topics and clusters with embeddings. Then, we try to see who else is talking about these topics so that we can see where the ideas came from. We will attach dates to people who talk about things to analyze origins. A possible idea to prevent stale ideas is to archive topics that haven't been updated in the past few days. We will try to display current topics in a visually useful graph. 

I plan to source the posts from X, though may switch depending on how hard or easy it is to get posts.

The hope is for the graph to look something like this but actually completely different since each topic node will be its own thing with individuals which talked about it connected to it, think of a center hub node with many offshoots. The hope is to use dimension reductions and a color gradient to plot these clusters on a 2d graph such that more related topics will be closer to each other and reflect that in their color. I am still considering switching a distance metric for the final visualization from space distance to person overlap so that it's easier to see who falls in to similar circles.

<img width="714" height="300" alt="image" src="https://github.com/user-attachments/assets/e81d8dde-c776-4f78-b180-4c2de3498a4f" />


ERD:
<img width="1161" height="692" alt="image" src="https://github.com/user-attachments/assets/26e2bc12-0749-4896-b2a3-e25c987d7646" />


Interaction drawing:
<img width="907" height="552" alt="image" src="https://github.com/user-attachments/assets/eae91279-fe67-4fc0-95b5-9b88bc7229f0" />

Planning:
| Date range  | Planned point |
| :---- | -------: |
| By nov 8 | Pin down a database service |
| by 15   | Figure out post intake and embedding |
| by 22 | Determine best clustering method with BERTopic |
| by Dec 6 | Make visually appealing visualization and investigate possibility of website version |
| Extra time | Investigate news titles visualization |
