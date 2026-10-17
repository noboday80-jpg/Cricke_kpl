"""Authenticated Streamlit admin tabs for scores, rosters, and player profiles."""

from __future__ import annotations

import hmac
from typing import Any

import streamlit as st
from supabase import Client

from tournament import next_roster_number

PLAYER_PHOTO_BUCKET = "player-photos"
PHOTO_TYPES = ["jpg", "jpeg", "png", "webp"]
PHOTO_MIME_TYPES = {"image/jpeg": "jpg", "image/png": "png", "image/webp": "webp"}
ROLE_CHOICES = ["Player", "Captain", "Vice Captain", "Owner", "Member"]


def normalize_role_name(role: Any) -> str:
    if role is None:
        return "Player"
    text = str(role).strip()
    if not text:
        return "Player"
    mapping = {
        "player": "Player",
        "captain": "Captain",
        "vice captain": "Vice Captain",
        "vice_captain": "Vice Captain",
        "owner": "Owner",
        "member": "Member",
    }
    return mapping.get(text.casefold(), text)


def _upload_player_photo(client: Client, team_id: str, player_id: int | str, uploaded_file: Any) -> str:
    extension = PHOTO_MIME_TYPES.get(str(uploaded_file.type).lower())
    if extension is None:
        raise ValueError("Choose a JPG, PNG, or WebP image.")
    path = f"{team_id}/{player_id}.{extension}"
    client.storage.from_(PLAYER_PHOTO_BUCKET).upload(
        path,
        uploaded_file.getvalue(),
        {"content-type": uploaded_file.type, "upsert": "true"},
    )
    return path


def _delete_photo(client: Client, photo_path: str | None) -> None:
    if photo_path:
        client.storage.from_(PLAYER_PHOTO_BUCKET).remove([photo_path])


def _public_photo_url(client: Client, photo_path: str | None) -> str | None:
    if not photo_path:
        return None
    return str(client.storage.from_(PLAYER_PHOTO_BUCKET).get_public_url(photo_path))


def render_admin(
    client: Client,
    teams: list[dict[str, Any]],
    matches: list[dict[str, Any]],
    players: list[dict[str, Any]],
    batting_scores: list[dict[str, Any]],
    bowling_figures: list[dict[str, Any]],
    password: str,
) -> None:
    st.subheader("Tournament admin")
    if not st.session_state.get("admin_authenticated", False):
        st.caption("Sign in to update shared match scores and team information.")
        with st.form("admin_login"):
            entered_password = st.text_input("Admin password", type="password")
            submitted = st.form_submit_button("Sign in", type="primary")
        if submitted:
            if hmac.compare_digest(entered_password, password):
                st.session_state.admin_authenticated = True
                st.rerun()
            st.error("That password did not match.")
        return

    status_col, signout_col = st.columns([4, 1])
    with status_col:
        st.success("Admin signed in · changes are shared with everyone")
    with signout_col:
        if st.button("Sign out"):
            st.session_state.admin_authenticated = False
            st.rerun()

    teams_by_id = {str(team["id"]): team for team in teams}
    team_names = {team_id: str(team["name"]) for team_id, team in teams_by_id.items()}
    matches_by_id = {str(match["id"]): match for match in matches}
    match_ids = [str(match["id"]) for match in matches]

    def match_label(match_id: str) -> str:
        match = matches_by_id[match_id]
        home = team_names.get(str(match["team1_id"]), "TBC")
        away = team_names.get(str(match["team2_id"]), "TBC")
        return f"Match {match['match_number']} · {home} vs {away}"

    if not match_ids:
        st.warning("No fixtures are loaded. Run database_setup.sql in Supabase first.")
        return

    selected_match_id = st.selectbox(
        "Choose match",
        match_ids,
        format_func=match_label,
        key="admin_fixture_picker",
        help="Select the fixture once, then update it in the task tabs below.",
    )
    match = matches_by_id[selected_match_id]
    home_id, away_id = str(match["team1_id"]), str(match["team2_id"])
    home_name, away_name = team_names[home_id], team_names[away_id]
    match_team_ids = [home_id, away_id]

    match_score_tab, batter_bowler_tab, team_members_tab, player_profiles_tab, reset_data_tab = st.tabs(
        ["Live score entry", "Batter & bowler", "Team members", "Player profiles", "Delete all data"]
    )

    with match_score_tab:
        st.markdown(f"#### {match_label(selected_match_id)}")
        st.caption("Enter the current innings here. Set status to Live and save; the public Live Score tab refreshes automatically.")
        outcome_options = ["Undecided", home_id, away_id, "TIE"]
        outcome_labels = {
            "Undecided": "Not decided",
            home_id: f"{home_name} won",
            away_id: f"{away_name} won",
            "TIE": "Match tied",
        }
        current_outcome = "TIE" if match.get("is_tie") else str(match.get("winner_team_id") or "Undecided")
        if current_outcome not in outcome_options:
            current_outcome = "Undecided"
        batting_options = ["Not set", home_id, away_id]
        current_batting = str(match.get("batting_team_id") or "Not set")
        if current_batting not in batting_options:
            current_batting = "Not set"
        status_options = ["Scheduled", "Live", "Completed"]
        current_status = str(match.get("status") or "Scheduled")
        if current_status not in status_options:
            current_status = "Scheduled"

        with st.form(f"admin_score_form_{selected_match_id}"):
            status = st.selectbox("Match status", status_options, index=status_options.index(current_status))
            batting_team_id = st.selectbox(
                "Currently batting",
                batting_options,
                index=batting_options.index(current_batting),
                format_func=lambda team_id: "Not set" if team_id == "Not set" else team_names[team_id],
                help="Choose the batting side for the Live Score tab.",
            )
            score_left, score_right = st.columns(2)
            with score_left:
                score1 = st.text_input(f"{home_name} total (runs/wickets)", value=str(match.get("team1_score") or ""), placeholder="72/3")
            with score_right:
                score2 = st.text_input(f"{away_name} total (runs/wickets)", value=str(match.get("team2_score") or ""), placeholder="68/5")
            legal_balls = st.number_input(
                "Legal balls completed in current innings",
                min_value=0,
                max_value=int(match.get("overs", 6)) * 6,
                value=int(match.get("balls_completed") or 0),
                help="For a 6-over match, this ranges from 0 to 36. For example, 14 balls means 2.2 overs.",
            )
            outcome = st.selectbox(
                "Result",
                outcome_options,
                index=outcome_options.index(current_outcome),
                format_func=lambda value: outcome_labels[value],
            )
            result_note = st.text_input("Short match note (optional)", value=str(match.get("result_note") or ""), placeholder="Won by 4 runs")
            save_match = st.form_submit_button("Publish score to Live Score", type="primary", width="stretch")

        if save_match:
            if status == "Completed" and outcome == "Undecided":
                st.error("Choose a winner or mark the match tied before setting it to Completed.")
            else:
                update = {
                    "status": status,
                    "team1_score": score1.strip() or None,
                    "team2_score": score2.strip() or None,
                    "batting_team_id": None if batting_team_id == "Not set" else batting_team_id,
                    "balls_completed": int(legal_balls),
                    "winner_team_id": outcome if outcome in (home_id, away_id) else None,
                    "is_tie": outcome == "TIE" and status == "Completed",
                    "result_note": result_note.strip() or None,
                }
                try:
                    client.table("matches").update(update).eq("id", selected_match_id).execute()
                    st.success("Score saved. It will appear in the public Live Score tab.")
                    st.rerun()
                except Exception as error:
                    st.error(f"Could not save the match score: {error}")

    with batter_bowler_tab:
        st.markdown(f"#### Player figures · {match_label(selected_match_id)}")
        st.caption("Select a player, enter their figures, and save. You can return to edit a saved entry later.")
        batter_col, bowler_col = st.columns(2)
        player_map = {str(player["id"]): player for player in players if player.get("id") is not None}

        with batter_col:
            st.markdown("##### Batting")
            batting_team_id = st.selectbox(
                "Batting team",
                match_team_ids,
                format_func=lambda team_id: team_names[team_id],
                key=f"admin_batting_team_{selected_match_id}",
            )
            batters = [player for player in players if str(player["team_id"]) == batting_team_id and player.get("id") is not None]
            existing_batting = [row for row in batting_scores if str(row["match_id"]) == selected_match_id and str(row["team_id"]) == batting_team_id]
            if not batters:
                st.info("No players are listed for this batting team yet.")
            else:
                batter_ids = [str(player["id"]) for player in batters]
                batter_id = st.selectbox(
                    "Batter",
                    batter_ids,
                    format_func=lambda player_id: str(player_map[player_id]["name"]),
                    key=f"admin_batter_{selected_match_id}_{batting_team_id}",
                )
                current_batting = next((row for row in existing_batting if str(row.get("player_id")) == batter_id), {})
                batting_order = int(current_batting.get("batting_order", max((int(row["batting_order"]) for row in existing_batting), default=0) + 1))
                with st.form(f"admin_batting_form_{selected_match_id}_{batting_team_id}"):
                    runs = st.number_input("Runs", min_value=0, value=int(current_batting.get("runs", 0)), step=1)
                    balls_faced = st.number_input("Balls faced", min_value=0, value=int(current_batting.get("balls_faced", 0)), step=1)
                    fours_col, sixes_col = st.columns(2)
                    with fours_col:
                        fours = st.number_input("Fours", min_value=0, value=int(current_batting.get("fours", 0)), step=1)
                    with sixes_col:
                        sixes = st.number_input("Sixes", min_value=0, value=int(current_batting.get("sixes", 0)), step=1)
                    dismissal_options = ["Not out", "Bowled", "Caught", "LBW", "Run out", "Stumped", "Retired hurt", "Other"]
                    old_dismissal = str(current_batting.get("dismissal", "Not out"))
                    dismissal = st.selectbox("Dismissal", dismissal_options, index=dismissal_options.index(old_dismissal) if old_dismissal in dismissal_options else 0)
                    save_batting = st.form_submit_button("💾 Save batting figures", type="primary", width="stretch")
                if save_batting:
                    if fours + sixes > balls_faced or 4 * fours + 6 * sixes > runs:
                        st.error("Check the boundary counts against balls faced and runs scored.")
                    else:
                        record = {
                            "match_id": selected_match_id,
                            "team_id": batting_team_id,
                            "player_id": batter_id,
                            "player_name": player_map[batter_id]["name"],
                            "batting_order": batting_order,
                            "runs": int(runs),
                            "balls_faced": int(balls_faced),
                            "fours": int(fours),
                            "sixes": int(sixes),
                            "dismissal": dismissal,
                        }
                        try:
                            client.table("batting_scores").upsert(record, on_conflict="match_id,team_id,player_id").execute()
                            st.success(f"Saved {player_map[batter_id]['name']}'s batting figures.")
                            st.rerun()
                        except Exception as error:
                            st.error(f"Could not save batting figures: {error}")
                if current_batting:
                    st.markdown("**Delete this batting entry**")
                    if st.button(f"🗑 Delete {player_map[batter_id]['name']} batting", key=f"delete_batting_{selected_match_id}_{batting_team_id}_{batter_id}"):
                        try:
                            client.table("batting_scores").delete().eq("match_id", selected_match_id).eq("team_id", batting_team_id).eq("player_id", batter_id).execute()
                            st.success(f"Deleted {player_map[batter_id]['name']}'s batting entry.")
                            st.rerun()
                        except Exception as error:
                            st.error(f"Could not delete batting entry: {error}")

        with bowler_col:
            st.markdown("##### Bowling")
            bowling_team_id = away_id if batting_team_id == home_id else home_id
            st.caption(f"Bowling team: {team_names[bowling_team_id]}")
            bowlers = [player for player in players if str(player["team_id"]) == bowling_team_id and player.get("id") is not None]
            existing_bowling = [row for row in bowling_figures if str(row["match_id"]) == selected_match_id and str(row["team_id"]) == bowling_team_id]
            if not bowlers:
                st.info("No players are listed for the bowling team yet.")
            else:
                bowler_ids = [str(player["id"]) for player in bowlers]
                bowler_id = st.selectbox(
                    "Bowler",
                    bowler_ids,
                    format_func=lambda player_id: str(player_map[player_id]["name"]),
                    key=f"admin_bowler_{selected_match_id}_{bowling_team_id}",
                )
                current_bowling = next((row for row in existing_bowling if str(row.get("player_id")) == bowler_id), {})
                bowling_order = int(current_bowling.get("bowling_order", max((int(row["bowling_order"]) for row in existing_bowling), default=0) + 1))
                with st.form(f"admin_bowling_form_{selected_match_id}_{bowling_team_id}"):
                    balls_bowled = st.number_input("Legal balls bowled", min_value=0, max_value=36, value=int(current_bowling.get("balls_bowled", 0)), step=1, help="Six legal balls count as one over; 14 balls displays as 2.2 overs.")
                    maidens = st.number_input("Maidens", min_value=0, max_value=6, value=int(current_bowling.get("maidens", 0)), step=1)
                    runs_conceded = st.number_input("Runs conceded", min_value=0, value=int(current_bowling.get("runs_conceded", 0)), step=1)
                    wickets = st.number_input("Wickets", min_value=0, max_value=10, value=int(current_bowling.get("wickets", 0)), step=1)
                    save_bowling = st.form_submit_button("💾 Save bowling figures", type="primary", width="stretch")
                if save_bowling:
                    if maidens > balls_bowled // 6:
                        st.error("Maidens cannot exceed the completed overs bowled.")
                    else:
                        record = {
                            "match_id": selected_match_id,
                            "team_id": bowling_team_id,
                            "player_id": bowler_id,
                            "player_name": player_map[bowler_id]["name"],
                            "bowling_order": bowling_order,
                            "balls_bowled": int(balls_bowled),
                            "maidens": int(maidens),
                            "runs_conceded": int(runs_conceded),
                            "wickets": int(wickets),
                        }
                        try:
                            client.table("bowling_figures").upsert(record, on_conflict="match_id,team_id,player_id").execute()
                            st.success(f"Saved {player_map[bowler_id]['name']}'s bowling figures.")
                            st.rerun()
                        except Exception as error:
                            st.error(f"Could not save bowling figures: {error}")
                if current_bowling:
                    st.markdown("**Delete this bowling entry**")
                    if st.button(f"🗑 Delete {player_map[bowler_id]['name']} bowling", key=f"delete_bowling_{selected_match_id}_{bowling_team_id}_{bowler_id}"):
                        try:
                            client.table("bowling_figures").delete().eq("match_id", selected_match_id).eq("team_id", bowling_team_id).eq("player_id", bowler_id).execute()
                            st.success(f"Deleted {player_map[bowler_id]['name']}'s bowling entry.")
                            st.rerun()
                        except Exception as error:
                            st.error(f"Could not delete bowling entry: {error}")

    with reset_data_tab:
        st.markdown("#### Reset shared tournament data")
        st.warning("This permanently removes all shared score entries, roster records, and match data for the app. This action cannot be undone.")
        st.caption("This only clears the shared tournament data used by the app. It does not remove the fixed team list from the setup file.")
        confirm_delete = st.checkbox("I understand and want to delete all shared app data.", key="confirm_delete_all_app_data")
        if st.button("Delete all tournament data", type="primary", key="delete_all_tournament_data_button"):
            if not confirm_delete:
                st.warning("Check the confirmation box before deleting the shared data.")
            else:
                try:
                    for table_name in ["batting_scores", "bowling_figures", "players", "matches"]:
                        rows = client.table(table_name).select("id").execute().data or []
                        ids = [row["id"] for row in rows if row.get("id") is not None]
                        if ids:
                            client.table(table_name).delete().in_("id", ids).execute()
                    st.success("All shared score and roster data has been cleared.")
                    st.rerun()
                except Exception as error:
                    st.error(f"Could not clear the shared tournament data: {error}")

    with team_members_tab:
        st.caption("Add a player or remove a roster entry.")
        add_column, delete_column = st.columns(2)
        team_ids = [str(team["id"]) for team in teams]
        with add_column:
            st.markdown("#### Add a team member")
            with st.form("add_team_member_form", clear_on_submit=True):
                add_team_id = st.selectbox("Team", team_ids, format_func=lambda team_id: team_names[team_id], key="add_member_team")
                member_name = st.text_input("Player name", max_chars=80)
                member_role = st.selectbox("Role", ROLE_CHOICES)
                jersey_number = st.text_input("Jersey number (optional)", max_chars=12)
                profile_details = st.text_area("Player details (optional)", max_chars=240, placeholder="e.g. Opening batter · Right-arm medium")
                member_photo = st.file_uploader("Player photo (optional)", type=["jpg", "jpeg", "png", "webp"], key="new_member_photo")
                add_member = st.form_submit_button("Add player", type="primary", width="stretch")
            if add_member:
                cleaned_name = member_name.strip()
                if not cleaned_name:
                    st.error("Enter a player name first.")
                else:
                    new_player = {
                        "team_id": add_team_id,
                        "roster_number": next_roster_number(players, add_team_id),
                        "name": cleaned_name,
                        "role": normalize_role_name(member_role),
                        "jersey_number": jersey_number.strip() or None,
                        "profile_details": profile_details.strip() or None,
                    }
                    try:
                        result = client.table("players").insert(new_player).execute()
                        created_player = (result.data or [None])[0]
                        if member_photo and not created_player:
                            created_player = client.table("players").select("id").eq("team_id", add_team_id).eq("roster_number", new_player["roster_number"]).single().execute().data
                        if member_photo and created_player and created_player.get("id") is not None:
                            photo_path = _upload_player_photo(client, add_team_id, created_player["id"], member_photo)
                            client.table("players").update({"photo_path": photo_path}).eq("id", created_player["id"]).execute()
                        st.success(f"Added {cleaned_name} to {team_names[add_team_id]}.")
                        st.rerun()
                    except Exception as error:
                        st.error(f"Could not add player: {error}")

        with delete_column:
            st.markdown("#### Remove a team member")
            players_by_id = {str(player["id"]): player for player in players if player.get("id") is not None}
            if players_by_id:
                player_ids = list(players_by_id)

                def player_label(player_id: str) -> str:
                    player = players_by_id[player_id]
                    return f"{team_names.get(str(player['team_id']), 'Team')} · {player['name']}"

                with st.form("delete_team_member_form"):
                    delete_player_id = st.selectbox("Player", player_ids, format_func=player_label)
                    confirm_delete = st.checkbox("Confirm permanent removal")
                    delete_member = st.form_submit_button("🗑 Remove player", width="stretch")
                if delete_member:
                    if not confirm_delete:
                        st.error("Tick the confirmation box to continue.")
                    else:
                        try:
                            client.table("players").delete().eq("id", delete_player_id).execute()
                            _delete_photo(client, players_by_id[delete_player_id].get("photo_path"))
                            st.success("Player removed from the roster.")
                            st.rerun()
                        except Exception as error:
                            st.error(f"Could not remove player: {error}")
            else:
                st.info("No players in the database yet.")

    with player_profiles_tab:
        editable_players = {str(player["id"]): player for player in players if player.get("id") is not None}
        if not editable_players:
            st.info("Add players in the Team members tab before editing profiles.")
        else:
            def profile_label(player_id: str) -> str:
                player = editable_players[player_id]
                return f"{team_names.get(str(player['team_id']), 'Team')} · {player['name']}"

            profile_id = st.selectbox("Choose player", list(editable_players), format_func=profile_label, key="profile_editor_player")
            player = editable_players[profile_id]
            current_url = _public_photo_url(client, str(player.get("photo_path") or "") or None)
            if current_url:
                st.image(current_url, width=160, caption=f"Current portrait · {player['name']}")
            role_choices = ROLE_CHOICES
            current_role = normalize_role_name(player.get("role"))
            role_index = role_choices.index(current_role) if current_role in role_choices else 0

            with st.form(f"edit_profile_{profile_id}"):
                profile_name = st.text_input("Player name", value=str(player["name"]), max_chars=80)
                profile_role = st.selectbox("Role", role_choices, index=role_index)
                jersey_number = st.text_input("Jersey number", value=str(player.get("jersey_number") or ""), max_chars=12)
                details = st.text_area("Player details", value=str(player.get("profile_details") or ""), max_chars=240)
                photo = st.file_uploader("Upload or replace portrait", type=PHOTO_TYPES, key=f"profile_photo_{profile_id}")
                remove_photo = st.checkbox("Remove current portrait", key=f"remove_photo_{profile_id}")
                save_profile = st.form_submit_button("Save profile", type="primary")

            if save_profile:
                if not profile_name.strip():
                    st.error("Player name cannot be empty.")
                else:
                    old_photo_path = str(player.get("photo_path") or "") or None
                    new_photo_path = old_photo_path
                    try:
                        if photo:
                            new_photo_path = _upload_player_photo(client, str(player["team_id"]), player["id"], photo)
                        elif remove_photo:
                            new_photo_path = None
                        update = {
                            "name": profile_name.strip(),
                            "role": normalize_role_name(profile_role),
                            "jersey_number": jersey_number.strip() or None,
                            "profile_details": details.strip() or None,
                            "photo_path": new_photo_path,
                        }
                        client.table("players").update(update).eq("id", player["id"]).execute()
                        if old_photo_path and old_photo_path != new_photo_path:
                            _delete_photo(client, old_photo_path)
                        st.success("Player profile saved.")
                        st.rerun()
                    except Exception as error:
                        st.error(f"Could not save player profile: {error}")