import streamlit as st

from logic.program_templates import (
    PROGRAM_TEMPLATES,
    SUPPLEMENTAL_TEMPLATES,
    DELOAD_TEMPLATES,
)
from logic.program_generator import generate_program


EXERCISES = [
    "Squat",
    "Bench Press",
    "Deadlift",
    "Overhead Press",
]


def render_program_creation():
    st.header("Program Creation")

    # ==================================================
    # Global settings
    # ==================================================
    st.subheader("Global Settings")

    program_name = st.text_input(
        "Program Name",
        value="5/3/1 Program",
    )
    st.session_state.program_name = program_name

    start_date = st.date_input("Program Start Date")
    st.session_state.start_date = start_date

    st.divider()

    # ==================================================
    # Exercises in program
    # ==================================================
    st.subheader("Exercises in Program")

    if "program_exercises" not in st.session_state:
        st.session_state.program_exercises = []

    if st.button("Add Exercise"):
        already_selected = {ex["name"] for ex in st.session_state.program_exercises}

        remaining_options = [
            ex_name for ex_name in EXERCISES
            if ex_name not in already_selected
        ]

        if remaining_options:
            st.session_state.program_exercises.append(
                {
                    "name": remaining_options[0],
                    "tm": 100.0,
                    "increment": 2.5,
                }
            )

    for i, ex in enumerate(st.session_state.program_exercises):
        col1, col2, col3, col4 = st.columns([3, 2, 2, 1])

        with col1:
            selected_elsewhere = {
                e["name"]
                for j, e in enumerate(st.session_state.program_exercises)
                if j != i
            }

            available_options = [
                ex_name
                for ex_name in EXERCISES
                if ex_name not in selected_elsewhere or ex_name == ex["name"]
            ]

            if ex["name"] not in available_options:
                ex["name"] = available_options[0]

            ex["name"] = st.selectbox(
                "Exercise",
                options=available_options,
                index=available_options.index(ex["name"]),
                key=f"exercise_name_{i}",
            )

        with col2:
            ex["tm"] = st.number_input(
                "Training Max (kg)",
                min_value=0.0,
                step=2.5,
                value=float(ex["tm"]),
                key=f"exercise_tm_{i}",
            )

        with col3:
            ex["increment"] = st.number_input(
                "TM Increment (kg)",
                min_value=0.0,
                step=0.5,
                value=float(ex["increment"]),
                key=f"exercise_increment_{i}",
            )

        with col4:
            st.write("")
            if st.button("Remove", key=f"remove_exercise_{i}"):
                st.session_state.program_exercises.pop(i)
                st.rerun()

    if not st.session_state.program_exercises:
        st.info("Add at least one exercise to the program.")

    st.divider()

    # ==================================================
    # Program structure
    # ==================================================
    st.subheader("Program Structure")

    if "cycles" not in st.session_state:
        st.session_state.cycles = []

    main_options = list(PROGRAM_TEMPLATES.keys())
    supplemental_options = list(SUPPLEMENTAL_TEMPLATES.keys())
    deload_options = ["None"] + list(DELOAD_TEMPLATES.keys())

    if st.button("Add Cycle"):
        st.session_state.cycles.append(
            {
                "type": "Leader",
                "main": main_options[0],
                "supplemental": supplemental_options[0],
                "deload": False,
                "deload_type": None,
            }
        )

    for i, cycle in enumerate(st.session_state.cycles):
        st.markdown(f"### Cycle {i + 1}")

        col1, col2, col3, col4, col5 = st.columns([1, 1, 1, 1, 1])

        with col1:
            cycle["type"] = st.selectbox(
                "Type",
                options=["Leader", "Anchor"],
                index=0 if cycle["type"] == "Leader" else 1,
                key=f"cycle_type_{i}",
            )

        with col2:
            cycle["main"] = st.selectbox(
                "Main",
                options=main_options,
                index=main_options.index(cycle["main"]),
                key=f"cycle_main_{i}",
            )

        with col3:
            cycle["supplemental"] = st.selectbox(
                "Supplemental",
                options=supplemental_options,
                index=supplemental_options.index(cycle["supplemental"]),
                key=f"cycle_supp_{i}",
            )

        with col4:
            current_deload_value = cycle["deload_type"] if cycle["deload_type"] is not None else "None"

            cycle["deload_type"] = st.selectbox(
                "Deload",
                options=deload_options,
                index=deload_options.index(current_deload_value),
                key=f"cycle_deload_type_{i}",
            )

            cycle["deload"] = cycle["deload_type"] != "None"

            if not cycle["deload"]:
                cycle["deload_type"] = None

        with col5:
            st.write("")
            if st.button("Remove", key=f"delete_cycle_{i}"):
                st.session_state.cycles.pop(i)
                st.rerun()

        st.divider()

    # ==================================================
    # Build program
    # ==================================================
    st.subheader("Build Program")

    can_generate = bool(st.session_state.program_exercises) and bool(
        st.session_state.cycles
    )

    if not can_generate:
        st.warning("Add at least one exercise and one cycle before generating.")
        return

    if st.button("Generate Program"):
        st.session_state.program = generate_program(
            program_name=st.session_state.program_name,
            exercises_config=st.session_state.program_exercises,
            cycles_config=st.session_state.cycles,
        )

        st.success("Program generated.")
