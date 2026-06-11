# NBA Finals Sentiment-Driven Game Outcome Predictor

A machine learning pipeline that scrapes pre-game YouTube comments and ESPN articles, runs NLP sentiment analysis, and predicts NBA Finals game outcomes. Built and evaluated on **live 2026 playoff data** (New York Knicks vs. San Antonio Spurs).

## How It Works

1. **Scrape** — pulls pre-game YouTube comments (via YouTube Data API) and ESPN articles in the 24–48 hours before tip-off
2. **Sentiment** — scores each piece of text using HuggingFace's `cardiffnlp/twitter-roberta-base-sentiment-latest` transformer model
3. **Features** — aggregates sentiment scores per team into a feature matrix alongside game context (home/away, rest days, injury flags)
4. **Predict** — classifies game outcome (win/loss) using a threshold rule and logistic regression trained on Conference Finals data

## Results

Evaluated on live 2026 NBA Playoffs games. Simple sentiment-differential threshold rule achieved **~67% accuracy** on Conference Finals games, outperforming logistic regression at this sample size (n≈9).

## Stack

- Python 3.11
- HuggingFace Transformers 4.40.0 + PyTorch 2.2.2
- scikit-learn, pandas, numpy
- YouTube Data API v3

> **Note:** Intel Mac constraint — PyTorch caps at 2.2.2, so `transformers` is pinned to 4.40.0 and `numpy<2`.

## Setup

```bash
git clone https://github.com/TjWill859/nba-sentiment-predictor.git
cd nba-sentiment-predictor

python -m venv venv
source venv/bin/activate

pip install -r requirements.txt
```

Copy `.env.example` to `.env` and add your YouTube Data API key:

YOUTUBE_API_KEY=your_key_here


## Usage

```bash
# Run a prediction for the next game
python predict.py
```

## Project Structure

    nba_predictor/
    ├── scrapers/          # YouTube + ESPN + injury data scrapers
    ├── pipeline/          # Sentiment scoring, feature engineering, model training
    ├── data/              # game_index.json (game metadata + result labels)
    ├── predict.py         # Main prediction entry point
    └── requirements.txt

## Context

- **Training data:** 2026 Western and Eastern Conference Finals games
- **Live evaluation:** 2026 NBA Finals (NYK vs. SAS), starting June 3
- **Prediction target:** Binary win/loss outcome for the home team
