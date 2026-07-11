import json
from datetime import date, datetime, timezone
from typing import Any

import streamlit as st
from supabase import Client, create_client

from logic.program_models import Program, Exercise, Cycle, Scheme


SUPABASE_URL = st.secrets["SUPABASE_URL"]
SUPABASE_KEY = st.secrets["SUPABASE_KEY"]


# ------------------------------
# Client / auth
# ------------------------------

def init_db() -> None:
    _ = SUPABASE_URL
    _ = SUPABASE_KEY


def _new_client() -> Client:
    return create_client(SUPABASE_URL, SUPABASE_KEY)


def _get_client() -> Client:
    client = _new_client()
    access_token = st.session_state.get("supabase_access_token")
    refresh_token = st.session_state.get("supabase_refresh_token")

    if access_token and refresh_token:
        client.auth.set_session(access_token, refresh_token)

    return client


def sign_in_user(email: str, password: str) -> None:
    client = _new_client()
    response = client.auth.sign_in_with_password(
        {
            "email": email,
            "password": password,
        }
    )

    session = response.session
    user = response.user

    if session is None or user is None:
        raise ValueError("Sign in failed.")

    st.session_state.authenticated = True
    st.session_state.user_id = user.id
    st.session_state.user_email = user.email or email
    st.session_state.supabase_access_token = session.access_token
    st.session_state.supabase_refresh_token = session.refresh_token


def sign_out_user() -> None:
    client = _get_client()
    client.auth.sign_out()

    for key in [
        "authenticated",
        "user_id",
        "user_email",
        "supabase_access_token",
        "supabase_refresh_token",
        "program",
        "saved_program_id",
        "loaded_amrap_program_id",
        "loaded_amrap_results",
    ]:
        if key in st.session_state:
            del st.session_state[key]


# ------------------------------
# Serialization
# ------------------------------

def _scheme_to_dict(scheme: Scheme | None) -> dict[str, Any] | None:
    if scheme is None:
        return None
    return {
        "name": scheme.name,
        "reps": scheme.reps,
        "pct": scheme.pct,
    }


def _cycle_to_dict(cycle: Cycle) -> dict[str, Any]:
    return {
        "index": cycle.index,
        "type": cycle.type,
        "main": _scheme_to_dict(cycle.main),
        "supplemental": _scheme_to_dict(cycle.supplemental),
        "deload": _scheme_to_dict(cycle.deload),
    }


def _exercise_to_dict(exercise: Exercise) -> dict[str, Any]:
    return {
        "name": exercise.name,
        "training_max": exercise.training_max,
        "increment": exercise.increment,
    }


def program_to_dict(program: Program) -> dict[str, Any]:
    return {
        "name": program.name,
        "exercises": [_exercise_to_dict(ex) for ex in program.exercises],
        "cycles": [_cycle_to_dict(cycle) for cycle in program.cycles],
    }


def _scheme_from_dict(data: dict[str, Any] | None) -> Scheme | None:
    if data is None:
        return None
    return Scheme(
        name=data["name"],
        reps=data["reps"],
        pct=data["pct"],
    )


def _cycle_from_dict(data: dict[str, Any]) -> Cycle:
    main = _scheme_from_dict(data["main"])
    assert main is not None
    return Cycle(
        index=int(data["index"]),
        cycle_type=data["type"],
        main=main,
        supplemental=_scheme_from_dict(data.get("supplemental")),
        deload=_scheme_from_dict(data.get("deload")),
    )


def _exercise_from_dict(data: dict[str, Any]) -> Exercise:
    return Exercise(
        name=data["name"],
        training_max=float(data["training_max"]),
        increment=float(data["increment"]),
    )


def program_from_dict(data: dict[str, Any]) -> Program:
    return Program(
        name=data["name"],
        exercises=[_exercise_from_dict(ex) for ex in data["exercises"]],
        cycles=[_cycle_from_dict(c) for c in data["cycles"]],
    )


# ------------------------------
# Program persistence
# ------------------------------

def save_program(program: Program) -> int:
    client = _get_client()
    user_id = st.session_state.get("user_id")

    if not user_id:
        raise ValueError("You must be signed in to save a program.")

    created_at = datetime.now(timezone.utc).isoformat()
    payload = program_to_dict(program)

    client.table("programs").update({"is_current": False}).eq("user_id", user_id).eq(
        "is_current", True
    ).execute()

    start_date = st.session_state.get("start_date")

    program_insert = client.table("programs").insert(
        {
            "user_id": user_id,
            "name": program.name,
            "created_at": created_at,
            "is_current": True,
            "program_json": payload,
            "start_date": start_date.isoformat() if start_date is not None else None,
        }
    ).execute()

    if not program_insert.data:
        raise ValueError("Failed to save program.")

    program_id = int(program_insert.data[0]["id"])

    cycle_tm_rows: list[dict[str, Any]] = []
    for cycle in program.cycles:
        for exercise in program.exercises:
            cycle_tm = exercise.training_max + (cycle.index - 1) * exercise.increment
            cycle_tm_rows.append(
                {
                    "user_id": user_id,
                    "program_id": program_id,
                    "cycle_index": cycle.index,
                    "exercise_name": exercise.name,
                    "training_max": cycle_tm,
                    "base_training_max": exercise.training_max,
                    "increment_value": exercise.increment,
                }
            )

    if cycle_tm_rows:
        client.table("cycle_training_maxes").insert(cycle_tm_rows).execute()

    st.session_state.saved_program_id = program_id
    return program_id


def get_current_program_record() -> dict[str, Any] | None:
    client = _get_client()
    user_id = st.session_state.get("user_id")

    if not user_id:
        return None

    # First try the current program
    response = (
        client.table("programs")
        .select("*")
        .eq("user_id", user_id)
        .eq("is_current", True)
        .order("id", desc=True)
        .limit(1)
        .execute()
    )

    if response.data:
        return response.data[0]

    # Fallback: latest saved program for this user
    fallback_response = (
        client.table("programs")
        .select("*")
        .eq("user_id", user_id)
        .order("id", desc=True)
        .limit(1)
        .execute()
    )

    if fallback_response.data:
        record = fallback_response.data[0]
        client.table("programs").update({"is_current": True}).eq("id", record["id"]).execute()
        return record

    return None


def load_current_program_into_session() -> Program | None:
    record = get_current_program_record()
    if record is None:
        return None

    payload = record.get("program_json")
    if payload is None:
        return None

    if isinstance(payload, str):
        payload_dict = json.loads(payload)
    else:
        payload_dict = payload

    program = program_from_dict(payload_dict)
    st.session_state.program = program
    st.session_state.saved_program_id = int(record["id"])
    saved_start_date = record.get("start_date")
    if saved_start_date:
        st.session_state.start_date = date.fromisoformat(saved_start_date)

    return program


# ------------------------------
# AMRAP persistence
# ------------------------------

def estimate_training_max(weight_used: float, actual_reps: int) -> float:
    """
    Epley estimated 1RM, converted to TM at 90%.
    """
    estimated_1rm = weight_used * (1.0 + (actual_reps / 30.0))
    return estimated_1rm * 0.9


def get_amrap_results(program_id: int) -> dict[tuple[int, str, int, int], int]:
    client = _get_client()
    user_id = st.session_state.get("user_id")

    if not user_id:
        return {}

    response = (
        client.table("amrap_results")
        .select("cycle_index, exercise_name, step_index, set_index, actual_reps")
        .eq("user_id", user_id)
        .eq("program_id", program_id)
        .execute()
    )

    results: dict[tuple[int, str, int, int], int] = {}
    for row in response.data or []:
        key = (
            int(row["cycle_index"]),
            str(row["exercise_name"]),
            int(row["step_index"]),
            int(row["set_index"]),
        )
        results[key] = int(row["actual_reps"])

    return results


def replace_amrap_results(program_id: int, results: list[dict[str, Any]]) -> None:
    client = _get_client()
    user_id = st.session_state.get("user_id")

    if not user_id:
        raise ValueError("You must be signed in to save AMRAP results.")

    # Delete existing AMRAP rows for this program. estimated_training_maxes cascade via FK.
    client.table("amrap_results").delete().eq("user_id", user_id).eq(
        "program_id", program_id
    ).execute()

    if not results:
        return

    logged_at = datetime.now(timezone.utc).isoformat()
    amrap_rows: list[dict[str, Any]] = []

    for result in results:
        amrap_rows.append(
            {
                "user_id": user_id,
                "program_id": program_id,
                "cycle_index": result["cycle_index"],
                "exercise_name": result["exercise_name"],
                "step_index": result["step_index"],
                "set_index": result["set_index"],
                "planned_reps_label": result["planned_reps_label"],
                "weight_used": result["weight_used"],
                "actual_reps": result["actual_reps"],
                "logged_at": logged_at,
            }
        )

    insert_response = client.table("amrap_results").insert(amrap_rows).execute()
    inserted_rows = insert_response.data or []

    est_rows: list[dict[str, Any]] = []
    for inserted, original in zip(inserted_rows, results):
        est_rows.append(
            {
                "user_id": user_id,
                "amrap_result_id": int(inserted["id"]),
                "program_id": program_id,
                "cycle_index": original["cycle_index"],
                "exercise_name": original["exercise_name"],
                "estimated_training_max": estimate_training_max(
                    float(original["weight_used"]),
                    int(original["actual_reps"]),
                ),
                "formula_name": "Epley x 0.9",
                "created_at": logged_at,
            }
        )

    if est_rows:
        client.table("estimated_training_maxes").insert(est_rows).execute()


def get_estimated_training_maxes(program_id: int) -> list[dict[str, Any]]:
    client = _get_client()
    user_id = st.session_state.get("user_id")

    if not user_id:
        return []

    response = (
        client.table("estimated_training_maxes")
        .select("cycle_index, exercise_name, estimated_training_max, created_at")
        .eq("user_id", user_id)
        .eq("program_id", program_id)
        .order("created_at")
        .execute()
    )

    return response.data or []
