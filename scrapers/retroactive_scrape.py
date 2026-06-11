"""
Retroactive YouTube scraper for Conference Finals games.
Run once to collect historical pre-game data.

Usage:
    python retroactive_scrape.py
    python retroactive_scrape.py --max-videos 3 --max-comments 75
"""

import argparse
import time
from youtube_scraper import collect_pregame_comments

GAMES = [
    # ("SAS", "OKC", "2026-05-18", 1),
    # ("CLE", "NYK", "2026-05-19", 1),
    # ("SAS", "OKC", "2026-05-20", 2),
    # ("CLE", "NYK", "2026-05-21", 2),
    # ("OKC", "SAS", "2026-05-22", 3),
    # ("NYK", "CLE", "2026-05-23", 3),
    # ("OKC", "SAS", "2026-05-24", 4),
    # ("NYK", "CLE", "2026-05-25", 4),
    # ("SAS", "OKC", "2026-05-26", 5),
    # ("OKC", "SAS", "2026-05-28", 6),
    # ("SAS", "OKC", "2026-05-30", 7),
    # ("NYK", "SAS", "2026-06-03", 1),
    # ("NYK", "SAS", "2026-06-05", 2),
    # ("SAS", "NYK", "2026-06-08", 3),
    ("SAS", "NYK", "2026-06-10", 4),
]

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--max-videos", type=int, default=5)
    parser.add_argument("--max-comments", type=int, default=100)
    args = parser.parse_args()

    for i, (team1, team2, date, game_num) in enumerate(GAMES):
        print(f"\n{'='*65}")
        print(f"  [{i+1}/{len(GAMES)}] {team1} vs {team2} Game {game_num} | {date}")
        print(f"{'='*65}")

        videos_df, comments_df = collect_pregame_comments(
            team1=team1,
            team2=team2,
            game_num=game_num,
            game_date=date,
            max_videos=args.max_videos,
            max_comments_per_video=args.max_comments,
        )

        print(f"  → {len(videos_df)} videos, {len(comments_df)} comments collected")
        time.sleep(2)  # be polite between games

    print("\nDone. All Conference Finals games scraped.")