import pandas as pd
from transformers import pipeline
import os
import json

# Load the sentiment analysis pipeline
def load_model():
    model = pipeline(task="sentiment-analysis", model="cardiffnlp/twitter-roberta-base-sentiment-latest", top_k=None)
    return model

# Perform sentiment analysis on the input text
def analyze_text(text, model):
    text = text[:512]  # Truncate text to 512 characters
    result = model(text)
    result = result[0]  # Get the first (and only) result from the list
    clean_dict = {}
    for item in result:
        label = item['label']
        score = item['score']
        clean_dict[label] = score
    return clean_dict

def score_articles(file_paths, model):
    results = []
    for file_path in file_paths:
        df = pd.read_json(file_path)
        is_youtube = "youtube" in file_path
        for index, row in df.iterrows():
            if not is_youtube:
                text = row['full_text']
                teams = row["team_relevance"].split(",")
            else:
                text = row["text"]
                teams = [row["team1"], row["team2"]]
            sentiment_scores = analyze_text(text, model)
            results.append({
                "text": text,
                "teams": teams,
                "sentiment_scores": sentiment_scores
            })
    team_scores = {}
    for result in results:
        teams = result["teams"]
        sentiment_scores = result["sentiment_scores"]
        for team in teams:
            if team not in team_scores:
                team_scores[team] = {"positive": 0, "neutral": 0, "negative": 0, "count": 0}
            team_scores[team]["positive"] += sentiment_scores.get("positive", 0)
            team_scores[team]["neutral"] += sentiment_scores.get("neutral", 0)
            team_scores[team]["negative"] += sentiment_scores.get("negative", 0)
            team_scores[team]["count"] += 1
    for team, scores in team_scores.items():
        count = scores["count"]
        if count > 0:
            scores["positive"] /= count
            scores["neutral"] /= count
            scores["negative"] /= count
        scores["sentiment_score"] = scores["positive"] - scores["negative"]
    return team_scores