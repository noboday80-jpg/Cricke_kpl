import unittest
from collections import Counter

from tournament import (
    CONFIRMED_OWNERS,
    DEMO_MATCHES,
    DEMO_PLAYERS,
    DEMO_TEAMS,
    build_standings,
    format_bowling_overs,
    next_roster_number,
    parse_team_score,
)


class TournamentDataTests(unittest.TestCase):
    def test_poster_schedule_has_five_teams_and_ten_fixtures(self) -> None:
        self.assertEqual(len(DEMO_TEAMS), 5)
        self.assertEqual(len(DEMO_MATCHES), 10)
        self.assertEqual(DEMO_MATCHES[0]["start_time"], "08:00")
        self.assertEqual(DEMO_MATCHES[-1]["end_time"], "16:15")

    def test_round_robin_contains_each_pair_once(self) -> None:
        pairings = Counter(
            tuple(sorted((match["team1_id"], match["team2_id"])))
            for match in DEMO_MATCHES
        )
        self.assertEqual(len(pairings), 10)
        self.assertTrue(all(count == 1 for count in pairings.values()))

    def test_all_five_supplied_rosters_are_seeded(self) -> None:
        roster_sizes = Counter(player["team_id"] for player in DEMO_PLAYERS)
        self.assertEqual(roster_sizes["og_power_star"], 12)
        self.assertEqual(roster_sizes["royal_strikes"], 13)
        self.assertEqual(roster_sizes["devara_dragons"], 13)
        self.assertEqual(roster_sizes["varanasi"], 7)
        self.assertEqual(roster_sizes["race_gurram"], 8)

    def test_user_confirmed_team_owners_are_tagged(self) -> None:
        owners = {
            player["team_id"]: player["name"]
            for player in DEMO_PLAYERS
            if player["role"] == "Owner"
        }
        self.assertEqual(owners["varanasi"], "Guru Prasad")
        self.assertEqual(owners["race_gurram"], "Charan")
        self.assertEqual(owners["devara_dragons"], "Rajesh")

    def test_confirmed_owner_fallbacks_are_available(self) -> None:
        self.assertEqual(CONFIRMED_OWNERS["varanasi"], "Guru Prasad")
        self.assertEqual(CONFIRMED_OWNERS["race_gurram"], "Charan")
        self.assertEqual(CONFIRMED_OWNERS["devara_dragons"], "Rajesh")

    def test_next_roster_number_is_scoped_to_team(self) -> None:
        self.assertEqual(next_roster_number(DEMO_PLAYERS, "varanasi"), 8)
        self.assertEqual(next_roster_number(DEMO_PLAYERS, "unknown-team"), 1)

    def test_bowling_overs_use_cricket_ball_notation(self) -> None:
        self.assertEqual(format_bowling_overs(14), "2.2")
        self.assertEqual(format_bowling_overs(36), "6.0")

    def test_parse_team_score_supports_common_formats_and_rejects_bad_values(self) -> None:
        self.assertEqual(parse_team_score("114/3"), (114, 3))
        self.assertEqual(parse_team_score("114-3 (16.2)"), (114, 3))
        self.assertIsNone(parse_team_score("—"))

    def test_points_table_awards_win_and_tie_points(self) -> None:
        matches = [
            {
                "team1_id": "varanasi",
                "team2_id": "og_power_star",
                "status": "Completed",
                "winner_team_id": "varanasi",
                "is_tie": False,
            },
            {
                "team1_id": "race_gurram",
                "team2_id": "royal_strikes",
                "status": "Completed",
                "winner_team_id": None,
                "is_tie": True,
            },
            {
                "team1_id": "devara_dragons",
                "team2_id": "varanasi",
                "status": "Scheduled",
                "winner_team_id": None,
                "is_tie": False,
            },
        ]
        table = {row["team_id"]: row for row in build_standings(DEMO_TEAMS, matches)}
        self.assertEqual(table["varanasi"]["points"], 2)
        self.assertEqual(table["varanasi"]["played"], 1)
        self.assertEqual(table["og_power_star"]["lost"], 1)
        self.assertEqual(table["race_gurram"]["points"], 1)
        self.assertEqual(table["royal_strikes"]["tied"], 1)
        self.assertEqual(table["devara_dragons"]["played"], 0)


if __name__ == "__main__":
    unittest.main()
