import pandas as pd
import streamlit as st

from db import get_estimated_training_maxes
from logic.program_models import Program


def render_stats() -> None:
    st.header("Stats")

    if "program" not in st.session_state or "saved_program_id" not in st.session_state:
        st.write("Save a program to the database first.")
        return

    program = st.session_state.program
    if not isinstance(program, Program):
        st.write("Program object is invalid.")
        return

    program_id = st.session_state.saved_program_id
    estimated_tms = get_estimated_training_maxes(program_id)

    if not estimated_tms:
        st.write("No AMRAP / PR-test data available yet.")
        return

    est_tm_df = pd.DataFrame(estimated_tms)

    for exercise in program.exercises:
        st.subheader(exercise.name)

        exercise_df = est_tm_df[
            est_tm_df["exercise_name"] == exercise.name
        ].copy()

        if exercise_df.empty:
            st.write("No data for this exercise yet.")
            continue

        exercise_df = exercise_df.sort_values(["cycle_index", "created_at"])

        exercise_df["Point"] = [
            f"Cycle {int(c)} result {i + 1}"
            for i, c in enumerate(exercise_df["cycle_index"])
        ]
        exercise_df["Estimated TM"] = exercise_df["estimated_training_max"].astype(float)

        chart_df = exercise_df.set_index("Point")[["Estimated TM"]]
        st.line_chart(chart_df)

        detail_df = exercise_df[
            ["cycle_index", "estimated_training_max", "created_at"]
        ].copy()
        detail_df.columns = ["Cycle", "Estimated TM", "Timestamp"]

        st.dataframe(detail_df, width="stretch", hide_index=True)
