import requests
import pandas as pd
import json
import time
import logging
import argparse
from datetime import datetime, timedelta, timezone
from pathlib import Path

# Config 

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data" / "raw"
DATA_DIR.mkdir(parents=True, exist_ok=True)

ESPN_NEWS_API = "https://site.api.espn.com/apis/site/v2/sports/basketball/nba/news"
ESPN_ARTICLE_API = "https://site.api.espn.com/apis/site/v2/sports/basketball/nba/news/{article_id}"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json",
    "Referer": "https://www.espn.com/",
}

TEAM_KEYWORDS = {
    "NYK": ["knicks", "new york knicks", "nyk", "new york"],
    "SAS": ["spurs", "san antonio spurs", "sas", "san antonio"],
    "BOS": ["celtics", "boston celtics", "boston"],
    "MIA": ["heat", "miami heat", "miami"],
    "GSW": ["warriors", "golden state warriors", "golden state"],
    "LAL": ["lakers", "los angeles lakers", "los angeles lakers"],
    "DEN": ["nuggets", "denver nuggets", "denver"],
    "PHX": ["suns", "phoenix suns", "phoenix"],
    "CLE": ["cavaliers", "cleveland cavaliers", "cleveland"],
    "OKC": ["thunder", "oklahoma city thunder", "oklahoma city"],
}

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger(__name__)


# Mock data for offline testing 

MOCK_ARTICLES = [
    {
        "headline": "Knicks look to take 3-1 series lead as Jalen Brunson returns to form",
        "description": "New York has momentum after two close wins in San Antonio. Brunson posted 34 points in Game 2.",
        "published": datetime.now(timezone.utc).isoformat(),
        "links": {"web": {"href": "https://www.espn.com/nba/story/_/id/mock1"}},
        "id": "mock1",
    },
    {
        "headline": "Spurs' Victor Wembanyama questionable for Game 4 with ankle soreness",
        "description": "San Antonio's star center is listed as questionable after rolling his ankle late in Game 3.",
        "published": (datetime.now(timezone.utc) - timedelta(hours=12)).isoformat(),
        "links": {"web": {"href": "https://www.espn.com/nba/story/_/id/mock2"}},
        "id": "mock2",
    },
    {
        "headline": "NBA Finals preview: Can the Knicks close out at Madison Square Garden?",
        "description": "New York hosts Game 4 with a chance to go up 3-1. Home crowd will be electric.",
        "published": (datetime.now(timezone.utc) - timedelta(hours=6)).isoformat(),
        "links": {"web": {"href": "https://www.espn.com/nba/story/_/id/mock3"}},
        "id": "mock3",
    },
    {
        "headline": "Spurs coaching staff adjusting defensive schemes ahead of Game 4",
        "description": "San Antonio plans to attack New York's pick-and-roll coverage after it was exposed in Games 1 and 2.",
        "published": (datetime.now(timezone.utc) - timedelta(hours=20)).isoformat(),
        "links": {"web": {"href": "https://www.espn.com/nba/story/_/id/mock4"}},
        "id": "mock4",
    },
    {
        "headline": "OG Anunoby on Knicks' defensive identity: 'We make every game hard'",
        "description": "New York's wing defender has been key to limiting San Antonio's transition offense.",
        "published": (datetime.now(timezone.utc) - timedelta(hours=30)).isoformat(),
        "links": {"web": {"href": "https://www.espn.com/nba/story/_/id/mock5"}},
        "id": "mock5",
    },
]


# ESPN API fetchers 

def fetch_espn_news(limit: int = 50) -> list[dict]:
    """Fetch NBA news from ESPN's public JSON API."""
    log.info("Fetching ESPN NBA news via JSON API...")
    try:
        resp = requests.get(
            ESPN_NEWS_API,
            params={"limit": limit},
            headers=HEADERS,
            timeout=15,
        )
        resp.raise_for_status()
        data = resp.json()
        articles = data.get("articles", [])
        log.info(f"ESPN API returned {len(articles)} articles")
        return articles
    except requests.HTTPError as e:
        log.error(f"ESPN API HTTP error: {e}")
    except requests.RequestException as e:
        log.error(f"ESPN API request failed: {e}")
    except json.JSONDecodeError:
        log.error("ESPN API returned non-JSON response")
    return []


def fetch_article_body(article: dict) -> str:
    """
    Try to get the full article text. ESPN's API sometimes includes
    a 'story' field; otherwise fall back to headline + description.
    """
    # Some ESPN API responses include full story text
    story = article.get("story", "")
    if story:
        return story

    # Fall back to description (usually a 1-2 sentence summary)
    return article.get("description", "")


def parse_published_date(article: dict) -> datetime | None:
    """Parse the 'published' or 'lastModified' field into a timezone-aware datetime."""
    for field in ("published", "lastModified"):
        raw = article.get(field)
        if raw:
            try:
                # ESPN format: "2026-06-08T14:32:00Z"
                return datetime.fromisoformat(raw.replace("Z", "+00:00"))
            except ValueError:
                pass
    return None


# Relevance filtering 

def is_relevant(article: dict, keywords: list[str]) -> bool:
    combined = " ".join([
        article.get("headline", ""),
        article.get("description", ""),
        article.get("story", ""),
    ]).lower()
    return any(kw in combined for kw in keywords)


def team_relevance_tags(article: dict, team1: str, team2: str) -> str:
    kw1 = TEAM_KEYWORDS.get(team1.upper(), [team1.lower()])
    kw2 = TEAM_KEYWORDS.get(team2.upper(), [team2.lower()])
    combined = " ".join([
        article.get("headline", ""),
        article.get("description", ""),
        article.get("story", ""),
    ]).lower()
    tags = []
    if any(kw in combined for kw in kw1):
        tags.append(team1)
    if any(kw in combined for kw in kw2):
        tags.append(team2)
    return ",".join(tags)


# Main collection logic

def collect_pregame_articles(
    team1: str = "NYK",
    team2: str = "SAS",
    hours_back: int = 48,
    max_articles: int = 30,
    test_mode: bool = False,
) -> pd.DataFrame:

    kw1 = TEAM_KEYWORDS.get(team1.upper(), [team1.lower()])
    kw2 = TEAM_KEYWORDS.get(team2.upper(), [team2.lower()])
    all_keywords = kw1 + kw2
    cutoff = datetime.now(timezone.utc) - timedelta(hours=hours_back)

    log.info(f"Collecting ESPN articles: {team1} vs {team2} | last {hours_back}h | test={test_mode}")

    raw_articles = MOCK_ARTICLES if test_mode else fetch_espn_news(limit=50)

    if not raw_articles and not test_mode:
        log.warning("No articles returned from ESPN API.")

    results = []
    for article in raw_articles[:max_articles]:
        if not is_relevant(article, all_keywords):
            continue

        pub_date = parse_published_date(article)
        if pub_date and pub_date < cutoff:
            log.debug(f"Skipping old article: {article.get('headline', '')[:60]}")
            continue

        body = fetch_article_body(article)
        url = article.get("links", {}).get("web", {}).get("href", "")

        results.append({
            "title": article.get("headline", ""),
            "url": url,
            "snippet": article.get("description", ""),
            "full_text": body,
            "team_relevance": team_relevance_tags(article, team1, team2),
            "published_at": pub_date.isoformat() if pub_date else "",
            "scraped_at": datetime.now(timezone.utc).isoformat(),
            "source": "espn",
        })

        if not test_mode:
            time.sleep(0.5)  # polite crawl delay

    df = pd.DataFrame(results)
    log.info(f"Collected {len(df)} relevant articles")

    if df.empty:
        log.warning("No matching articles found. Check team keywords or try --hours 72.")
        return df

    # Save
    timestamp = datetime.now().strftime("%Y%m%d_%H%M")
    suffix = "_TEST" if test_mode else ""
    csv_path = DATA_DIR / f"espn_{team1}_{team2}_{timestamp}{suffix}.csv"
    json_path = DATA_DIR / f"espn_{team1}_{team2}_{timestamp}{suffix}.json"

    df.to_csv(csv_path, index=False)
    df.to_json(json_path, orient="records", indent=2)
    log.info(f"Saved → {csv_path}")
    log.info(f"Saved → {json_path}")

    return df


# CLI 

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Scrape ESPN NBA pre-game articles")
    parser.add_argument("--team1", default="NYK", help="Team 1 abbreviation (default: NYK)")
    parser.add_argument("--team2", default="SAS", help="Team 2 abbreviation (default: SAS)")
    parser.add_argument("--hours", type=int, default=48, help="Lookback window in hours (default: 48)")
    parser.add_argument("--max", type=int, default=30, help="Max articles to process (default: 30)")
    parser.add_argument("--test", action="store_true", help="Use mock data (no network calls)")
    args = parser.parse_args()

    df = collect_pregame_articles(
        team1=args.team1,
        team2=args.team2,
        hours_back=args.hours,
        max_articles=args.max,
        test_mode=args.test,
    )

    if not df.empty:
        print(f"\n{'─'*65}")
        print(f"  {len(df)} articles | {args.team1} vs {args.team2} | last {args.hours}h")
        print(f"{'─'*65}")
        for _, row in df.iterrows():
            print(f"  [{row['team_relevance']:6s}] {row['title'][:65]}")
        print(f"{'─'*65}")
