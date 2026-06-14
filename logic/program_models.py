from typing import List, Optional, Union


Rep = Union[int, str]


class Scheme:
    """
    A Scheme represents a full progression.

    reps and pct are lists of lists:
      - outer list = progression step (e.g. week)
      - inner list = sets within that step
    """

    def __init__(
        self,
        name: str,
        reps: List[List[Rep]],
        pct: List[List[float]],
    ):
        assert len(reps) == len(pct), "Reps and pct must have same number of steps"

        for r, p in zip(reps, pct):
            assert len(r) == len(p), "Each step must have matching reps and pct"

        self.name = name
        self.reps = reps
        self.pct = pct

    @property
    def num_steps(self) -> int:
        return len(self.reps)

    def sets_in_step(self, step_index: int) -> int:
        return len(self.reps[step_index])


class Exercise:
    """
    Represents a lift with its own Training Max and progression rule.
    """

    def __init__(self, name: str, training_max: float, increment: float):
        self.name = name
        self.training_max = training_max
        self.increment = increment

    def weight_for_pct(self, pct: float) -> float:
        return self.training_max * pct

    def increment_tm(self):
        self.training_max += self.increment


class Cycle:
    """
    A Cycle assigns schemes to roles.
    """

    def __init__(
        self,
        index: int,
        cycle_type: str,              # leader | anchor
        main: Scheme,
        supplemental: Optional[Scheme],
        deload: Optional[Scheme],
    ):
        self.index = index
        self.type = cycle_type
        self.main = main
        self.supplemental = supplemental
        self.deload = deload

    def has_deload(self) -> bool:
        return self.deload is not None


class Program:
    """
    Top-level container for exercises and cycles.
    """

    def __init__(
        self,
        name: str,
        exercises: List[Exercise],
        cycles: List[Cycle],
    ):
        self.name = name
        self.exercises = exercises
        self.cycles = cycles

    def iter_cycles(self):
        return self.cycles

    def iter_exercises(self):
        return self.exercises
