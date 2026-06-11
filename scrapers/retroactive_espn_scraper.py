"""
Retroactive ESPN scraper for Conference Finals + Finals games.
Uses ESPN's search API to find articles by date window.
"""

import requests
import json
import time
import logging
log = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
import pandas as pd
from datetime import datetime, timedelta, timezone
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data" / "raw" / "espn"
DATA_DIR.mkdir(parents=True, exist_ok=True)

ESPN_SEARCH_API = "https://site.web.api.espn.com/apis/search/v2"

TEAM_KEYWORDS = {
    "NYK": ["knicks", "new york knicks", "new york"],
    "SAS": ["spurs", "san antonio spurs", "san antonio", "wembanyama", "wemby"],
    "OKC": ["thunder", "oklahoma city thunder", "oklahoma city", "sga", "gilgeous-alexander"],
    "CLE": ["cavaliers", "cleveland cavaliers", "cleveland", "harden"],
}

GAMES = [
    ("SAS", "OKC", "2026-05-18", 1),
    ("CLE", "NYK", "2026-05-19", 1),
    ("SAS", "OKC", "2026-05-20", 2),
    ("CLE", "NYK", "2026-05-21", 2),
    ("OKC", "SAS", "2026-05-22", 3),
    ("NYK", "CLE", "2026-05-23", 3),
    ("OKC", "SAS", "2026-05-24", 4),
    ("NYK", "CLE", "2026-05-25", 4),
    ("SAS", "OKC", "2026-05-26", 5),
    ("OKC", "SAS", "2026-05-28", 6),
    ("SAS", "OKC", "2026-05-30", 7),
    ("NYK", "SAS", "2026-06-03", 1),
    ("NYK", "SAS", "2026-06-05", 2),
    ("SAS", "NYK", "2026-06-08", 3),
    ("SAS", "NYK", "2026-06-10", 4),
]

def search_espn_articles(query):
    try:
        response = requests.get(ESPN_SEARCH_API, params={"query": query, "limit": 20, "type": "article"}, headers={"User-Agent": "Mozilla/5.0"}, timeout=15)
        response.raise_for_status()
        data = response.json()
        return data["results"][0]["contents"]
    except Exception as e:
        log.error(f"Search failed for '{query}': {e}")
        return []
    
def collect_game_articles(team1, team2, game_date, game_num):
    tip_off = datetime.strptime(game_date, "%Y-%m-%d").replace(tzinfo=timezone.utc)
    published_after = tip_off - timedelta(hours=48)
    published_before = tip_off + timedelta(hours=20)

    name1 = TEAM_KEYWORDS[team1][0]
    name2 = TEAM_KEYWORDS[team2][0]
    queries = [
        f"{name1} {name2} game {game_num} preview",
        f"{name1} {name2} game {game_num} prediction",
        f"{name1} {name2} nba playoffs 2026",
    ]

    articles = []
    seen_ids = set()

    for query in queries:
        results = search_espn_articles(query)
        for article in results:
            art_id = article.get("id")
            if art_id in seen_ids:
                continue
            seen_ids.add(art_id)

            # Parse and filter by date
            raw_date = article.get("date", "")
            try:
                pub_date = datetime.fromisoformat(raw_date.replace("Z", "+00:00"))
            except ValueError:
                continue
            if not (published_after <= pub_date <= published_before):
                continue

            url = article.get("link", {}).get("web", "")
            title = article.get("displayName", "")

            articles.append({
                "title": title,
                "url": url,
                "snippet": title,
                "full_text": title,
                "team_relevance": f"{team1},{team2}",
                "published_at": pub_date.isoformat(),
                "scraped_at": datetime.now(timezone.utc).isoformat(),
                "source": "espn",
            })

        time.sleep(0.5)

    if not articles:
        log.warning(f"No articles found for {team1} vs {team2} Game {game_num}")
        return []

    # Save
    timestamp = datetime.now().strftime("%Y%m%d_%H%M")
    filename = f"espn_{team1}_{team2}_G{game_num}_{timestamp}.json"
    path = DATA_DIR / filename
    with open(path, "w") as f:
        json.dump(articles, f, indent=2)
    log.info(f"Saved {len(articles)} articles → {path}")

    return articles


if __name__ == "__main__":
    for team1, team2, game_date, game_num in GAMES:
        print(f"\n{'='*60}")
        print(f"  {team1} vs {team2} Game {game_num} | {game_date}")
        print(f"{'='*60}")
        articles = collect_game_articles(team1, team2, game_date, game_num)
        print(f"  → {len(articles)} articles collected")
        time.sleep(2)
    print("\nDone.")