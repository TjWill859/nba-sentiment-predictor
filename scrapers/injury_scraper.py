"""
NBA injury report scraper.
Primary: Ball Don't Lie API v1 (free, no auth needed)
Fallback: NBA.com official injury JSON

Produces a structured injury DataFrame used as features in the classifier:
  - is_injured / status (out, questionable, probable, available)
  - player importance tier (star, starter, bench)
  - team injury load score (0-1)

Usage:
    python injury_scraper.py                        # NYK vs SAS (default)
    python injury_scraper.py --team1 NYK --team2 SAS
    python injury_scraper.py --test                 # mock data, no network
"""

import requests
import pandas as pd
import json
import time
import logging
import argparse
from datetime import datetime, timezone
from pathlib import Path

# ── Config ────────────────────────────────────────────────────────────────────

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data" / "raw"
DATA_DIR.mkdir(parents=True, exist_ok=True)

# Ball Don't Lie free API — no key needed for v1
BDL_BASE = "https://www.balldontlie.io/api/v1"
BDL_INJURIES_URL = f"{BDL_BASE}/injuries"          # returns active injuries
BDL_PLAYERS_URL  = f"{BDL_BASE}/players"

# NBA.com official injury report JSON (backup)
NBA_INJURIES_URL = "https://stats.nba.com/js/data/leaders/00_player_injuries.json"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
    "Referer": "https://www.nba.com/",
    "Accept": "application/json",
}

# Team name → BDL team ID (2025-26 season)
TEAM_IDS = {
    "NYK": 20,   # New York Knicks
    "SAS": 28,   # San Antonio Spurs
    "BOS": 2,    # Boston Celtics
    "MIA": 16,   # Miami Heat
    "GSW": 9,    # Golden State Warriors
    "LAL": 14,   # Los Angeles Lakers
    "DEN": 7,    # Denver Nuggets
    "PHX": 24,   # Phoenix Suns
    "CLE": 5,    # Cleveland Cavaliers
    "OKC": 21,   # Oklahoma City Thunder
}

# Known star/starter players for Finals teams — used for importance weighting
# Format: {player_last_name: tier}  tier: "star" | "starter" | "bench"
PLAYER_TIERS = {
    # NYK
    "brunson":    "star",
    "anunoby":    "starter",
    "hartenstein": "starter",
    "randle":     "starter",
    "divincenzo": "starter",
    "hart":       "bench",
    "robinson":   "bench",
    # SAS
    "wembanyama": "star",
    "castle":     "starter",
    "jones":      "starter",
    "sochan":     "starter",
    "johnson":    "bench",
    "vassell":    "starter",
}

# Status severity — higher = more impactful
STATUS_SEVERITY = {
    "out":          1.0,
    "doubtful":     0.75,
    "questionable": 0.5,
    "probable":     0.25,
    "available":    0.0,
    "day-to-day":   0.4,
}

TIER_WEIGHT = {
    "star":    1.0,
    "starter": 0.5,
    "bench":   0.2,
    "unknown": 0.1,
}

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger(__name__)


# ── Mock data ─────────────────────────────────────────────────────────────────

MOCK_INJURIES = [
    {
        "player_name":   "Victor Wembanyama",
        "team":          "SAS",
        "status":        "questionable",
        "reason":        "Right ankle soreness",
        "updated_at":    datetime.now(timezone.utc).isoformat(),
        "source":        "mock",
    },
    {
        "player_name":   "Jalen Brunson",
        "team":          "NYK",
        "status":        "available",
        "reason":        "",
        "updated_at":    datetime.now(timezone.utc).isoformat(),
        "source":        "mock",
    },
    {
        "player_name":   "Mitchell Robinson",
        "team":          "NYK",
        "status":        "out",
        "reason":        "Left knee (season-ending)",
        "updated_at":    datetime.now(timezone.utc).isoformat(),
        "source":        "mock",
    },
]


# ── Fetchers ──────────────────────────────────────────────────────────────────

def fetch_bdl_injuries(team_abbr: str) -> list[dict]:
    """Fetch injuries for a team from Ball Don't Lie API v1."""
    team_id = TEAM_IDS.get(team_abbr.upper())
    if not team_id:
        log.warning(f"No BDL team ID for {team_abbr}")
        return []

    log.info(f"  Fetching BDL injuries for {team_abbr} (team_id={team_id})...")
    try:
        resp = requests.get(
            BDL_INJURIES_URL,
            params={"team_ids[]": team_id},
            headers=HEADERS,
            timeout=12,
        )
        resp.raise_for_status()
        data = resp.json()
    except requests.RequestException as e:
        log.error(f"BDL API error for {team_abbr}: {e}")
        return []

    results = []
    for item in data.get("data", []):
        player = item.get("player", {})
        results.append({
            "player_name": f"{player.get('first_name', '')} {player.get('last_name', '')}".strip(),
            "team":        team_abbr.upper(),
            "status":      item.get("status", "").lower(),
            "reason":      item.get("notes", ""),
            "updated_at":  item.get("updated_at", datetime.now(timezone.utc).isoformat()),
            "source":      "balldontlie",
        })
    return results


def fetch_nba_official_injuries() -> list[dict]:
    """
    Fallback: fetch from NBA.com's official injury JSON.
    Returns raw list — caller filters by team.
    """
    log.info("  Fetching NBA.com official injury report...")
    try:
        resp = requests.get(NBA_INJURIES_URL, headers=HEADERS, timeout=12)
        resp.raise_for_status()
        data = resp.json()
    except requests.RequestException as e:
        log.error(f"NBA.com injury fetch failed: {e}")
        return []

    results = []
    for row in data.get("LeagueInjuries", {}).get("rowSet", []):
        # NBA.com format: [team_abbr, player_name, date, status, reason, ...]
        if len(row) < 5:
            continue
        results.append({
            "player_name": row[1],
            "team":        row[0],
            "status":      row[3].lower(),
            "reason":      row[4],
            "updated_at":  row[2],
            "source":      "nba.com",
        })
    return results


# ── Feature engineering ───────────────────────────────────────────────────────

def classify_player_tier(player_name: str) -> str:
    """Return star/starter/bench/unknown for a player."""
    last = player_name.split()[-1].lower() if player_name else ""
    return PLAYER_TIERS.get(last, "unknown")


def compute_team_injury_load(team_df: pd.DataFrame) -> float:
    """
    Compute a 0-1 injury load score for a team.
    Higher = more impactful players are out/questionable.
    Formula: sum(severity * tier_weight) / max_possible
    """
    if team_df.empty:
        return 0.0

    score = 0.0
    for _, row in team_df.iterrows():
        sev  = STATUS_SEVERITY.get(row["status"], 0.0)
        wt   = TIER_WEIGHT.get(row["player_tier"], 0.1)
        score += sev * wt

    # Normalize: assume max realistic load = 2 stars out (2 * 1.0 * 1.0)
    max_load = 2.0
    return min(round(score / max_load, 4), 1.0)


def enrich_injuries(raw: list[dict], team_abbr: str) -> pd.DataFrame:
    """Add tier, severity, and load columns to raw injury list."""
    df = pd.DataFrame(raw)
    if df.empty:
        return df

    df = df[df["team"] == team_abbr.upper()].copy()
    df["player_tier"]       = df["player_name"].apply(classify_player_tier)
    df["status_severity"]   = df["status"].map(STATUS_SEVERITY).fillna(0.0)
    df["is_out"]            = df["status"].isin(["out", "doubtful"]).astype(int)
    df["is_questionable"]   = (df["status"] == "questionable").astype(int)
    df["is_star_affected"]  = ((df["player_tier"] == "star") & (df["status"] != "available")).astype(int)
    return df.reset_index(drop=True)


# ── Main collection logic ──────────────────────────────────────────────────────

def collect_injury_reports(
    team1: str = "NYK",
    team2: str = "SAS",
    test_mode: bool = False,
) -> dict:
    """
    Collect and structure injury reports for both teams.

    Returns dict with keys:
        'injuries_df'   — full per-player injury table
        'summary'       — per-team feature dict ready for classifier
    """
    log.info(f"Collecting injury reports: {team1} vs {team2} | test={test_mode}")

    if test_mode:
        raw = MOCK_INJURIES
    else:
        raw = fetch_bdl_injuries(team1) + fetch_bdl_injuries(team2)
        time.sleep(0.5)

        if not raw:
            log.warning("BDL returned nothing — trying NBA.com fallback...")
            all_injuries = fetch_nba_official_injuries()
            t1, t2 = team1.upper(), team2.upper()
            raw = [i for i in all_injuries if i["team"] in (t1, t2)]

    if not raw:
        log.warning("No injury data found from any source.")
        return {"injuries_df": pd.DataFrame(), "summary": {}}

    df1 = enrich_injuries(raw, team1)
    df2 = enrich_injuries(raw, team2)
    injuries_df = pd.concat([df1, df2], ignore_index=True)

    # Per-team feature summary (this is what goes into the classifier)
    summary = {}
    for abbr, df in [(team1, df1), (team2, df2)]:
        summary[abbr] = {
            "team":                  abbr,
            "injury_load_score":     compute_team_injury_load(df),
            "stars_affected":        int(df["is_star_affected"].sum()) if not df.empty else 0,
            "players_out":           int(df["is_out"].sum()) if not df.empty else 0,
            "players_questionable":  int(df["is_questionable"].sum()) if not df.empty else 0,
            "total_injured":         len(df) if not df.empty else 0,
        }

    # Save
    timestamp = datetime.now().strftime("%Y%m%d_%H%M")
    suffix = "_TEST" if test_mode else ""
    csv_path  = DATA_DIR / f"injuries_{team1}_{team2}_{timestamp}{suffix}.csv"
    json_path = DATA_DIR / f"injuries_{team1}_{team2}_{timestamp}{suffix}.json"

    injuries_df.to_csv(csv_path, index=False)
    with open(json_path, "w") as f:
        json.dump({"injuries": injuries_df.to_dict(orient="records"), "summary": summary}, f, indent=2)

    log.info(f"Saved → {csv_path}")

    return {"injuries_df": injuries_df, "summary": summary}


# ── CLI ───────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Fetch NBA injury reports")
    parser.add_argument("--team1", default="NYK")
    parser.add_argument("--team2", default="SAS")
    parser.add_argument("--test", action="store_true", help="Use mock data")
    args = parser.parse_args()

    result = collect_injury_reports(
        team1=args.team1,
        team2=args.team2,
        test_mode=args.test,
    )

    injuries_df = result["injuries_df"]
    summary     = result["summary"]

    if not injuries_df.empty:
        print(f"\n{'─'*65}")
        print(f"  Injury Report: {args.team1} vs {args.team2}")
        print(f"{'─'*65}")
        for _, row in injuries_df.iterrows():
            star = "⭐" if row["player_tier"] == "star" else "  "
            print(f"  {star} [{row['team']}] {row['player_name']:<22} {row['status']:<14} {row['reason'][:28]}")
        print(f"\n  Team Injury Load Scores:")
        for abbr, feat in summary.items():
            bar = "█" * int(feat["injury_load_score"] * 20)
            print(f"  {abbr}: {feat['injury_load_score']:.2f} |{bar:<20}|  stars affected: {feat['stars_affected']}")
        print(f"{'─'*65}")
        print(f"\n  Classifier features:")
        print(json.dumps(summary, indent=4))
