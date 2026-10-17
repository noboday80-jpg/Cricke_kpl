"""Tournament seed data and points-table calculation."""

from __future__ import annotations

import re
from typing import Any

TEAM_SEEDS: list[dict[str, Any]] = [
    {"id": "varanasi", "name": "Team Varanasi", "short_name": "TV", "color": "#f47b16", "seed": 1},
    {"id": "og_power_star", "name": "OG Power Star Soldiers", "short_name": "OG", "color": "#1464e8", "seed": 2},
    {"id": "race_gurram", "name": "Team Race Gurram", "short_name": "RG", "color": "#e5282e", "seed": 3},
    {"id": "royal_strikes", "name": "Royal Strikes", "short_name": "RS", "color": "#c69b08", "seed": 4},
    {"id": "devara_dragons", "name": "Devara Dragons", "short_name": "DD", "color": "#079a9a", "seed": 5},
]

PLAYER_SEEDS: list[dict[str, Any]] = [
    {"team_id": "og_power_star", "roster_number": 1, "name": "Santhosh", "role": "Owner"},
    {"team_id": "og_power_star", "roster_number": 2, "name": "Ravi", "role": "Captain"},
    {"team_id": "og_power_star", "roster_number": 3, "name": "Nagarjuna", "role": "Vice Captain"},
    {"team_id": "og_power_star", "roster_number": 4, "name": "Vijay", "role": "Player"},
    {"team_id": "og_power_star", "roster_number": 5, "name": "Suresh", "role": "Player"},
    {"team_id": "og_power_star", "roster_number": 6, "name": "Chandrappa", "role": "Player"},
    {"team_id": "og_power_star", "roster_number": 7, "name": "Manju", "role": "Player"},
    {"team_id": "og_power_star", "roster_number": 8, "name": "Manoj", "role": "Player"},
    {"team_id": "og_power_star", "roster_number": 9, "name": "Raviteja", "role": "Player"},
    {"team_id": "og_power_star", "roster_number": 10, "name": "Gangadhara", "role": "Player"},
    {"team_id": "og_power_star", "roster_number": 11, "name": "Ramesh", "role": "Player"},
    {"team_id": "og_power_star", "roster_number": 12, "name": "Karthik", "role": "Player"},
    {"team_id": "royal_strikes", "roster_number": 1, "name": "Suresh BR", "role": "Owner"},
    {"team_id": "royal_strikes", "roster_number": 2, "name": "Gowtham", "role": "Captain"},
    {"team_id": "royal_strikes", "roster_number": 3, "name": "Gengireddy", "role": "Player"},
    {"team_id": "royal_strikes", "roster_number": 4, "name": "Manikant", "role": "Player"},
    {"team_id": "royal_strikes", "roster_number": 5, "name": "Ganapa", "role": "Player"},
    {"team_id": "royal_strikes", "roster_number": 6, "name": "Ramanji", "role": "Player"},
    {"team_id": "royal_strikes", "roster_number": 7, "name": "Mahendra", "role": "Player"},
    {"team_id": "royal_strikes", "roster_number": 8, "name": "Anji", "role": "Player"},
    {"team_id": "royal_strikes", "roster_number": 9, "name": "Nagesh", "role": "Player"},
    {"team_id": "royal_strikes", "roster_number": 10, "name": "Venugopal", "role": "Player"},
    {"team_id": "royal_strikes", "roster_number": 11, "name": "Prajwal", "role": "Player"},
    {"team_id": "royal_strikes", "roster_number": 12, "name": "Venkataramana", "role": "Player"},
    {"team_id": "royal_strikes", "roster_number": 13, "name": "Shankarnna", "role": "Player"},
    {"team_id": "devara_dragons", "roster_number": 1, "name": "Rajesh", "role": "Owner"},
    {"team_id": "devara_dragons", "roster_number": 2, "name": "Subramani", "role": "Member"},
    {"team_id": "devara_dragons", "roster_number": 3, "name": "Suresh", "role": "Player"},
    {"team_id": "devara_dragons", "roster_number": 4, "name": "Bhagath", "role": "Player"},
    {"team_id": "devara_dragons", "roster_number": 5, "name": "Rajesh K", "role": "Player"},
    {"team_id": "devara_dragons", "roster_number": 6, "name": "Virat Nagesh", "role": "Player", "jersey_number": "18"},
    {"team_id": "devara_dragons", "roster_number": 7, "name": "Niranjan", "role": "Player"},
    {"team_id": "devara_dragons", "roster_number": 8, "name": "Jagan Raj", "role": "Player"},
    {"team_id": "devara_dragons", "roster_number": 9, "name": "Jagadish CPL", "role": "Player"},
    {"team_id": "devara_dragons", "roster_number": 10, "name": "Venkatesh OSU", "role": "Player"},
    {"team_id": "devara_dragons", "roster_number": 11, "name": "Tulasiram", "role": "Player"},
    {"team_id": "devara_dragons", "roster_number": 12, "name": "Mahesh", "role": "Player"},
    {"team_id": "devara_dragons", "roster_number": 13, "name": "Mithun", "role": "Player"},
    {"team_id": "varanasi", "roster_number": 1, "name": "Chandrashekar", "role": "Player"},
    {"team_id": "varanasi", "roster_number": 2, "name": "Madhan", "role": "Player"},
    {"team_id": "varanasi", "roster_number": 3, "name": "Karthik", "role": "Player"},
    {"team_id": "varanasi", "roster_number": 4, "name": "Yugendra", "role": "Player"},
    {"team_id": "varanasi", "roster_number": 5, "name": "Ashok", "role": "Player"},
    {"team_id": "varanasi", "roster_number": 6, "name": "Gurumurthy", "role": "Player"},
    {"team_id": "varanasi", "roster_number": 7, "name": "Guru Prasad", "role": "Owner"},
    {"team_id": "race_gurram", "roster_number": 1, "name": "Yuvaraj", "role": "Player"},
    {"team_id": "race_gurram", "roster_number": 2, "name": "Pradeep", "role": "Player"},
    {"team_id": "race_gurram", "roster_number": 3, "name": "Prashanth", "role": "Player"},
    {"team_id": "race_gurram", "roster_number": 4, "name": "Bharath", "role": "Player"},
    {"team_id": "race_gurram", "roster_number": 5, "name": "Gangaraju", "role": "Player"},
    {"team_id": "race_gurram", "roster_number": 6, "name": "Varadaraju", "role": "Player"},
    {"team_id": "race_gurram", "roster_number": 7, "name": "Manoj", "role": "Player"},
    {"team_id": "race_gurram", "roster_number": 8, "name": "Charan", "role": "Owner"},
]

DEMO_PLAYERS = PLAYER_SEEDS

CONFIRMED_OWNERS: dict[str, str] = {
    "varanasi": "Guru Prasad",
    "og_power_star": "Santhosh",
    "race_gurram": "Charan",
    "royal_strikes": "Suresh BR",
    "devara_dragons": "Rajesh",
}

SCHEDULE_SEEDS: list[dict[str, Any]] = [
    {"match_number": 1, "team1_id": "varanasi", "team2_id": "og_power_star", "start_time": "08:00", "end_time": "08:45"},
    {"match_number": 2, "team1_id": "race_gurram", "team2_id": "royal_strikes", "start_time": "08:50", "end_time": "09:35"},
    {"match_number": 3, "team1_id": "devara_dragons", "team2_id": "varanasi", "start_time": "09:40", "end_time": "10:25"},
    {"match_number": 4, "team1_id": "og_power_star", "team2_id": "race_gurram", "start_time": "10:30", "end_time": "11:15"},
    {"match_number": 5, "team1_id": "royal_strikes", "team2_id": "devara_dragons", "start_time": "11:20", "end_time": "12:05"},
    {"match_number": 6, "team1_id": "varanasi", "team2_id": "royal_strikes", "start_time": "12:10", "end_time": "12:55"},
    {"match_number": 7, "team1_id": "og_power_star", "team2_id": "devara_dragons", "start_time": "13:00", "end_time": "13:45"},
    {"match_number": 8, "team1_id": "race_gurram", "team2_id": "varanasi", "start_time": "13:50", "end_time": "14:35"},
    {"match_number": 9, "team1_id": "royal_strikes", "team2_id": "og_power_star", "start_time": "14:40", "end_time": "15:25"},
    {"match_number": 10, "team1_id": "devara_dragons", "team2_id": "race_gurram", "start_time": "15:30", "end_time": "16:15"},
]

DEMO_TEAMS = TEAM_SEEDS
DEMO_MATCHES: list[dict[str, Any]] = [
    {
        "id": f"demo-{row['match_number']}",
        **row,
        "team2_id": row["team2_id"],
        "overs": 6,
        "status": "Scheduled",
        "team1_score": "",
        "team2_score": "",
        "winner_team_id": None,
        "is_tie": False,
        "result_note": "",
    }
    for row in SCHEDULE_SEEDS
]


def next_roster_number(players: list[dict[str, Any]], team_id: str) -> int:
    """Return the next display number for a team's roster."""
    existing_numbers = [
        int(player.get("roster_number", 0))
        for player in players
        if str(player.get("team_id")) == team_id
    ]
    return max(existing_numbers, default=0) + 1


def format_bowling_overs(balls_bowled: int) -> str:
    """Format legal balls using cricket notation, where the digit is balls, not a decimal fraction."""
    return f"{balls_bowled // 6}.{balls_bowled % 6}"


def parse_team_score(score: Any) -> tuple[int, int] | None:
    """Parse a score like 114/3 or 114-3 without guessing malformed values."""
    if score is None:
        return None
    match = re.match(r"^\s*(\d+)\s*[/\-–]\s*(\d+)\b", str(score))
    if not match:
        return None
    return int(match.group(1)), int(match.group(2))


def build_standings(teams: list[dict[str, Any]], matches: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Return a points table using two points for a win and one for a tie."""
    rows: dict[str, dict[str, Any]] = {
        str(team["id"]): {
            "team_id": str(team["id"]),
            "team": str(team["name"]),
            "played": 0,
            "won": 0,
            "tied": 0,
            "lost": 0,
            "points": 0,
            "seed": int(team.get("seed", 99)),
        }
        for team in teams
    }

    for match in matches:
        if match.get("status") != "Completed":
            continue
        home_id = str(match.get("team1_id", ""))
        away_id = str(match.get("team2_id", ""))
        if home_id not in rows or away_id not in rows:
            continue
        home, away = rows[home_id], rows[away_id]
        home["played"] += 1
        away["played"] += 1
        winner_id = match.get("winner_team_id")
        if winner_id == home_id:
            home["won"] += 1
            home["points"] += 2
            away["lost"] += 1
        elif winner_id == away_id:
            away["won"] += 1
            away["points"] += 2
            home["lost"] += 1
        elif match.get("is_tie"):
            home["tied"] += 1
            away["tied"] += 1
            home["points"] += 1
            away["points"] += 1
        else:
            home["lost"] += 1
            away["lost"] += 1

    return sorted(rows.values(), key=lambda row: (-row["points"], -row["won"], row["seed"]))
