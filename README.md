# KPL Season 2 · Tournament Central

A Python + Streamlit tournament site transcribed from the supplied schedule poster. It includes five teams, ten 6-over fixtures, match start/end times, score entry, and a shared points table.

See [assets/README.md](assets/README.md) for the team-logo and cricket hero image filenames the UI loads automatically.

## Tournament details included

- Team Varanasi, OG Power Star Soldiers, Team Race Gurram, Royal Strikes, and Devara Dragons.
- Ten scheduled matches from 8:00 AM to 4:15 PM; each is 6 overs and 45 minutes.
- Admins publish team scores and mark a fixture Live in Admin → Live score entry. The public Live Score tab reads the shared match/scorecard data and refreshes it every 15 seconds. Ball-by-ball commentary is not captured.
- Two-over power play, no break between matches, and umpire decision is final.
- Player rosters are transcribed for all five teams. The Team Varanasi roster comes from the upper-middle handwritten list; the confirmed spelling is “Chandrashekar.” Crossed-out names were omitted.
- The poster's knockout wording is displayed as supplied and flagged for confirmation because its semifinal qualification is ambiguous.
- Points table currently uses 2 points for a win and 1 point each for a tie. The poster does not specify a scoring system.
- Signed-in admins can add players to a selected team or delete a player with an explicit confirmation; changes are written to Supabase and appear in the shared roster.
- The Admin workspace separates tasks into Live score entry, Batter & bowler, Team members, and Player profiles tabs.
- Admins can record each batter's runs, balls, fours, sixes, and dismissal, plus each bowler's legal balls, maidens, runs conceded, and wickets. The public Scorecards tab shows these figures, strike rate, and economy.
- The Team owners tab lists roster members marked with the Owner role. Confirmed owners: Team Varanasi — Guru Prasad; Team Race Gurram — Charan; Devara Dragons — Rajesh. Scorecards and the points table remain separate tabs.
- Admins can upload or replace player portraits and edit role, jersey number, and a short profile description. Photos appear with player details in the Player rosters tab.

## Run locally

1. Install Python 3.10 or newer.
2. Install dependencies with `pip install -r requirements.txt`.
3. Copy `.streamlit/secrets.toml.example` to `.streamlit/secrets.toml` and fill in the Supabase project URL, service-role key, and a strong admin password.
4. Run `streamlit run app.py`.

Without secrets, the app opens in read-only demo mode. Never commit `.streamlit/secrets.toml` or expose the Supabase service-role key in frontend code.

## Create the shared online database

1. Create a Supabase project on its free plan.
2. Open the Supabase SQL Editor and run all of [`database_setup.sql`](database_setup.sql). It creates and seeds the team, fixture, player roster, batter score, and bowler figure tables, creates the public-read player-photo bucket, and enables read-only table policies. If you already ran an earlier version, run the updated SQL again to add scorecard, live-innings, player-profile, and photo fields.
3. Copy the project URL and service-role key from the Supabase project settings. Keep the service-role key private; Streamlit uses it only on the server.
4. Set `supabase.url`, `supabase.service_role_key`, and `auth.admin_password` as Streamlit secrets. Only an admin who enters that password can save scores; viewers see the shared database results.

## Publish with GitHub and Streamlit Community Cloud

1. Create a GitHub repository and push this project, including `app.py`, `admin_ui.py`, `tournament.py`, `requirements.txt`, `database_setup.sql`, and the `assets/` folder. The real `.streamlit/secrets.toml` is ignored by Git.
2. In Streamlit Community Cloud, create an app from that repository and select `app.py` as the main file.
3. In the app's settings, add these secrets:

```toml
[supabase]
url = "https://YOUR-PROJECT.supabase.co"
service_role_key = "YOUR-SUPABASE-SERVICE-ROLE-KEY"

[auth]
admin_password = "YOUR-STRONG-ADMIN-PASSWORD"
```

4. Deploy. Share the Streamlit app URL with teams and supporters. Anyone with the URL can view the schedule and scores; only people with the admin password can update results.

## Data and security notes

- Scores and standings are shared through Supabase, not stored in each viewer's browser.
- Keep the service-role key only in Streamlit's server-side secrets. Do not publish it in GitHub, chat, screenshots, or client-side code.
- The SQL policies allow public reads but no direct public writes. Admin updates go through the Streamlit server after password verification.
- Player photos in the public `player-photos` bucket can be viewed by anyone who can view the roster. Only the Streamlit server uses the service-role key to upload/delete images; never expose that key in browser-side code.
- Confirm the semifinal qualification wording and the points rules with the tournament organizer before using this for official results.
