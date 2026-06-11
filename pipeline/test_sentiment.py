from sentiment import load_model, score_articles

# Create a sample list of file paths with real JSON files for testing
file_paths = ["/Users/tjwill/TJ's Stuff/Portfolio/nba_predictor/data/raw/espn/espn_NYK_SAS_20260609_1946.json", "/Users/tjwill/TJ's Stuff/Portfolio/nba_predictor/data/raw/youtube/youtube_NYK_SAS_G4_20260609_1845_TEST_comments.json"]

model = load_model()
team_scores = score_articles(file_paths, model)

# Print the team scores for verification
print(team_scores)