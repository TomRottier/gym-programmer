from copy import deepcopy
from typing import Any, cast

from logic.program_templates import (
    PROGRAM_TEMPLATES,
    SUPPLEMENTAL_TEMPLATES,
    DELOAD_TEMPLATES,
)
from logic.program_models import (
    Program,
    Exercise,
    Cycle,
    Scheme,
    Rep,
)


def _scheme_from_template(name: str, template: dict[str, Any]) -> Scheme:
    """
    Convert a numeric template dict directly into a Scheme instance.
    Use this for main schemes and any fixed-pct schemes.
    """
    reps = cast(list[list[Rep]], deepcopy(template["reps"]))
    pct = cast(list[list[float]], deepcopy(template["pct"]))

    return Scheme(
        name=name,
        reps=reps,
        pct=pct,
    )


def _build_source_based_supplemental(
    name: str,
    template: dict[str, Any],
    main_scheme: Scheme,
) -> Scheme:
    """
    Build supplemental schemes like FSL / SSL.

    These templates define a single base step for reps, but must be expanded to
    the same number of steps as the main scheme.
    """
    source = cast(str, template["source"])
    base_reps_steps = cast(list[list[Rep]], deepcopy(template["reps"]))
    base_reps_step = base_reps_steps[0]
    supp_sets = len(base_reps_step)

    if source == "first_set":
        source_index = 0
    elif source == "second_set":
        source_index = 1
    else:
        raise ValueError(f"Unknown supplemental source: {source}")

    resolved_reps: list[list[Rep]] = []
    resolved_pct: list[list[float]] = []

    for main_pct_step in main_scheme.pct:
        ref_pct = float(main_pct_step[source_index])
        resolved_reps.append(deepcopy(base_reps_step))
        resolved_pct.append([ref_pct for _ in range(supp_sets)])

    return Scheme(
        name=name,
        reps=resolved_reps,
        pct=resolved_pct,
    )


def _build_supplemental_scheme(
    name: str,
    template: dict[str, Any],
    main_scheme: Scheme,
) -> Scheme:
    """
    Build either:
    - source-based supplemental (FSL / SSL)
    - fixed-pct supplemental (BBB)
    """
    source = cast(str | None, template.get("source"))

    if source in ("first_set", "second_set"):
        return _build_source_based_supplemental(name, template, main_scheme)

    return _scheme_from_template(name, template)


def generate_program(
    program_name: str,
    exercises_config: list[dict[str, Any]],
    cycles_config: list[dict[str, Any]],
) -> Program:
    """
    Assemble a Program object from UI configs.
    """
    exercises: list[Exercise] = []
    for ex in exercises_config:
        exercises.append(
            Exercise(
                name=cast(str, ex["name"]),
                training_max=float(ex["tm"]),
                increment=float(ex["increment"]),
            )
        )

    cycles: list[Cycle] = []

    for idx, cycle_cfg in enumerate(cycles_config, start=1):
        main_key = cast(str, cycle_cfg["main"])
        main_template = PROGRAM_TEMPLATES[main_key]
        main_scheme = _scheme_from_template(main_key, main_template)

        supplemental_scheme: Scheme | None = None
        supp_key = cast(str, cycle_cfg["supplemental"])
        if supp_key != "None":
            supp_template = SUPPLEMENTAL_TEMPLATES[supp_key]
            assert supp_template is not None
            supplemental_scheme = _build_supplemental_scheme(
                supp_key,
                supp_template,
                main_scheme,
            )

        deload_scheme: Scheme | None = None
        if bool(cycle_cfg.get("deload")):
            deload_key = cast(str | None, cycle_cfg.get("deload_type"))
            if deload_key is None:
                raise ValueError("Cycle marked as deload=True but deload_type is None")
            deload_template = DELOAD_TEMPLATES[deload_key]
            deload_scheme = _scheme_from_template(deload_key, deload_template)

        cycles.append(
            Cycle(
                index=idx,
                cycle_type=cast(str, cycle_cfg["type"]).lower(),
                main=main_scheme,
                supplemental=supplemental_scheme,
                deload=deload_scheme,
            )
        )

    return Program(
        name=program_name,
        exercises=exercises,
        cycles=cycles,
    )
