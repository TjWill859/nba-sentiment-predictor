from pipeline.features import build_features
from pipeline.train import train_model

features_df = build_features("data/game_index.json")
model = train_model("data/game_index.json")

unlabeled = features_df[features_df['result'].isna()]
row = unlabeled.iloc[0]
home_team = row['home_team']
away_team = row['away_team']
home_sent = row['home_sentiment_score']
away_sent = row['away_sentiment_score']
sent_diff = row['sentiment_diff']
prediction = model.predict(unlabeled[['sentiment_diff']])
predicted_winner = home_team if prediction[0] == 1 else away_team

labeled = features_df.dropna(subset=['result'])
accuracy = model.score(labeled[['sentiment_diff']], labeled['result'])

print(f"\n{'═'*45}")
print(f"  NBA PREDICTION — {row['game_id']}")
print(f"{'═'*45}")
print(f"  {home_team} (home)  sentiment: {home_sent:+.4f}")
print(f"  {away_team} (away)  sentiment: {away_sent:+.4f}")
print(f"  Sentiment diff:       {sent_diff:+.4f}")
print(f"  Model accuracy:       {accuracy:.1%}")
print(f"{'─'*45}")
print(f"  Predicted winner:     {predicted_winner}")
print(f"{'═'*45}\n")