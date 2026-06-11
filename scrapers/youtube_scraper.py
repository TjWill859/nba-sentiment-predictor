import os
import time
import logging
import argparse
import pandas as pd
from datetime import datetime, timedelta, timezone
from pathlib import Path

from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from dotenv import load_dotenv

# Config 

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data" / "raw"
DATA_DIR.mkdir(parents=True, exist_ok=True)

load_dotenv(BASE_DIR / ".env")
YOUTUBE_API_KEY = os.getenv("YOUTUBE_API_KEY")

# Channels known for pre-game NBA content (filter to these for higher quality)
TRUSTED_CHANNEL_IDS = {
    "ESPN":             "UCiWLfSweyRNmLpgEHekhoAg",
    "NBA":              "UCWX3yGbODI3RKzABMFXMpOA",
    "HouseOfHighlights":"UCnUYZLuoy1rq1aVMwx4aTzw",
    "BleacherReport":   "UCmMDMi8H9XGAWEBfXsH1zvQ",
}

# Search queries to find pre-game preview videos
SEARCH_QUERY_TEMPLATES = [
    "{team1} vs {team2} Game {game} preview",
    "{team1} {team2} NBA Finals Game {game} 2026",
    "NBA Finals Game {game} preview 2026",
    "{team1} vs {team2} prediction Game {game}",
]

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger(__name__)


# Mock data 

MOCK_VIDEOS = [
    {"video_id": "mock_v1", "title": "Knicks vs Spurs Game 4 Preview | NBA Finals 2026", "channel": "ESPN", "published_at": datetime.now(timezone.utc).isoformat(), "view_count": 142000},
    {"video_id": "mock_v2", "title": "Can Wembanyama play in Game 4? Injury update + prediction", "channel": "HouseOfHighlights", "published_at": (datetime.now(timezone.utc) - timedelta(hours=8)).isoformat(), "view_count": 87000},
    {"video_id": "mock_v3", "title": "NYK vs SAS Game 4 Breakdown — Who wins at MSG?", "channel": "BleacherReport", "published_at": (datetime.now(timezone.utc) - timedelta(hours=14)).isoformat(), "view_count": 63000},
]

MOCK_COMMENTS = {
    "mock_v1": [
        {"comment_id": "c1", "text": "Knicks in 6, MSG is going to be insane tomorrow night", "likes": 412, "published_at": datetime.now(timezone.utc).isoformat(), "video_id": "mock_v1"},
        {"comment_id": "c2", "text": "If Wemby is out the Spurs have no shot, Knicks close it out", "likes": 287, "published_at": datetime.now(timezone.utc).isoformat(), "video_id": "mock_v1"},
        {"comment_id": "c3", "text": "Spurs defense has been elite, don't sleep on them. Game 4 is a must-win", "likes": 198, "published_at": datetime.now(timezone.utc).isoformat(), "video_id": "mock_v1"},
        {"comment_id": "c4", "text": "Brunson is locked in, nobody stopping him at home", "likes": 156, "published_at": datetime.now(timezone.utc).isoformat(), "video_id": "mock_v1"},
        {"comment_id": "c5", "text": "San Antonio has been here before. Don't count them out", "likes": 134, "published_at": datetime.now(timezone.utc).isoformat(), "video_id": "mock_v1"},
    ],
    "mock_v2": [
        {"comment_id": "c6", "text": "Wemby playing through it shows how much heart this team has", "likes": 321, "published_at": datetime.now(timezone.utc).isoformat(), "video_id": "mock_v2"},
        {"comment_id": "c7", "text": "Knicks are going to bully him on that ankle, smart coaching to target it", "likes": 89, "published_at": datetime.now(timezone.utc).isoformat(), "video_id": "mock_v2"},
        {"comment_id": "c8", "text": "Even at 80% Wemby is the best player in this series", "likes": 245, "published_at": datetime.now(timezone.utc).isoformat(), "video_id": "mock_v2"},
    ],
    "mock_v3": [
        {"comment_id": "c9", "text": "MSG crowd is going to will this team to a 3-1 lead", "likes": 178, "published_at": datetime.now(timezone.utc).isoformat(), "video_id": "mock_v3"},
        {"comment_id": "c10", "text": "Spurs need to go small and push pace, they can't play halfcourt against NY", "likes": 203, "published_at": datetime.now(timezone.utc).isoformat(), "video_id": "mock_v3"},
    ],
}


# YouTube API helpers 

def get_youtube_client():
    if not YOUTUBE_API_KEY:
        raise ValueError("YOUTUBE_API_KEY not found. Add it to your .env file.")
    return build("youtube", "v3", developerKey=YOUTUBE_API_KEY)


def search_pregame_videos(
    yt,
    team1: str,
    team2: str,
    game_num: int,
    hours_back: int = 48,
    max_results_per_query: int = 5,
    game_date: str | None = None,
) -> list[dict]:
    
    cutoff = datetime.now(timezone.utc) - timedelta(hours=hours_back)
    published_before = None
    if game_date:
        tip_off = datetime.strptime(game_date, "%Y-%m-%d").replace(tzinfo=timezone.utc)
        cutoff = tip_off - timedelta(hours=hours_back)
        published_after = cutoff.strftime("%Y-%m-%dT%H:%M:%SZ")
        published_before = (tip_off + timedelta(hours=20)).strftime("%Y-%m-%dT%H:%M:%SZ")
    else:
        cutoff = datetime.now(timezone.utc) - timedelta(hours=hours_back)
        published_after = cutoff.strftime("%Y-%m-%dT%H:%M:%SZ")

    seen_ids = set()
    videos = []

    for template in SEARCH_QUERY_TEMPLATES:
        query = template.format(team1=team1, team2=team2, game=game_num)
        log.info(f"  Searching: '{query}'")
        try:
            response = yt.search().list(
                part="snippet",
                q=query,
                type="video",
                order="relevance",
                publishedAfter=published_after,
                publishedBefore=published_before,
                maxResults=max_results_per_query,
                relevanceLanguage="en",
            ).execute()
        except HttpError as e:
            log.error(f"YouTube search API error: {e}")
            continue

        for item in response.get("items", []):
            vid_id = item["id"]["videoId"]
            if vid_id in seen_ids:
                continue
            seen_ids.add(vid_id)

            snippet = item["snippet"]
            videos.append({
                "video_id": vid_id,
                "title": snippet.get("title", ""),
                "channel": snippet.get("channelTitle", ""),
                "published_at": snippet.get("publishedAt", ""),
                "view_count": None,  # filled in below
            })

        time.sleep(0.3)  # stay well under quota

    if not videos:
        return videos

    # Enrich with view counts (single batch call)
    try:
        video_ids = [v["video_id"] for v in videos]
        stats_resp = yt.videos().list(
            part="statistics",
            id=",".join(video_ids),
        ).execute()
        stats_map = {
            item["id"]: int(item["statistics"].get("viewCount", 0))
            for item in stats_resp.get("items", [])
        }
        for v in videos:
            v["view_count"] = stats_map.get(v["video_id"], 0)
    except HttpError as e:
        log.warning(f"Could not fetch video stats: {e}")

    # Sort by view count — more viewed = more comments = better signal
    videos.sort(key=lambda v: v.get("view_count") or 0, reverse=True)
    log.info(f"Found {len(videos)} unique pre-game videos")
    return videos


def fetch_comments_for_video(
    yt,
    video_id: str,
    max_comments: int = 100,
) -> list[dict]:
    
    comments = []
    next_page_token = None

    while len(comments) < max_comments:
        try:
            response = yt.commentThreads().list(
                part="snippet",
                videoId=video_id,
                order="relevance",
                maxResults=min(100, max_comments - len(comments)),
                pageToken=next_page_token,
                textFormat="plainText",
            ).execute()
        except HttpError as e:
            if "commentsDisabled" in str(e):
                log.info(f"  Comments disabled for video {video_id}")
            else:
                log.warning(f"  Comment fetch error for {video_id}: {e}")
            break

        for item in response.get("items", []):
            top = item["snippet"]["topLevelComment"]["snippet"]
            comments.append({
                "comment_id": item["id"],
                "text": top.get("textDisplay", ""),
                "likes": top.get("likeCount", 0),
                "published_at": top.get("publishedAt", ""),
                "video_id": video_id,
            })

        next_page_token = response.get("nextPageToken")
        if not next_page_token:
            break
        time.sleep(0.2)

    return comments


# Main collection logic 

def collect_pregame_comments(
    team1: str = "NYK",
    team2: str = "SAS",
    game_num: int = 4,
    hours_back: int = 48,
    max_videos: int = 5,
    max_comments_per_video: int = 100,
    test_mode: bool = False,
    game_date: str | None = None,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    
    log.info(f"Collecting YouTube comments: {team1} vs {team2} Game {game_num} | test={test_mode}")

    if test_mode:
        videos = MOCK_VIDEOS[:max_videos]
        all_comments = []
        for v in videos:
            all_comments.extend(MOCK_COMMENTS.get(v["video_id"], []))
    else:
        yt = get_youtube_client()
        videos = search_pregame_videos(yt, team1, team2, game_num, hours_back, game_date=game_date)[:max_videos]
        if not videos:
            log.warning("No videos found. Try wider --hours or different team names.")
            return pd.DataFrame(), pd.DataFrame()

        all_comments = []
        for v in videos:
            log.info(f"  Fetching comments: '{v['title'][:60]}' ({v.get('view_count', '?')} views)")
            comments = fetch_comments_for_video(yt, v["video_id"], max_comments_per_video)
            all_comments.extend(comments)
            log.info(f"    → {len(comments)} comments")
            time.sleep(0.5)

    videos_df = pd.DataFrame(videos)
    comments_df = pd.DataFrame(all_comments)

    if comments_df.empty:
        log.warning("No comments collected.")
        return videos_df, comments_df

    # Add metadata columns useful for the sentiment pipeline
    comments_df["team1"] = team1
    comments_df["team2"] = team2
    comments_df["game_num"] = game_num
    comments_df["scraped_at"] = datetime.now(timezone.utc).isoformat()
    comments_df["source"] = "youtube"

    # Save
    timestamp = datetime.now().strftime("%Y%m%d_%H%M")
    suffix = "_TEST" if test_mode else ""
    base = f"youtube_{team1}_{team2}_G{game_num}_{timestamp}{suffix}"

    videos_df.to_csv(DATA_DIR / f"{base}_videos.csv", index=False)
    comments_df.to_csv(DATA_DIR / f"{base}_comments.csv", index=False)
    comments_df.to_json(DATA_DIR / f"{base}_comments.json", orient="records", indent=2)

    log.info(f"Saved {len(videos_df)} videos, {len(comments_df)} comments → data/raw/{base}*")
    return videos_df, comments_df


# CLI 

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Scrape YouTube pre-game comments for NBA sentiment")
    parser.add_argument("--team1", default="NYK")
    parser.add_argument("--team2", default="SAS")
    parser.add_argument("--game", type=int, default=4, help="Game number (default: 4)")
    parser.add_argument("--hours", type=int, default=48, help="Lookback window in hours (default: 48)")
    parser.add_argument("--max-videos", type=int, default=5, help="Max videos to pull comments from")
    parser.add_argument("--max-comments", type=int, default=100, help="Max comments per video")
    parser.add_argument("--test", action="store_true", help="Use mock data (no API calls)")
    parser.add_argument("--date", type=str, help="Game date (YYYY-MM-DD) to set search window around tip-off")
    args = parser.parse_args()

    videos_df, comments_df = collect_pregame_comments(
        team1=args.team1,
        team2=args.team2,
        game_num=args.game,
        hours_back=args.hours,
        max_videos=args.max_videos,
        max_comments_per_video=args.max_comments,
        test_mode=args.test,
        game_date=args.date,
    )

    if not comments_df.empty:
        print(f"\n{'─'*65}")
        print(f"  {len(videos_df)} videos | {len(comments_df)} comments | {args.team1} vs {args.team2} G{args.game}")
        print(f"{'─'*65}")
        for _, v in videos_df.iterrows():
            views = f"{v.get('view_count', 0):,}" if v.get("view_count") else "?"
            print(f"  [{views:>8} views] {v['title'][:52]}")
        print(f"{'─'*65}")
        print(f"\n  Sample comments:")
        for _, row in comments_df.head(5).iterrows():
            print(f"  ♟ {row['text'][:75]}")
