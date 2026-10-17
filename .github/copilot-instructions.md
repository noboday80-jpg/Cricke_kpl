## KPL Season 2 project

- The deployed app is Python + Streamlit; `app.py` is the Community Cloud entry point.
- Supabase stores the shared schedule and scores. Keep service-role credentials server-side in Streamlit secrets only.
- Admin updates require the password configured under `[auth]` in Streamlit secrets.
- Treat the poster's knockout qualification text as ambiguous; do not silently reinterpret it.
- Keep README.md, `database_setup.sql`, and `requirements.txt` aligned with app behavior.
- Run `python -m unittest discover -s tests` and check Python syntax after changes.
