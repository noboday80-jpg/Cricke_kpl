from __future__ import annotations

import base64
import html
import hmac
from datetime import datetime
from pathlib import Path
from typing import Any

import pandas as pd
import streamlit as st
from supabase import Client, create_client
from admin_ui import render_admin as render_admin_workspace

from tournament import (
    DEMO_MATCHES,
    DEMO_PLAYERS,
    DEMO_TEAMS,
    build_standings,
    format_bowling_overs,
    next_roster_number,
    parse_team_score,
)

st.set_page_config(page_title="KPL Season 2 · Tournament Central", page_icon="🏏", layout="wide")

ASSET_DIR = Path(__file__).resolve().parent / "assets"
PLAYER_PHOTO_BUCKET = "player-photos"
ROLE_CHOICES = ["Player", "Captain", "Vice Captain", "Owner", "Member"]


def normalize_role_name(role: Any) -> str:
    """Return a canonical role label for stored roster values."""
    if role is None:
        return "Player"
    text = str(role).strip()
    if not text:
        return "Player"
    normalized = text.casefold()
    role_map = {
        "captain": "Captain",
        "vice captain": "Vice Captain",
        "vice_captain": "Vice Captain",
        "owner": "Owner",
        "member": "Member",
        "player": "Player",
    }
    return role_map.get(normalized, text)


def find_image_asset(category: str, name: str) -> Path | None:
    """Find a supported local image file for a logo or cricket illustration."""
    for extension in (".png", ".webp", ".jpg", ".jpeg", ".svg"):
        candidate = ASSET_DIR / category / f"{name}{extension}"
        if candidate.is_file():
            return candidate
    return None


def image_data_uri(image_path: Path) -> str:
    """Encode a local image for inline display in the Streamlit page."""
    mime_types = {
        ".png": "image/png",
        ".webp": "image/webp",
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".svg": "image/svg+xml",
    }
    encoded_image = base64.b64encode(image_path.read_bytes()).decode("ascii")
    return f"data:{mime_types[image_path.suffix.lower()]};base64,{encoded_image}"


def team_logo_markup(team: dict[str, Any], size: int) -> str:
    """Render the team's local logo, or an initials fallback."""
    team_id = str(team["id"])
    image_path = find_image_asset("team_logos", team_id)
    team_name = html.escape(str(team["name"]))
    if image_path:
        return (
            f'<img class="team-logo-image" src="{image_data_uri(image_path)}" '
            f'alt="{team_name} logo" width="{size}" height="{size}">'
        )
    short_name = html.escape(str(team.get("short_name", "KPL")))
    color = html.escape(str(team.get("color", "#d9ad34")))
    return (
        f'<span class="team-logo-fallback" role="img" aria-label="{team_name} logo" '
        f'style="width:{size}px;height:{size}px;--logo-color:{color}">{short_name}</span>'
    )


def save_player_photo(
    client: Client,
    team_id: str,
    player_id: int | str,
    uploaded_file: Any,
) -> str:
    """Upload/replace a player portrait in the public-read storage bucket."""
    extension_by_type = {
        "image/jpeg": "jpg",
        "image/png": "png",
        "image/webp": "webp",
    }
    extension = extension_by_type.get(str(uploaded_file.type).lower())
    if extension is None:
        raise ValueError("Choose a JPG, PNG, or WebP image.")
    new_path = f"{team_id}/{player_id}.{extension}"
    client.storage.from_(PLAYER_PHOTO_BUCKET).upload(
        new_path,
        uploaded_file.getvalue(),
        {"content-type": uploaded_file.type, "upsert": "true"},
    )
    return new_path


def delete_player_photo(client: Client, photo_path: str | None) -> None:
    """Remove a stored portrait if a player currently has one."""
    if photo_path:
        client.storage.from_(PLAYER_PHOTO_BUCKET).remove([photo_path])


def player_photo_url(client: Client, photo_path: str | None) -> str | None:
    """Return a public URL for a stored player portrait."""
    if not photo_path:
        return None
    return str(client.storage.from_(PLAYER_PHOTO_BUCKET).get_public_url(photo_path))

st.markdown(
    """
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Barlow+Condensed:wght@500;600;700;800;900&family=DM+Sans:wght@400;500;600;700&display=swap');
    :root { --kpl-yellow:#ffd900; --kpl-ink:#07101b; --kpl-panel:#101d2b; }
    .stApp { background: radial-gradient(ellipse at 80% 0%, #142943 0, #07101b 48%); color:#f4f6fa; }
    [data-testid="stHeader"] { background:transparent; }
    [data-testid="stSidebar"] { background:#0b1522; border-right:1px solid #223043; }
    h1,h2,h3 { font-family:'Barlow Condensed',Impact,sans-serif !important; text-transform:uppercase; letter-spacing:.04em; }
    h1 { color:var(--kpl-yellow) !important; font-size:clamp(2.4rem,6vw,4.8rem) !important; line-height:.92 !important; }
    h2 { color:#fff !important; }
    p, label, [data-testid="stMarkdownContainer"] { font-family:'DM Sans',Arial,sans-serif; }
    .hero { border:1px solid #354253; border-radius:20px; padding:clamp(22px,4vw,42px); margin:8px 0 24px;
      background:linear-gradient(110deg,#101c2bcc,#101c2b55), radial-gradient(ellipse at 86% 80%,#194c55 0,#101d2b 42%,#0a1320 76%);
      box-shadow:0 20px 60px #0005; position:relative; overflow:hidden; }
    .hero:after { content:'🏏'; position:absolute; right:5%; bottom:-26px; font-size:clamp(100px,20vw,190px); opacity:.12; transform:rotate(-24deg); }
    .hero-with-image:after { content:none; }
    .eyebrow { color:#bdc7d3; font-size:.76rem; font-weight:700; letter-spacing:.2em; }
    .hero-tag { display:inline-block; color:#06101c; background:var(--kpl-yellow); padding:5px 10px; border-radius:4px; font-weight:900; letter-spacing:.12em; font-size:.72rem; }
    .hero-content { display:flex; align-items:center; gap:20px; position:relative; z-index:1; }
    .hero-copy { max-width:680px; position:relative; z-index:1; flex:1; }
    .hero-copy p { color:#c8d0d9; max-width:560px; line-height:1.6; }
    .hero-brand { flex:0 0 38%; padding:10px; border:1px solid #d8ae4540; border-radius:14px; background:#07101bc9; box-shadow:0 12px 40px #0005; }
    .hero-brand img { display:block; width:100%; height:auto; }
    .team-chip { display:inline-flex; align-items:center; gap:8px; padding:6px 10px 6px 6px; border:1px solid #ffffff2c; border-radius:999px; margin:4px 5px 4px 0; font-size:.78rem; background:#0b1522; }
    .team-logo-image { display:block; object-fit:contain; filter:drop-shadow(0 3px 6px #0006); }
    .team-chip .team-logo-image,.team-chip .team-logo-fallback { width:30px !important; height:30px !important; border-radius:50%; }
    .team-logo-fallback { display:inline-flex; align-items:center; justify-content:center; flex:0 0 auto; border:2px solid var(--logo-color); border-radius:50%; background:#101a27; color:#fff0b0; font-size:.72rem; font-weight:900; }
    .team-logo-frame { display:flex; justify-content:center; margin:2px auto 12px; }
    .rule-card { background:linear-gradient(135deg,#101d2b,#0b1522); border:1px solid #263649; padding:16px 18px; border-radius:12px; min-height:95px; }
    .rule-card b { color:var(--kpl-yellow); display:block; font-size:.76rem; letter-spacing:.12em; margin-bottom:7px; }
    .rule-card span { color:#d1d8df; font-size:.88rem; }
    [data-testid="stMetric"] { background:#0d1927; border:1px solid #263649; padding:14px 16px; border-radius:12px; }
    [data-testid="stMetricLabel"] { color:#aab5c2 !important; }
    [data-testid="stMetricValue"] { color:#fff !important; font-family:'Barlow Condensed',Impact,sans-serif; }
    div[data-testid="stTabs"] button { color:#c5ced8; }
    div[data-testid="stTabs"] button[aria-selected="true"] { color:var(--kpl-yellow); }
    .stButton button[kind="primary"] { background:#147a52; color:#fff !important; border:1px solid #54c894; font-weight:800; box-shadow:0 3px 12px #0005; }
    .stButton button[kind="primary"]:hover { background:#199765; color:#fff !important; border-color:#8ae2b8; }
    .stButton button[kind="primary"]:focus-visible { outline:3px solid #f2cf4a; outline-offset:2px; }
    .small-muted { color:#9eabba; font-size:.84rem; }
    .poster-note { border-left:3px solid var(--kpl-yellow); padding:8px 12px; color:#c7d0dc; background:#101d2b; }
    .live-score-panel { background:linear-gradient(135deg,#122235,#0a1421); border:1px solid #30445a; border-radius:16px; padding:20px 22px; margin:12px 0 18px; box-shadow:0 14px 35px #0004; }
    .live-score-top { display:flex; align-items:center; justify-content:space-between; color:#aab8c8; font-size:.8rem; }
    .live-pill { background:#8d241f; border:1px solid #ff7266; color:#fff; font-size:.68rem; font-weight:900; letter-spacing:.14em; padding:5px 9px; border-radius:999px; }
    .score-team { color:#aeb9c6; font-size:.78rem; letter-spacing:.06em; }
    .score-large { color:#fff; font-family:'Barlow Condensed',Impact,sans-serif; font-size:clamp(2rem,5vw,3.5rem); font-weight:800; line-height:1.05; margin:5px 0; }
    .score-overs { color:#aeb9c6; font-size:.82rem; }
    .live-summary { color:#c7d1dc; border-top:1px solid #ffffff20; margin-top:15px; padding-top:12px; font-size:.88rem; }
    .player-profile { background:linear-gradient(145deg,#122235,#0b1522); border:1px solid #2b3e51; border-radius:14px; padding:14px; min-height:265px; margin:5px 0 12px; }
    .player-profile img { width:100%; height:150px; object-fit:cover; border-radius:9px; background:#08111c; }
    .player-profile-placeholder { height:150px; display:flex; align-items:center; justify-content:center; border-radius:9px; background:#08111c; color:#efcf55; font-size:3.2rem; }
    .player-profile-name { color:#fff; font-size:1rem; font-weight:800; margin-top:10px; }
    .player-profile-meta { color:#b6c2ce; font-size:.78rem; margin-top:4px; }
    .player-profile-details { color:#d0d9e2; font-size:.8rem; line-height:1.5; margin-top:7px; }
    footer { visibility:hidden; }
    </style>
    """,
    unsafe_allow_html=True,
)


def get_settings() -> tuple[str, str, str] | None:
    try:
        supabase_settings = st.secrets["supabase"]
        auth_settings = st.secrets["auth"]
        return (
            str(supabase_settings["url"]).strip(),
            str(supabase_settings["service_role_key"]).strip(),
            str(auth_settings["admin_password"]),
        )
    except Exception:
        return None


def load_tournament(
    client: Client,
) -> tuple[
    list[dict[str, Any]],
    list[dict[str, Any]],
    list[dict[str, Any]],
    list[dict[str, Any]],
    list[dict[str, Any]],
]:
    teams = client.table("teams").select("*").order("seed").execute().data or []
    matches = client.table("matches").select("*").order("match_number").execute().data or []
    players = client.table("players").select("*").order("team_id").order("roster_number").execute().data or []
    batting_scores = client.table("batting_scores").select("*").order("match_id").order("team_id").order("batting_order").execute().data or []
    bowling_figures = client.table("bowling_figures").select("*").order("match_id").order("team_id").order("bowling_order").execute().data or []
    if not teams or not matches:
        raise RuntimeError("Database is empty. Run the latest database_setup.sql in your Supabase SQL Editor first.")
    return teams, matches, players, batting_scores, bowling_figures


def format_time(value: Any) -> str:
    if not value:
        return "—"
    try:
        return datetime.strptime(str(value)[:5], "%H:%M").strftime("%I:%M %p").lstrip("0")
    except ValueError:
        return str(value)


def build_schedule_frame(teams: list[dict[str, Any]], matches: list[dict[str, Any]]) -> pd.DataFrame:
    team_map = {str(team["id"]): team["name"] for team in teams}
    rows = []
    for match in matches:
        rows.append(
            {
                "S.No": match["match_number"],
                "Match": f"Match {match['match_number']}",
                "Team 1": team_map.get(str(match["team1_id"]), "TBC"),
                "VS": "VS",
                "Team 2": team_map.get(str(match["team2_id"]), "TBC"),
                "Start": format_time(match.get("start_time")),
                "End": format_time(match.get("end_time")),
                "Overs": f"{match.get('overs', 6)} overs",
                "Status": match.get("status", "Scheduled"),
                "Score": f"{match.get('team1_score') or '—'}  ·  {match.get('team2_score') or '—'}",
            }
        )
    return pd.DataFrame(rows)


def render_scorecard(
    match: dict[str, Any],
    teams: list[dict[str, Any]],
    batting_scores: list[dict[str, Any]],
    bowling_figures: list[dict[str, Any]],
) -> None:
    """Render batter and bowler tables for one fixture."""
    match_id = str(match["id"])
    team_map = {str(team["id"]): team for team in teams}
    participating_teams = [str(match["team1_id"]), str(match["team2_id"])]
    st.markdown(
        f"#### Match {match['match_number']} · {team_map[participating_teams[0]]['name']} vs {team_map[participating_teams[1]]['name']}"
    )
    st.caption(
        f"{team_map[participating_teams[0]]['name']} {match.get('team1_score') or '—'}  ·  "
        f"{team_map[participating_teams[1]]['name']} {match.get('team2_score') or '—'}"
    )

    match_batting = [row for row in batting_scores if str(row["match_id"]) == match_id]
    match_bowling = [row for row in bowling_figures if str(row["match_id"]) == match_id]
    if not match_batting and not match_bowling:
        st.info("No individual batter or bowler details have been entered for this match yet.")
        return

    st.markdown("### Batting")
    batting_columns = st.columns(2)
    for team_id, column in zip(participating_teams, batting_columns):
        rows = sorted(
            (row for row in match_batting if str(row["team_id"]) == team_id),
            key=lambda row: int(row["batting_order"]),
        )
        with column:
            st.markdown(f"**{team_map[team_id]['name']}**")
            if rows:
                table_rows = [
                    {
                        "Batter": row["player_name"],
                        "Dismissal": row.get("dismissal") or "Not out",
                        "R": row["runs"],
                        "B": row["balls_faced"],
                        "4s": row["fours"],
                        "6s": row["sixes"],
                        "SR": round(int(row["runs"]) * 100 / int(row["balls_faced"]), 2) if int(row["balls_faced"]) else 0.0,
                    }
                    for row in rows
                ]
                st.dataframe(pd.DataFrame(table_rows), hide_index=True, width="stretch")
            else:
                st.caption("No batting entries yet.")

    st.markdown("### Bowling")
    bowling_columns = st.columns(2)
    for team_id, column in zip(participating_teams, bowling_columns):
        rows = sorted(
            (row for row in match_bowling if str(row["team_id"]) == team_id),
            key=lambda row: int(row["bowling_order"]),
        )
        with column:
            st.markdown(f"**{team_map[team_id]['name']}**")
            if rows:
                table_rows = [
                    {
                        "Bowler": row["player_name"],
                        "O": format_bowling_overs(int(row["balls_bowled"])),
                        "M": row["maidens"],
                        "R": row["runs_conceded"],
                        "W": row["wickets"],
                        "Econ": round(int(row["runs_conceded"]) * 6 / int(row["balls_bowled"]), 2) if int(row["balls_bowled"]) else 0.0,
                    }
                    for row in rows
                ]
                st.dataframe(pd.DataFrame(table_rows), hide_index=True, width="stretch")
            else:
                st.caption("No bowling entries yet.")


def render_live_score(
    match: dict[str, Any],
    teams: list[dict[str, Any]],
    batting_scores: list[dict[str, Any]],
    bowling_figures: list[dict[str, Any]],
) -> None:
    """Render the entered match score and player figures in a compact live-score layout."""
    team_map = {str(team["id"]): team for team in teams}
    team1_id = str(match["team1_id"])
    team2_id = str(match["team2_id"])
    innings_scores = {
        team1_id: match.get("team1_score"),
        team2_id: match.get("team2_score"),
    }
    batting_team_id = str(match.get("batting_team_id") or "")
    balls_completed = int(match.get("balls_completed") or 0)
    current_score = parse_team_score(innings_scores.get(batting_team_id)) if batting_team_id in team_map else None
    status = str(match.get("status", "Scheduled"))
    status_label = "LIVE NOW" if status == "Live" else status.upper()

    st.markdown(
        f'<div class="live-score-panel"><div class="live-score-top">'
        f'<span>KPL · MATCH {match["match_number"]} · {format_time(match.get("start_time"))}</span>'
        f'<span class="live-pill">{html.escape(status_label)}</span></div></div>',
        unsafe_allow_html=True,
    )
    team1_col, team2_col = st.columns(2)
    for team_id, column in ((team1_id, team1_col), (team2_id, team2_col)):
        parsed_score = parse_team_score(innings_scores.get(team_id))
        display_score = innings_scores.get(team_id) or "Yet to bat"
        overs_label = (
            f"{format_bowling_overs(balls_completed)} overs"
            if team_id == batting_team_id
            else "Innings score" if innings_scores.get(team_id) else "Awaiting innings"
        )
        with column:
            st.markdown(
                f'<div class="live-score-panel"><div class="score-team">{html.escape(team_map[team_id]["name"].upper())}</div>'
                f'<div class="score-large">{html.escape(str(display_score))}</div>'
                f'<div class="score-overs">{html.escape(overs_label)}</div></div>',
                unsafe_allow_html=True,
            )
            if team_id == batting_team_id and parsed_score and balls_completed > 0:
                current_rate = parsed_score[0] * 6 / balls_completed
                st.metric("CURRENT RUN RATE", f"{current_rate:.2f}")

    if status == "Live":
        if batting_team_id in team_map and current_score is not None:
            other_team_id = team2_id if batting_team_id == team1_id else team1_id
            other_score = parse_team_score(innings_scores.get(other_team_id))
            if other_score:
                target = other_score[0] + 1
                remaining_balls = max(int(match.get("overs", 6)) * 6 - balls_completed, 0)
                runs_needed = max(target - current_score[0], 0)
                if remaining_balls:
                    required_rate = runs_needed * 6 / remaining_balls
                    summary = f"{team_map[batting_team_id]['name']} need {runs_needed} runs from {remaining_balls} balls · Required rate {required_rate:.2f}"
                else:
                    summary = f"Target {target} · Innings overs completed"
            else:
                run_rate = current_score[0] * 6 / balls_completed if balls_completed else 0
                summary = f"{team_map[batting_team_id]['name']} batting · CRR {run_rate:.2f}"
            st.markdown(f'<div class="live-summary">{html.escape(summary)}</div>', unsafe_allow_html=True)
        else:
            st.info("Set the batting team and entered score in the Admin tab to show the current innings summary.")

    st.caption("Score updates are shown from the latest admin entry. Ball-by-ball commentary is not recorded by this scorekeeper.")
    render_scorecard(match, teams, batting_scores, bowling_figures)


def _legacy_render_admin(
    client: Client,
    teams: list[dict[str, Any]],
    matches: list[dict[str, Any]],
    players: list[dict[str, Any]],
    batting_scores: list[dict[str, Any]],
    bowling_figures: list[dict[str, Any]],
    password: str,
) -> None:
    st.subheader("Scorekeeper desk")
    if not st.session_state.get("admin_authenticated", False):
        st.caption("Sign in with the tournament admin password to publish scores to the shared database.")
        with st.form("admin_login"):
            entered_password = st.text_input("Admin password", type="password")
            submitted = st.form_submit_button("Sign in", type="primary")
        if submitted:
            if hmac.compare_digest(entered_password, password):
                st.session_state.admin_authenticated = True
                st.rerun()
            st.error("That password did not match.")
        return

    left, right = st.columns([4, 1])
    with left:
        st.success("Admin session active · updates are visible to everyone using this app")
    with right:
        if st.button("Sign out"):
            st.session_state.admin_authenticated = False
            st.rerun()

    team_map = {str(team["id"]): team for team in teams}
    match_ids = [str(match["id"]) for match in matches]
    matches_by_id = {str(match["id"]): match for match in matches}

    def match_label(match_id: str) -> str:
        match = matches_by_id[match_id]
        home = team_map.get(str(match["team1_id"]), {}).get("name", "TBC")
        away = team_map.get(str(match["team2_id"]), {}).get("name", "TBC")
        return f"Match {match['match_number']} · {home} vs {away}"

    selected_id = st.selectbox("Choose a fixture", match_ids, format_func=match_label, key="admin_match_choice")
    selected = matches_by_id[selected_id]
    home_name = team_map[str(selected["team1_id"])]["name"]
    away_name = team_map[str(selected["team2_id"])]["name"]
    outcome_options = ["Undecided", str(selected["team1_id"]), str(selected["team2_id"]), "TIE"]
    outcome_labels = {"Undecided": "Not decided", str(selected["team1_id"]): f"{home_name} won", str(selected["team2_id"]): f"{away_name} won", "TIE": "Match tied"}
    current_outcome = "TIE" if selected.get("is_tie") else str(selected.get("winner_team_id") or "Undecided")
    if current_outcome not in outcome_options:
        current_outcome = "Undecided"
    current_batting_team_id = str(selected.get("batting_team_id") or "Not set")
    batting_team_options = ["Not set", str(selected["team1_id"]), str(selected["team2_id"])]
    if current_batting_team_id not in batting_team_options:
        current_batting_team_id = "Not set"

    with st.form(f"score_form_{selected_id}"):
        status = st.selectbox("Status", ["Scheduled", "Live", "Completed"], index=["Scheduled", "Live", "Completed"].index(selected.get("status", "Scheduled")))
        batting_team_id = st.selectbox(
            "Currently batting",
            batting_team_options,
            index=batting_team_options.index(current_batting_team_id),
            format_func=lambda team_id: "Not set" if team_id == "Not set" else team_map[team_id]["name"],
            help="Set this during a live match so the Live Score tab can identify the current innings.",
        )
        balls_completed = st.number_input(
            "Legal balls completed in current innings",
            min_value=0,
            max_value=int(selected.get("overs", 6)) * 6,
            value=int(selected.get("balls_completed") or 0),
            step=1,
        )
        score1_col, score2_col = st.columns(2)
        with score1_col:
            score1 = st.text_input(f"{home_name} score", value=selected.get("team1_score") or "", placeholder="e.g. 72/3")
        with score2_col:
            score2 = st.text_input(f"{away_name} score", value=selected.get("team2_score") or "", placeholder="e.g. 68/5")
        outcome = st.selectbox("Result", outcome_options, index=outcome_options.index(current_outcome), format_func=lambda value: outcome_labels[value])
        result_note = st.text_input("Scorebook note (optional)", value=selected.get("result_note") or "", placeholder="e.g. Varanasi won by 4 runs")
        saved = st.form_submit_button("Save shared result", type="primary", width="stretch")

    if saved:
        if status == "Completed" and outcome == "Undecided":
            st.error("Choose the winner or mark the game tied before completing it.")
            return
        winner_id = outcome if outcome in (str(selected["team1_id"]), str(selected["team2_id"])) else None
        update = {
            "status": status,
            "team1_score": score1.strip() or None,
            "team2_score": score2.strip() or None,
            "batting_team_id": None if batting_team_id == "Not set" else batting_team_id,
            "balls_completed": int(balls_completed),
            "winner_team_id": winner_id,
            "is_tie": outcome == "TIE" and status == "Completed",
            "result_note": result_note.strip() or None,
        }
        try:
            client.table("matches").update(update).eq("id", selected_id).execute()
            st.success("Score saved to the shared tournament database.")
            st.rerun()
        except Exception as error:
            st.error(f"Could not save the score: {error}")

    st.divider()
    st.subheader("Batter and bowler scorecard")
    st.caption("Enter one player at a time. Existing entries can be selected again and updated.")
    match_team_ids = [str(selected["team1_id"]), str(selected["team2_id"])]
    players_by_id = {str(player["id"]): player for player in players if player.get("id") is not None}

    batting_team_id = st.selectbox(
        "Batting team",
        match_team_ids,
        format_func=lambda team_id: team_map[team_id]["name"],
        key=f"batting_team_{selected_id}",
    )
    batters = [
        player for player in players
        if str(player["team_id"]) == batting_team_id and player.get("id") is not None
    ]
    existing_batting = [
        row for row in batting_scores
        if str(row["match_id"]) == selected_id and str(row["team_id"]) == batting_team_id
    ]
    if batters:
        batter_ids = [str(player["id"]) for player in batters]

        def batter_label(player_id: str) -> str:
            return players_by_id[player_id]["name"]

        batter_id = st.selectbox(
            "Batter",
            batter_ids,
            format_func=batter_label,
            key=f"batter_{selected_id}_{batting_team_id}",
        )
        current_batting = next((row for row in existing_batting if str(row.get("player_id")) == batter_id), {})
        batting_order = int(current_batting.get("batting_order", max((int(row["batting_order"]) for row in existing_batting), default=0) + 1))
        with st.form(f"batting_score_form_{selected_id}_{batting_team_id}"):
            batting_col1, batting_col2, batting_col3 = st.columns(3)
            with batting_col1:
                batter_runs = st.number_input("Runs", min_value=0, value=int(current_batting.get("runs", 0)), step=1)
            with batting_col2:
                balls_faced = st.number_input("Balls faced", min_value=0, value=int(current_batting.get("balls_faced", 0)), step=1)
            with batting_col3:
                dismissal_options = ["Not out", "Bowled", "Caught", "LBW", "Run out", "Stumped", "Retired hurt", "Other"]
                old_dismissal = str(current_batting.get("dismissal", "Not out"))
                dismissal_index = dismissal_options.index(old_dismissal) if old_dismissal in dismissal_options else 0
                dismissal = st.selectbox("Dismissal", dismissal_options, index=dismissal_index)
            boundary_col1, boundary_col2 = st.columns(2)
            with boundary_col1:
                fours = st.number_input("Fours", min_value=0, value=int(current_batting.get("fours", 0)), step=1)
            with boundary_col2:
                sixes = st.number_input("Sixes", min_value=0, value=int(current_batting.get("sixes", 0)), step=1)
            save_batting = st.form_submit_button("Save batter score", type="primary")

        if save_batting:
            if fours + sixes > balls_faced or 4 * fours + 6 * sixes > batter_runs:
                st.error("Boundary counts must fit within the batter's runs and balls faced.")
            else:
                batting_record = {
                    "match_id": selected_id,
                    "team_id": batting_team_id,
                    "player_id": batter_id,
                    "player_name": players_by_id[batter_id]["name"],
                    "batting_order": batting_order,
                    "runs": int(batter_runs),
                    "balls_faced": int(balls_faced),
                    "fours": int(fours),
                    "sixes": int(sixes),
                    "dismissal": dismissal,
                }
                try:
                    client.table("batting_scores").upsert(
                        batting_record,
                        on_conflict="match_id,team_id,player_id",
                    ).execute()
                    st.success(f"Saved {players_by_id[batter_id]['name']}'s batting score.")
                    st.rerun()
                except Exception as error:
                    st.error(f"Could not save the batter score: {error}")
    else:
        st.info("Add this team's players to the roster before entering batter scores.")

    bowling_team_ids = [team_id for team_id in match_team_ids if team_id != batting_team_id]
    bowling_team_id = bowling_team_ids[0]
    bowlers = [
        player for player in players
        if str(player["team_id"]) == bowling_team_id and player.get("id") is not None
    ]
    existing_bowling = [
        row for row in bowling_figures
        if str(row["match_id"]) == selected_id and str(row["team_id"]) == bowling_team_id
    ]
    if bowlers:
        bowler_ids = [str(player["id"]) for player in bowlers]

        def bowler_label(player_id: str) -> str:
            return players_by_id[player_id]["name"]

        bowler_id = st.selectbox(
            "Bowler",
            bowler_ids,
            format_func=bowler_label,
            key=f"bowler_{selected_id}_{bowling_team_id}",
        )
        current_bowling = next((row for row in existing_bowling if str(row.get("player_id")) == bowler_id), {})
        bowling_order = int(current_bowling.get("bowling_order", max((int(row["bowling_order"]) for row in existing_bowling), default=0) + 1))
        with st.form(f"bowling_figure_form_{selected_id}_{bowling_team_id}"):
            bowling_col1, bowling_col2, bowling_col3, bowling_col4 = st.columns(4)
            with bowling_col1:
                balls_bowled = st.number_input("Legal balls", min_value=0, max_value=36, value=int(current_bowling.get("balls_bowled", 0)), step=1, help="Six balls = one over; for example, 14 balls displays as 2.2 overs.")
            with bowling_col2:
                maidens = st.number_input("Maidens", min_value=0, max_value=6, value=int(current_bowling.get("maidens", 0)), step=1)
            with bowling_col3:
                runs_conceded = st.number_input("Runs conceded", min_value=0, value=int(current_bowling.get("runs_conceded", 0)), step=1)
            with bowling_col4:
                wickets = st.number_input("Wickets", min_value=0, max_value=10, value=int(current_bowling.get("wickets", 0)), step=1)
            save_bowling = st.form_submit_button("Save bowling figures", type="primary")

        if save_bowling:
            if maidens > balls_bowled // 6:
                st.error("Maiden overs cannot exceed the completed overs bowled.")
            else:
                bowling_record = {
                    "match_id": selected_id,
                    "team_id": bowling_team_id,
                    "player_id": bowler_id,
                    "player_name": players_by_id[bowler_id]["name"],
                    "bowling_order": bowling_order,
                    "balls_bowled": int(balls_bowled),
                    "maidens": int(maidens),
                    "runs_conceded": int(runs_conceded),
                    "wickets": int(wickets),
                }
                try:
                    client.table("bowling_figures").upsert(
                        bowling_record,
                        on_conflict="match_id,team_id,player_id",
                    ).execute()
                    st.success(f"Saved {players_by_id[bowler_id]['name']}'s bowling figures.")
                    st.rerun()
                except Exception as error:
                    st.error(f"Could not save the bowling figures: {error}")
    else:
        st.info("Add the opposition's players to the roster before entering bowling figures.")

    st.divider()
    st.subheader("Team member management")
    st.caption("Add roster members or remove an existing member. Changes update the shared roster immediately.")
    add_column, delete_column = st.columns(2)
    team_ids = [str(team["id"]) for team in teams]
    team_names = {str(team["id"]): str(team["name"]) for team in teams}

    with add_column:
        st.markdown("#### Add a member")
        with st.form("add_team_member_form", clear_on_submit=True):
            add_team_id = st.selectbox(
                "Team",
                team_ids,
                format_func=lambda team_id: team_names[team_id],
                key="add_member_team",
            )
            member_name = st.text_input("Player name", max_chars=80)
            member_role = st.selectbox("Role", ROLE_CHOICES)
            jersey_number = st.text_input("Jersey number (optional)", max_chars=12)
            profile_details = st.text_area("Player details (optional)", max_chars=240, placeholder="e.g. Opening batter · Right-arm medium")
            member_photo = st.file_uploader("Player photo (optional)", type=["jpg", "jpeg", "png", "webp"], key="new_member_photo")
            add_member = st.form_submit_button("Add team member", type="primary", width="stretch")

        if add_member:
            cleaned_name = member_name.strip()
            if not cleaned_name:
                st.error("Enter a player name before adding them.")
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
                    insert_result = client.table("players").insert(new_player).execute()
                    created_player = (insert_result.data or [None])[0]
                    if member_photo and not created_player:
                        created_player = (
                            client.table("players")
                            .select("id")
                            .eq("team_id", add_team_id)
                            .eq("roster_number", new_player["roster_number"])
                            .single()
                            .execute()
                            .data
                        )
                    if member_photo and created_player and created_player.get("id") is not None:
                        photo_path = save_player_photo(client, add_team_id, created_player["id"], member_photo)
                        client.table("players").update({"photo_path": photo_path}).eq("id", created_player["id"]).execute()
                    st.success(f"Added {cleaned_name} to {team_names[add_team_id]}.")
                    st.rerun()
                except Exception as error:
                    st.error(f"Could not add the team member: {error}")

    with delete_column:
        st.markdown("#### Delete a member")
        if players:
            player_ids = [str(player["id"]) for player in players if player.get("id") is not None]
            players_by_id = {str(player["id"]): player for player in players if player.get("id") is not None}

            def player_label(player_id: str) -> str:
                player = players_by_id[player_id]
                team_name = team_names.get(str(player["team_id"]), "Unknown team")
                return f"{team_name} · {player['name']} ({player.get('role') or 'Player'})"

            if player_ids:
                with st.form("delete_team_member_form"):
                    delete_player_id = st.selectbox(
                        "Select member",
                        player_ids,
                        format_func=player_label,
                    )
                    confirm_delete = st.checkbox("I confirm this member should be removed")
                    delete_member = st.form_submit_button("Delete selected member", width="stretch")

                if delete_member:
                    if not confirm_delete:
                        st.error("Confirm the deletion before continuing.")
                    else:
                        try:
                            client.table("players").delete().eq("id", delete_player_id).execute()
                            delete_player_photo(client, players_by_id[delete_player_id].get("photo_path"))
                            st.success(f"Removed {players_by_id[delete_player_id]['name']} from the roster.")
                            st.rerun()
                        except Exception as error:
                            st.error(f"Could not delete the team member: {error}")
            else:
                st.info("No database player IDs were returned. Run the latest database_setup.sql.")
        else:
            st.info("There are no team members to delete yet.")

    st.divider()
    st.markdown("#### Edit player profile / upload photo")
    editable_players = [player for player in players if player.get("id") is not None]
    if editable_players:
        editable_players_by_id = {str(player["id"]): player for player in editable_players}

        def profile_player_label(player_id: str) -> str:
            player = editable_players_by_id[player_id]
            return f"{team_names.get(str(player['team_id']), 'Team')} · {player['name']}"

        profile_player_id = st.selectbox(
            "Select player to edit",
            list(editable_players_by_id),
            format_func=profile_player_label,
            key="edit_profile_player",
        )
        selected_player = editable_players_by_id[profile_player_id]
        selected_player_team = str(selected_player["team_id"])
        role_options = ROLE_CHOICES
        current_role = normalize_role_name(selected_player.get("role"))
        role_index = role_options.index(current_role) if current_role in role_options else 0
        current_photo_url = player_photo_url(client, str(selected_player.get("photo_path") or "") or None)
        if current_photo_url:
            st.image(current_photo_url, width=160, caption=f"Current photo · {selected_player['name']}")

        with st.form(f"edit_player_profile_{profile_player_id}"):
            profile_name = st.text_input("Player name", value=str(selected_player["name"]), max_chars=80)
            profile_role = st.selectbox("Role", role_options, index=role_index)
            profile_jersey = st.text_input("Jersey number", value=str(selected_player.get("jersey_number") or ""), max_chars=12)
            profile_details_edit = st.text_area("Player details", value=str(selected_player.get("profile_details") or ""), max_chars=240)
            replacement_photo = st.file_uploader(
                "Upload or replace photo (JPG, PNG, WebP)",
                type=["jpg", "jpeg", "png", "webp"],
                key=f"edit_player_photo_{profile_player_id}",
            )
            remove_photo = st.checkbox("Remove current photo", value=False)
            save_profile = st.form_submit_button("Save player profile", type="primary")

        if save_profile and not profile_name.strip():
            st.error("Player name cannot be empty.")

        if save_profile and profile_name.strip():
            new_photo_path = selected_player.get("photo_path")
            try:
                if replacement_photo:
                    new_photo_path = save_player_photo(
                        client,
                        selected_player_team,
                        selected_player["id"],
                        replacement_photo,
                    )
                elif remove_photo:
                    new_photo_path = None

                profile_update = {
                    "name": profile_name.strip(),
                    "role": normalize_role_name(profile_role),
                    "jersey_number": profile_jersey.strip() or None,
                    "profile_details": profile_details_edit.strip() or None,
                    "photo_path": new_photo_path,
                }
                client.table("players").update(profile_update).eq("id", selected_player["id"]).execute()
                old_photo_path = str(selected_player.get("photo_path") or "") or None
                if old_photo_path and old_photo_path != new_photo_path:
                    delete_player_photo(client, old_photo_path)
                st.success(f"Saved profile for {selected_player['name']}.")
                st.rerun()
            except Exception as error:
                st.error(f"Could not save the player profile: {error}")

render_admin = render_admin_workspace


def main() -> None:
    settings = get_settings()
    client: Client | None = None
    admin_password = ""
    if settings:
        supabase_url, service_role_key, admin_password = settings
        try:
            client = create_client(supabase_url, service_role_key)
            teams, matches, players, batting_scores, bowling_figures = load_tournament(client)
        except Exception as error:
            st.error(f"Could not connect to the tournament database: {error}")
            st.info("Check the Supabase URL and service-role key in Streamlit secrets, and confirm the SQL setup ran successfully.")
            st.stop()
    else:
        teams, matches, players = DEMO_TEAMS, DEMO_MATCHES, DEMO_PLAYERS
        batting_scores, bowling_figures = [], []

    standings = build_standings(teams, matches)
    completed = sum(match.get("status") == "Completed" for match in matches)
    live = sum(match.get("status") == "Live" for match in matches)

    hero_image = find_image_asset("cricket", "hero")
    brand_image = find_image_asset("cricket", "kpl_brand")
    hero_style = ""
    if hero_image:
        hero_style = (
            "background-image:linear-gradient(90deg,#07101bf2 0%,#07101bc9 50%,#07101b40 100%),"
            f"url({image_data_uri(hero_image)});background-size:cover;background-position:right center;"
        )
    hero_class = "hero hero-with-image" if hero_image else "hero"
    brand_markup = (
        f'<div class="hero-brand"><img src="{image_data_uri(brand_image)}" alt="Kodihalli Premier League Season 2 logo"></div>'
        if brand_image
        else ""
    )

    st.markdown(
        f"""
        <div class="{hero_class}" style="{hero_style}"><div class="hero-content"><div class="hero-copy">
        <span class="hero-tag">KPL · SEASON 2</span>
        <div class="eyebrow" style="margin-top:18px">SAME GAME · DIFFERENT BATTLE</div>
        <h1>KPL<br>SESSION 2</h1>
        <p>Five teams. Ten matchups. One day of six-over cricket. Follow the schedule and live scorebook from the ground.</p>
        </div>{brand_markup}</div></div>
        """,
        unsafe_allow_html=True,
    )

    if client is None:
        st.warning("Demo preview: connect Supabase to share scores across devices. Demo scores are read-only.", icon="ℹ️")
    else:
        st.success("Connected to the shared KPL tournament database.", icon="☁️")

    metric1, metric2, metric3, metric4 = st.columns(4)
    metric1.metric("TEAMS", len(teams))
    metric2.metric("FIXTURES", len(matches))
    metric3.metric("PLAYED", completed)
    metric4.metric("LIVE NOW", live)

    st.markdown("### Tournament rules")
    rule_columns = st.columns(4)
    rule_cards = [
        ("MATCH FORMAT", "6 overs per match · 45 minutes"),
        ("POWER PLAY", "First 2 overs"),
        ("BREAKS", "No break between matches"),
        ("UMPIRE", "Umpire decision is final"),
    ]
    for column, (title, detail) in zip(rule_columns, rule_cards):
        with column:
            st.markdown(f'<div class="rule-card"><b>{title}</b><span>{detail}</span></div>', unsafe_allow_html=True)

    overview, live_score_tab, schedule_tab, scorecards_tab, table_tab, teams_tab, owners_tab, players_tab, admin_tab = st.tabs(["Overview", "Live Score", "Match schedule", "Scorecards", "Points table", "Teams", "Team owners", "Player rosters", "Admin"])
    with overview:
        left, right = st.columns([1.25, 1])
        with left:
            st.subheader("Today's fixture list")
            st.dataframe(build_schedule_frame(teams, matches), hide_index=True, width="stretch", height=430)
        with right:
            st.subheader("The teams")
            team_chips = "".join(
                f'<span class="team-chip">{team_logo_markup(team, 30)}<span>{html.escape(str(team["name"]))}</span></span>'
                for team in teams
            )
            st.markdown(team_chips, unsafe_allow_html=True)
            st.markdown("<br>", unsafe_allow_html=True)
            st.subheader("At a glance")
            st.markdown('<div class="poster-note">Start: <b>8:00 AM</b> &nbsp; · &nbsp; Last match ends: <b>4:15 PM</b> &nbsp; · &nbsp; 6 overs each</div>', unsafe_allow_html=True)
            st.caption("Knockout note copied from the poster: ‘Top 2 and 3 teams will play in the Semifinals. Top 1 team and the winners of the Semifinals play in the Finals.’ Confirm the qualification wording before the knockouts.")

    with live_score_tab:
        @st.fragment(run_every="15s" if client else None)
        def live_match_centre() -> None:
            current_matches = matches
            current_batting_scores = batting_scores
            current_bowling_figures = bowling_figures
            if client:
                try:
                    current_matches = client.table("matches").select("*").order("match_number").execute().data or []
                    current_batting_scores = client.table("batting_scores").select("*").execute().data or []
                    current_bowling_figures = client.table("bowling_figures").select("*").execute().data or []
                except Exception as error:
                    st.error(f"Could not refresh live scores: {error}")
                    return

            live_match_ids = [
                str(match["id"])
                for match in sorted(
                    current_matches,
                    key=lambda row: (row.get("status") != "Live", int(row["match_number"])),
                )
            ]
            live_matches_by_id = {str(match["id"]): match for match in current_matches}

            def live_match_label(match_id: str) -> str:
                current_match = live_matches_by_id[match_id]
                home = next(team["name"] for team in teams if str(team["id"]) == str(current_match["team1_id"]))
                away = next(team["name"] for team in teams if str(team["id"]) == str(current_match["team2_id"]))
                live_tag = "🔴 LIVE · " if current_match.get("status") == "Live" else ""
                return f"{live_tag}Match {current_match['match_number']} · {home} vs {away}"

            live_count = sum(match.get("status") == "Live" for match in current_matches)
            st.subheader("Live match centre")
            if live_count:
                st.caption(f"{live_count} match{'es' if live_count != 1 else ''} marked Live · scores refresh automatically every 15 seconds.")
            else:
                st.info("No fixture is marked Live yet. Select a scheduled match below, or ask the admin to set its status to Live.")
            if not live_match_ids:
                st.warning("No fixtures are available.")
                return
            selected_live_match_id = st.selectbox(
                "Select match",
                live_match_ids,
                format_func=live_match_label,
                key="live_score_match_select",
            )
            render_live_score(
                live_matches_by_id[selected_live_match_id],
                teams,
                current_batting_scores,
                current_bowling_figures,
            )

        live_match_centre()

    with schedule_tab:
        st.subheader("Full tournament schedule")
        st.dataframe(build_schedule_frame(teams, matches), hide_index=True, width="stretch", height=560)
        st.caption("All match times and pairings are transcribed from the supplied KPL Season 2 poster.")

    with scorecards_tab:
        st.subheader("Match scorecards")
        scorecard_match_ids = [str(match["id"]) for match in matches]
        matches_by_id = {str(match["id"]): match for match in matches}

        def scorecard_match_label(match_id: str) -> str:
            match = matches_by_id[match_id]
            home = next(team["name"] for team in teams if str(team["id"]) == str(match["team1_id"]))
            away = next(team["name"] for team in teams if str(team["id"]) == str(match["team2_id"]))
            return f"Match {match['match_number']} · {home} vs {away}"

        selected_scorecard_id = st.selectbox(
            "Choose a match",
            scorecard_match_ids,
            format_func=scorecard_match_label,
            key="public_scorecard_match",
        )
        render_scorecard(matches_by_id[selected_scorecard_id], teams, batting_scores, bowling_figures)

    with table_tab:
        st.subheader("Points table")
        st.caption("Scoring used by this app: 2 points for a win, 1 point per team for a tie, 0 for a loss. Teams tied on points are ordered by wins, then poster seed order.")
        table_rows = [
            {"POS": index, "TEAM": row["team"], "P": row["played"], "W": row["won"], "T": row["tied"], "L": row["lost"], "PTS": row["points"]}
            for index, row in enumerate(standings, start=1)
        ]
        st.dataframe(pd.DataFrame(table_rows), hide_index=True, width="stretch")

    with teams_tab:
        st.subheader("Meet the five sides")
        team_columns = st.columns(5)
        for column, team in zip(team_columns, teams):
            with column:
                st.markdown(
                    f'<div class="rule-card" style="border-top:4px solid {team.get("color", "#ffd900")};text-align:center;min-height:210px">'
                    f'<div class="team-logo-frame">{team_logo_markup(team, 112)}</div>'
                    f'<div style="font-size:1.25rem;font-weight:900;color:{team.get("color", "#ffd900")}">{team.get("short_name", "KPL")}</div>'
                    f'<b style="display:block;color:#fff;margin:12px 0 0">{team["name"]}</b></div>',
                    unsafe_allow_html=True,
                )

    with owners_tab:
        st.subheader("Team owners")
        st.caption("Owner names appear here when their roster role is marked Owner.")
        owner_columns = st.columns(3)
        for index, team in enumerate(teams):
            team_owners = [
                player["name"]
                for player in players
                if str(player["team_id"]) == str(team["id"])
                and normalize_role_name(player.get("role")) == "Owner"
            ]
            owner_text = ", ".join(team_owners) if team_owners else "Not listed"
            with owner_columns[index % len(owner_columns)]:
                st.markdown(
                    f'<div class="rule-card" style="border-top:4px solid {team.get("color", "#ffd900")};min-height:105px">'
                    f'<b>{html.escape(str(team["name"]))}</b>'
                    f'<span>{html.escape(owner_text)}</span></div>',
                    unsafe_allow_html=True,
                )

    with players_tab:
        st.subheader("Player rosters")
        st.caption("Player photos, team roles, jersey numbers, and profile details appear here.")
        players_by_team: dict[str, list[dict[str, Any]]] = {str(team["id"]): [] for team in teams}
        for player in players:
            players_by_team.setdefault(str(player["team_id"]), []).append(player)
        for team in teams:
            team_id = str(team["id"])
            roster = players_by_team.get(team_id, [])
            with st.expander(f"{team['name']} · {len(roster)} listed", expanded=bool(roster)):
                if roster:
                    profile_columns = st.columns(3)
                    for index, player in enumerate(roster):
                        with profile_columns[index % len(profile_columns)]:
                            photo_url = player_photo_url(client, str(player.get("photo_path") or "") or None) if client else None
                            if photo_url:
                                st.image(photo_url, width="stretch")
                            else:
                                team_logo = find_image_asset("team_logos", team_id)
                                if team_logo:
                                    st.image(str(team_logo), width=130)
                                else:
                                    st.markdown(team_logo_markup(team, 112), unsafe_allow_html=True)
                                st.caption("Player photo not uploaded")
                            st.markdown(f"**{html.escape(str(player['name']))}**")
                            jersey = str(player.get("jersey_number") or "Not set")
                            role = normalize_role_name(player.get("role"))
                            st.caption(f"{html.escape(role)} · #{html.escape(jersey)}")
                            details = str(player.get("profile_details") or "").strip()
                            if details:
                                st.write(details)
                else:
                    st.caption("Roster details not received yet. Add this team's list when available.")

    with admin_tab:
        if client is None:
            st.info("Add the Supabase and admin secrets to enable shared score updates.")
        elif not admin_password:
            st.error("ADMIN_PASSWORD is not set in Streamlit secrets. Score updates are disabled until an admin password is configured.")
        else:
            render_admin(client, teams, matches, players, batting_scores, bowling_figures, admin_password)

    st.divider()
    st.caption("KPL Season 2 · Built for the teams, scorekeepers, and supporters. Scores are shared through the tournament database when connected.")


if __name__ == "__main__":
    main()
