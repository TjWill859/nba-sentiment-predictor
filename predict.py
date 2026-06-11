from pipeline.features import build_features
from pipeline.train import train_model

features_df = build_features("data/game_index.json")
model = train_model("data/game_index.json")

unlabeled = features_df[features_df['result'].isna()]
home_team = unlabeled.iloc[0]['home_team']
away_team = unlabeled.iloc[0]['away_team']
prediction = model.predict(unlabeled[['sentiment_diff']])
if prediction[0] == 1:
    print(f"Predicted winner: {home_team}")
else:
    print(f"Predicted winner: {away_team}")

# if unlabeled.iloc[0]['sentiment_diff'] > 0:
#     print(f"Predicted winner: {home_team}")
# else:
#     print(f"Predicted winner: {away_team}")
