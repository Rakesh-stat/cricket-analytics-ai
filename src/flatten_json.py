import json
from pathlib import Path
import pandas as pd

RAW_DIR = Path("data/raw/ipl_json")
OUTPUT_DIR = Path("data/processed")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

delivery_rows = []
match_rows = []

for file_path in RAW_DIR.glob("*.json"):
    with open(file_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    info = data["info"]
    match_id = file_path.stem
    teams = info.get("teams", [])
    winner = info.get("outcome", {}).get("winner")

    teams = info.get("teams", [])

    team1 = teams[0] if len(teams) > 0 else None
    team2 = teams[1] if len(teams) > 1 else None

    losing_team = None

    if winner == team1:
        losing_team = team2
    elif winner == team2:
        losing_team = team1

    match_rows.append({
        "match_id": match_id,
        "date": info.get("dates", [None])[0],
        "event": info.get("event", {}).get("name"),
        "match_type": info.get("match_type"),
        "venue": info.get("venue"),
        "city": info.get("city"),
        "team1": teams[0] if len(teams) > 0 else None,
        "team2": teams[1] if len(teams) > 1 else None,
        "winner": winner,
        "losing_team": losing_team,
        "win_by_runs": info.get("outcome", {}).get("by", {}).get("runs"),
        "win_by_wickets": info.get("outcome", {}).get("by", {}).get("wickets"),
        "toss_winner": info.get("toss", {}).get("winner"),
        "toss_decision": info.get("toss", {}).get("decision"),
        "season": info.get("season"),
        "match_number": info.get("event", {}).get("match_number"),
        "stage": info.get("event", {}).get("stage"),
        "player_of_match": ", ".join(info.get("player_of_match", [])),
    })

    for innings_no, innings in enumerate(data.get("innings", []), start=1):
        batting_team = innings.get("team")

        for over in innings.get("overs", []):
            over_no = over.get("over")

            for ball_no, delivery in enumerate(over.get("deliveries", []), start=1):
                wickets = delivery.get("wickets", [])

                delivery_rows.append({
                    "match_id": match_id,
                    "innings": innings_no,
                    "batting_team": batting_team,
                    "over": over_no,
                    "ball": ball_no,
                    "batter": delivery.get("batter"),
                    "bowler": delivery.get("bowler"),
                    "non_striker": delivery.get("non_striker"),
                    "runs_batter": delivery.get("runs", {}).get("batter", 0),
                    "runs_extras": delivery.get("runs", {}).get("extras", 0),
                    "runs_total": delivery.get("runs", {}).get("total", 0),
                    "extras_type": ",".join(delivery.get("extras", {}).keys()) if "extras" in delivery else None,
                    "is_wicket": len(wickets) > 0,
                    "player_out": wickets[0].get("player_out") if wickets else None,
                    "wicket_kind": wickets[0].get("kind") if wickets else None
                })

matches_df = pd.DataFrame(match_rows)
deliveries_df = pd.DataFrame(delivery_rows)

for col in [
    "match_number",
    "stage",
    "season",
    "player_of_match",
    "winner",
    "toss_winner",
    "toss_decision",
    "event",
    "match_type",
    "venue",
    "city",
    "team1",
    "team2"
]:
    if col in matches_df.columns:
        matches_df[col] = matches_df[col].astype("string")

for col in ["overs", "win_by_runs", "win_by_wickets"]:
    if col in matches_df.columns:
        matches_df[col] = pd.to_numeric(matches_df[col], errors="coerce")


matches_df.to_parquet(OUTPUT_DIR / "matches.parquet", index=False)
deliveries_df.to_parquet(OUTPUT_DIR / "deliveries.parquet", index=False)

print("Done.")
print("Matches:", matches_df.shape)
print("Deliveries:", deliveries_df.shape)