from .features import build_features
from sklearn.linear_model import LogisticRegression


def train_model(game_index_path):
    # Build features from the game index
    features_df = build_features(game_index_path)
    
    # Prepare training data
    features_df = features_df.dropna(subset=['result'])
    X = features_df[['sentiment_diff']]
    y = features_df['result']
    
    # Train a logistic regression model
    model = LogisticRegression()
    model.fit(X, y)
    
    return model