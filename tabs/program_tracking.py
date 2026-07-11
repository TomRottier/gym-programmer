from __future__ import annotations

from datetime import date
from typing import Any

import pandas as pd
import streamlit as st

from db import (
    get_amrap_results,
    load_current_program_into_session,
    replace_amrap_results,
    save_program,
)
from logic.program_models import Program, Exercise, Cycle, Scheme


# ==========================================================
# Core derivation
# ==========================================================

def format_set_cell(rep: int | str, weight: float) -> str:
    return f"{weight:.1f}kg x {rep}"


def training_max_for_cycle(exercise: Exercise, cycle_index: int) -> float:
    return exercise.training_max + (cycle_index - 1) * exercise.increment


def derive_weights_for_step(
    exercise: Exercise,
    cycle: Cycle,
    scheme: Scheme,
    step_index: int,
    ) -> list[float]:
    tm = training_max_for_cycle(exercise, cycle.index)
    pct_step = scheme.pct[step_index]
    return [tm * float(p) for p in pct_step]


def get_amrap_set_index(reps_step: list[int | str]) -> int | None:
    for idx, rep in enumerate(reps_step):
        if isinstance(rep, str) and ("+" in rep or rep == "PR"):
            return idx
    return None


def derive_supplemental_value(
    exercise: Exercise,
    cycle: Cycle,
    main_step_index: int,
) -> tuple[str | None, str | None]:
    supp = cycle.supplemental
    if supp is None:
        return None, None

    if not supp.reps or not supp.pct:
        return None, None

    supp_reps_step_index = min(main_step_index, len(supp.reps) - 1)
    supp_pct_step_index = min(main_step_index, len(supp.pct) - 1)

    supp_reps = supp.reps[supp_reps_step_index]
    supp_weights = derive_weights_for_step(
        exercise=exercise,
        cycle=cycle,
        scheme=supp,
        step_index=supp_pct_step_index,
    )

    if not supp_reps or not supp_weights:
        return None, None

    return supp.name, f"{supp_weights[0]:.1f}kg x {supp_reps[0]}"


def session_rows(
    exercise: Exercise,
    cycle: Cycle,
    step_index: int,
    reps_step: list[int | str],
    weights: list[float],
    week_label: str,
    program_week_number: int,
    amrap_results: dict[tuple[int, str, int, int], int],
) -> dict[str, Any]:
    rows: list[tuple[str, str]] = []

    for set_index, rep in enumerate(reps_step):
        rows.append(
            (
                f"Set {set_index + 1}",
                format_set_cell(rep, weights[set_index]),
            )
        )

    # Supplemental only applies to normal training weeks, not deload/test weeks.
    if not week_label.startswith("Deload"):
        supp_label, supp_value = derive_supplemental_value(
            exercise=exercise,
            cycle=cycle,
            main_step_index=step_index,
        )
        if supp_label is not None and supp_value is not None:
            rows.append((supp_label, supp_value))

    amrap_set_index = get_amrap_set_index(reps_step)
    amrap_value = None
    planned_reps_label = None
    weight_used = None

    if amrap_set_index is not None:
        result_key = (
            cycle.index,
            exercise.name,
            step_index,
            amrap_set_index + 1,
        )
        amrap_value = amrap_results.get(result_key)
        planned_reps_label = str(reps_step[amrap_set_index])
        weight_used = float(weights[amrap_set_index])
        rows.append(("AMRAP", "" if amrap_value is None else str(amrap_value)))

    return {
        "cycle_index": cycle.index,
        "cycle_name": cycle.main.name,
        "exercise_name": exercise.name,
        "week_index": step_index + 1,
        "week_label": week_label,
        "program_week_number": program_week_number,
        "rows": rows,
        "step_index": step_index,
        "set_index": amrap_set_index + 1 if amrap_set_index is not None else None,
        "planned_reps_label": planned_reps_label,
        "weight_used": weight_used,
        "is_deload": week_label.startswith("Deload"),
    }


def build_sessions(
    program: Program,
    amrap_results: dict[tuple[int, str, int, int], int],
) -> list[dict[str, Any]]:
    sessions: list[dict[str, Any]] = []
    completed_program_weeks = 0

    for cycle in program.cycles:
        # ------------------------------
        # Main weeks
        # ------------------------------
        for step_index, reps_step in enumerate(cycle.main.reps):
            program_week_number = completed_program_weeks + step_index + 1
            week_label = f"Week {step_index + 1}"

            for exercise in program.exercises:
                weights = derive_weights_for_step(
                    exercise=exercise,
                    cycle=cycle,
                    scheme=cycle.main,
                    step_index=step_index,
                )

                sessions.append(
                    session_rows(
                        exercise=exercise,
                        cycle=cycle,
                        step_index=step_index,
                        reps_step=reps_step,
                        weights=weights,
                        week_label=week_label,
                        program_week_number=program_week_number,
                        amrap_results=amrap_results,
                    )
                )

        completed_program_weeks += len(cycle.main.reps)

        # ------------------------------
        # Deload / test week
        # ------------------------------
        if cycle.deload is not None:
            reps_step = cycle.deload.reps[0]
            week_label = f"Deload – {cycle.deload.name}"
            program_week_number = completed_program_weeks + 1
            step_index = len(cycle.main.reps)

            for exercise in program.exercises:
                weights = derive_weights_for_step(
                    exercise=exercise,
                    cycle=cycle,
                    scheme=cycle.deload,
                    step_index=0,
                )

                sessions.append(
                    session_rows(
                        exercise=exercise,
                        cycle=cycle,
                        step_index=step_index,
                        reps_step=reps_step,
                        weights=weights,
                        week_label=week_label,
                        program_week_number=program_week_number,
                        amrap_results=amrap_results,
                    )
                )

            completed_program_weeks += 1

    return sessions


# ==========================================================
# AMRAP loading / saving
# ==========================================================

def ensure_amrap_results_loaded(
    program_id: int,
) -> dict[tuple[int, str, int, int], int]:
    loaded_program_id = st.session_state.get("loaded_amrap_program_id")

    if loaded_program_id != program_id:
        st.session_state.loaded_amrap_results = get_amrap_results(program_id)
        st.session_state.loaded_amrap_program_id = program_id

    return st.session_state.get("loaded_amrap_results", {})


def table_to_df(sessions: list[dict[str, Any]]) -> pd.DataFrame:
    field_order: list[str] = []
    seen: set[str] = set()

    preferred_order = [
        "Set 1",
        "Set 2",
        "Set 3",
        "Set 4",
        "Set 5",
        "AMRAP",
    ]

    raw_fields: list[str] = []

    for session in sessions:
        for label, _ in session["rows"]:
            if label not in seen:
                seen.add(label)
                raw_fields.append(label)

    for field in preferred_order:
        if field in raw_fields:
            field_order.append(field)

    for field in raw_fields:
        if field not in field_order:
            field_order.append(field)

    data: dict[str, list[str]] = {"Field": field_order}

    for session in sessions:
        row_map = {label: value for label, value in session["rows"]}
        data[session["exercise_name"]] = [
            row_map.get(field, "") for field in field_order
        ]

    return pd.DataFrame(data)


def render_combined_table(
    sessions: list[dict[str, Any]],
    table_key: str,
    visible_edited_tables: dict[str, tuple[pd.DataFrame, list[dict[str, Any]]]],
) -> None:
    df = table_to_df(sessions)
    exercise_cols = [s["exercise_name"] for s in sessions]

    column_config: dict[str, Any] = {
        "Field": st.column_config.TextColumn(width="small")
    }

    for col in exercise_cols:
        column_config[col] = st.column_config.TextColumn(width="small")

    edited_df = st.data_editor(
        df,
        width="stretch",
        hide_index=True,
        num_rows="fixed",
        disabled=["Field"],
        column_config=column_config,
        key=table_key,
    )

    visible_edited_tables[table_key] = (edited_df, sessions)


def collect_amrap_results(
    all_sessions: list[dict[str, Any]],
    visible_edited_tables: dict[str, tuple[pd.DataFrame, list[dict[str, Any]]]],
) -> list[dict[str, object]]:
    collected: dict[tuple[int, str, int, int], dict[str, object]] = {}

    # Keep existing AMRAP values for sessions not currently visible.
    for session in all_sessions:
        if session.get("set_index") is None:
            continue

        rows = {label: value for label, value in session["rows"]}
        raw_value = str(rows.get("AMRAP", "")).strip()

        if raw_value in ("", "0"):
            continue

        key = (
            session["cycle_index"],
            session["exercise_name"],
            session["step_index"],
            session["set_index"],
        )

        collected[key] = {
            "cycle_index": session["cycle_index"],
            "exercise_name": session["exercise_name"],
            "step_index": session["step_index"],
            "set_index": session["set_index"],
            "planned_reps_label": session["planned_reps_label"],
            "weight_used": session["weight_used"],
            "actual_reps": int(raw_value),
        }

    # Overwrite with values edited in currently visible tables.
    for edited_df, sessions in visible_edited_tables.values():
        if "AMRAP" not in edited_df["Field"].values:
            continue

        amrap_row = edited_df[edited_df["Field"] == "AMRAP"].iloc[0]

        for session in sessions:
            if session.get("set_index") is None:
                continue

            raw_value = str(amrap_row.get(session["exercise_name"], "")).strip()

            key = (
                session["cycle_index"],
                session["exercise_name"],
                session["step_index"],
                session["set_index"],
            )

            if raw_value in ("", "0"):
                collected.pop(key, None)
                continue

            collected[key] = {
                "cycle_index": session["cycle_index"],
                "exercise_name": session["exercise_name"],
                "step_index": session["step_index"],
                "set_index": session["set_index"],
                "planned_reps_label": session["planned_reps_label"],
                "weight_used": session["weight_used"],
                "actual_reps": int(raw_value),
            }

    return list(collected.values())


# ==========================================================
# Rendering helpers
# ==========================================================

def render_week_group(
    week_sessions: list[dict[str, Any]],
    table_prefix: str,
    visible_edited_tables: dict[str, tuple[pd.DataFrame, list[dict[str, Any]]]],
) -> None:
    if not week_sessions:
        return

    table_key = (
        f"{table_prefix}_cycle{week_sessions[0]['cycle_index']}"
        f"_week{week_sessions[0]['week_label']}"
    )

    render_combined_table(
        week_sessions,
        table_key,
        visible_edited_tables,
    )


def render_cycle_view(
    cycle_sessions: list[dict[str, Any]],
    visible_edited_tables: dict[str, tuple[pd.DataFrame, list[dict[str, Any]]]],
) -> None:
    week_groups: dict[str, list[dict[str, Any]]] = {}

    for session in cycle_sessions:
        week_groups.setdefault(session["week_label"], []).append(session)

    for week_label, week_sessions in week_groups.items():
        st.markdown(f"### {week_label}")
        render_week_group(week_sessions, "cycle_view", visible_edited_tables)
        st.divider()


def render_program_view(
    all_sessions: list[dict[str, Any]],
    visible_edited_tables: dict[str, tuple[pd.DataFrame, list[dict[str, Any]]]],
) -> None:
    cycle_groups: dict[int, list[dict[str, Any]]] = {}

    for session in all_sessions:
        cycle_groups.setdefault(session["cycle_index"], []).append(session)

    for cycle_index, cycle_sessions in cycle_groups.items():
        cycle_name = cycle_sessions[0]["cycle_name"]
        st.subheader(f"Cycle {cycle_index} – {cycle_name}")
        render_cycle_view(cycle_sessions, visible_edited_tables)


# ==========================================================
# Current week defaults
# ==========================================================

def normalise_start_date(value: Any) -> date | None:
    if value is None:
        return None

    if isinstance(value, date):
        return value

    if isinstance(value, str):
        try:
            return date.fromisoformat(value)
        except ValueError:
            return None

    return None


def get_current_program_week(start_date: date | None, total_weeks: int) -> int:
    if start_date is None:
        return 1

    today = date.today()
    delta_days = (today - start_date).days
    current_week = (delta_days // 7) + 1

    if current_week < 1:
        return 1

    if current_week > total_weeks:
        return total_weeks

    return current_week


def get_default_cycle_and_week_label(
    sessions: list[dict[str, Any]],
    start_date: date | None,
) -> tuple[int, str]:
    if not sessions:
        return 1, "Week 1"

    total_weeks = max(session["program_week_number"] for session in sessions)
    current_program_week = get_current_program_week(start_date, total_weeks)

    matching = next(
        (
            session
            for session in sessions
            if session["program_week_number"] == current_program_week
        ),
        sessions[0],
    )

    return matching["cycle_index"], matching["week_label"]


def sync_tracking_defaults(
    default_cycle: int,
    default_week_label: str,
    program_identity: str,
) -> None:
    target = (program_identity, default_cycle, default_week_label)

    if st.session_state.get("tracking_default_target") != target:
        st.session_state["tracking_default_target"] = target
        st.session_state["tracking_cycle_select"] = default_cycle
        st.session_state["tracking_week_select"] = default_week_label
        st.session_state["tracking_view_mode"] = "Week"


# ==========================================================
# Main render
# ==========================================================

def render_program_tracking() -> None:
    st.header("Program Tracking")

    program = st.session_state.get("program")

    if not isinstance(program, Program):
        program = load_current_program_into_session()

        if not isinstance(program, Program):
            st.write("No program generated yet. Go to Program Creation.")
            return

        st.session_state.program = program

    saved_program_id = st.session_state.get("saved_program_id")

    amrap_defaults: dict[tuple[int, str, int, int], int] = {}
    if saved_program_id is not None:
        amrap_defaults = ensure_amrap_results_loaded(saved_program_id)

    start_date = normalise_start_date(st.session_state.get("start_date"))
    all_sessions = build_sessions(program, amrap_defaults)

    default_cycle, default_week_label = get_default_cycle_and_week_label(
        all_sessions,
        start_date,
    )

    program_identity = (
        f"program_{saved_program_id}"
        if saved_program_id is not None
        else "draft"
    )

    sync_tracking_defaults(
        default_cycle=default_cycle,
        default_week_label=default_week_label,
        program_identity=program_identity,
    )

    # ------------------------------
    # Top actions
    # ------------------------------
    action_left, action_mid, action_load = st.columns([1, 1, 1])

    with action_left:
        if st.button("Save Program to Database", use_container_width=True):
            try:
                program_id = save_program(program)
                st.session_state.saved_program_id = program_id
                st.session_state.loaded_amrap_program_id = None
                st.session_state.loaded_amrap_results = {}
                st.success(f"Saved program to database (ID {program_id}).")
                st.rerun()
            except Exception as exc:
                st.error(str(exc))

    with action_mid:
        save_amrap_clicked = st.button(
            "Save AMRAP Results",
            use_container_width=True,
        )

    with action_load:
        if st.button("Load Saved Program", use_container_width=True):
            try:
                loaded_program = load_current_program_into_session()
                if loaded_program is None:
                    st.error("No saved program found in database.")
                else:
                    st.session_state.tracking_default_target = None
                    st.success("Loaded saved program.")
                    st.rerun()
            except Exception as exc:
                st.error(str(exc))

    # ------------------------------
    # Horizontal controls
    # ------------------------------
    controls_label, controls_left, controls_mid, controls_right = st.columns(
        [0.5, 1, 1, 1]
    )

    with controls_label:
        st.markdown("**View**")

    with controls_left:
        view_mode = st.selectbox(
            "View",
            ["Week", "Cycle", "Program"],
            key="tracking_view_mode",
            label_visibility="collapsed",
        )

    visible_edited_tables: dict[str, tuple[pd.DataFrame, list[dict[str, Any]]]] = {}

    cycle_numbers = sorted({session["cycle_index"] for session in all_sessions})
    cycle_labels = {n: f"Cycle {n}" for n in cycle_numbers}

    if (
        "tracking_cycle_select" not in st.session_state
        or st.session_state["tracking_cycle_select"] not in cycle_numbers
    ):
        st.session_state["tracking_cycle_select"] = default_cycle

    # ------------------------------
    # Week view
    # ------------------------------
    if view_mode == "Week":
        with controls_mid:
            selected_cycle = st.selectbox(
                "Cycle",
                cycle_numbers,
                key="tracking_cycle_select",
                format_func=lambda x: cycle_labels[x],
                label_visibility="collapsed",
            )

        cycle_sessions = [
            s for s in all_sessions if s["cycle_index"] == selected_cycle
        ]

        week_options: list[str] = []
        seen_week_labels: set[str] = set()

        for session in cycle_sessions:
            label = session["week_label"]
            if label not in seen_week_labels:
                seen_week_labels.add(label)
                week_options.append(label)

        if (
            "tracking_week_select" not in st.session_state
            or st.session_state["tracking_week_select"] not in week_options
        ):
            st.session_state["tracking_week_select"] = (
                default_week_label
                if default_week_label in week_options
                else week_options[0]
            )

        with controls_right:
            selected_week = st.selectbox(
                "Week",
                week_options,
                key="tracking_week_select",
                label_visibility="collapsed",
            )

        week_sessions = [
            s for s in cycle_sessions if s["week_label"] == selected_week
        ]

        render_week_group(
            week_sessions,
            "week_view",
            visible_edited_tables,
        )

    # ------------------------------
    # Cycle view
    # ------------------------------
    elif view_mode == "Cycle":
        with controls_mid:
            selected_cycle = st.selectbox(
                "Cycle",
                cycle_numbers,
                key="tracking_cycle_select",
                format_func=lambda x: cycle_labels[x],
                label_visibility="collapsed",
            )

        cycle_sessions = [
            s for s in all_sessions if s["cycle_index"] == selected_cycle
        ]

        render_cycle_view(
            cycle_sessions,
            visible_edited_tables,
        )

    # ------------------------------
    # Program view
    # ------------------------------
    else:
        render_program_view(
            all_sessions,
            visible_edited_tables,
        )

    # ------------------------------
    # Save AMRAP results
    # ------------------------------
    if save_amrap_clicked:
        if saved_program_id is None:
            st.error("Save program to database first.")
        else:
            try:
                results = collect_amrap_results(
                    all_sessions,
                    visible_edited_tables,
                )
                replace_amrap_results(saved_program_id, results)
                st.session_state.loaded_amrap_results = get_amrap_results(
                    saved_program_id
                )
                st.session_state.loaded_amrap_program_id = saved_program_id
                st.success("AMRAP results saved.")
            except Exception as exc:
                st.error(str(exc))
