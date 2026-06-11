import json
import pandas as pd
from .sentiment import score_articles, load_model

def build_features(game_index_path):
    with open(game_index_path, 'r') as f:
        game_index = json.load(f)
    
    features = []
    model = load_model()
    for game in game_index:
        game_id = game['game_id']
        home_team = game['home_team']
        away_team = game['away_team']
        data_files = game['data_files']
        result = game['result']
        
        team_scores = score_articles(data_files, model)
        
        features.append({
            'game_id': game_id,
            'home_team': home_team,
            'away_team': away_team,
            'home_sentiment_score': team_scores.get(home_team, {}).get('sentiment_score', 0),
            'away_sentiment_score': team_scores.get(away_team, {}).get('sentiment_score', 0),
            'sentiment_diff': team_scores.get(home_team, {}).get('sentiment_score', 0) - team_scores.get(away_team, {}).get('sentiment_score', 0),
            'result': result
        })
    
    return pd.DataFrame(features)

