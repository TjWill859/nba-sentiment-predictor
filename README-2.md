# NBA Finals Sentiment Classifier

Predicts NBA Finals game outcomes using pre-game sentiment from ESPN articles and YouTube comments.

## Setup

```bash
python -m venv venv
source venv/bin/activate      # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

## Project Structure

```
nba_sentiment/
├── scrapers/
│   ├── espn_scraper.py       # ESPN article scraper  ✅
│   └── youtube_scraper.py    # YouTube comment scraper (add after API key)
├── data/
│   ├── raw/                  # Raw scraped CSVs/JSONs
│   └── processed/            # Sentiment-scored feature files
├── models/                   # Trained classifier artifacts
├── notebooks/                # EDA and analysis
└── requirements.txt
```

## Usage

### Scrape ESPN articles (pre-game, 48h window)
```bash
cd scrapers
python espn_scraper.py                          # defaults: NYK vs SAS, 48h
python espn_scraper.py --team1 NYK --team2 SAS --hours 48
python espn_scraper.py --hours 24 --max 20      # faster, last 24h only
```

Output saved to `data/raw/espn_NYK_SAS_<timestamp>.csv`

### Next steps (coming soon)
- `youtube_scraper.py` — pre-game YouTube comment collection
- `sentiment_pipeline.py` — run HuggingFace RoBERTa over collected text
- `feature_builder.py` — aggregate sentiment scores + injury flags per team
- `train_classifier.py` — train logistic regression / XGBoost on conf finals data

## Data Sources
| Source | Type | Status |
|---|---|---|
| ESPN articles | Media sentiment | ✅ Ready |
| YouTube comments | Fan sentiment | ⏳ Needs API key |
| NBA injury reports | Structured features | 🔜 Next |
| Ball Don't Lie API | Ground truth labels | 🔜 Next |

## Live Evaluation — NBA Finals 2026
| Game | Date | Prediction | Actual |
|---|---|---|---|
| Game 4 | Jun 10 | TBD | TBD |
| Game 5 | Jun 13 | TBD | TBD |
| Game 6 | Jun 16 | TBD | TBD |
| Game 7 | Jun 19 | TBD | TBD |
