import streamlit as st

from db import (
    init_db,
    sign_in_user,
    sign_out_user,
    load_current_program_into_session,
)
from tabs.program_creation import render_program_creation
from tabs.program_tracking import render_program_tracking
from tabs.stats import render_stats
# from tabs.progression import render_progression


init_db()

st.set_page_config(page_title="5/3/1 Tracker")


def render_login() -> None:
    st.title("5/3/1 Tracker")
    st.subheader("Sign in")

    with st.form("login_form"):
        email = st.text_input("Email")
        password = st.text_input("Password", type="password")
        submitted = st.form_submit_button("Sign in")

    if submitted:
        try:
            sign_in_user(email=email, password=password)
            load_current_program_into_session()
            st.success("Signed in.")
            st.rerun()
        except Exception as exc:
            st.error(str(exc))


if not st.session_state.get("authenticated", False):
    render_login()
    st.stop()

# On reruns after the initial login, restore the current saved program if needed.
if "program" not in st.session_state:
    load_current_program_into_session()

header_col, action_col = st.columns([4, 1])
with header_col:
    st.caption(f"Signed in as {st.session_state.get('user_email', '')}")
with action_col:
    if st.button("Sign out"):
        sign_out_user()
        st.rerun()

tab1, tab2, tab3, tab4 = st.tabs([
    "Program Creation",
    "Program Tracking",
    "Stats",
    "Program Progression",
])

with tab1:
    render_program_creation()

with tab2:
    render_program_tracking()

with tab3:
    render_stats()

# with tab4:
#     render_progression()
