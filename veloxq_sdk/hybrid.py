"""Hybrid workflow integration for VeloxQ solvers.

This module exposes a ``Runnable`` compatible sampler that can be used inside
``dwave-hybrid`` workflows. It wraps any ``veloxq_sdk`` solver and returns a
``dimod.SampleSet`` so that VeloxQ can participate in Hybrid flows alongside
other Ocean components.
"""
from __future__ import annotations

import typing as t

try:  # Soft dependency to keep the core SDK lightweight.
    from hybrid.core import Runnable, State, traits
except ImportError as exc:  # pragma: no cover - import guard
    msg = (
        'dwave-hybrid is required for hybrid workflows. Install '
        '"dwave-hybrid" or the "veloxq_sdk[hybrid]" extra.'
    )
    raise ImportError(msg) from exc

from veloxq_sdk.api.solvers import BaseSolver, VeloxQSolver


class VeloxHybridRunnable(traits.ProblemSampler, traits.SISO, Runnable):
    """Runnable wrapper to use VeloxQ solvers inside Hybrid workflows.

    This ``Runnable`` reads a :class:`dimod.BinaryQuadraticModel` from the input
    state field (by default, ``'problem'``), submits it to a VeloxQ solver, and
    writes the resulting :class:`dimod.SampleSet` to the output state field
    (by default, ``'samples'``).
    """

    solver: BaseSolver
    input: str
    output: str

    def __init__(
        self,
        solver: BaseSolver | None = None,
        *,
        fields: t.Set[str] | None = None,
        **runopts,
    ) -> None:
        """Initialize the VeloxHybridRunnable.

        Parameters
        ----------
        solver:
            The VeloxQ solver instance to use. Defaults to :class:`VeloxQSolver`.
        fields:
            The set of state fields to read the problem from and write samples to.
            Defaults to ``{'problem', 'samples'}``.
        **runopts:
            Extra options forwarded to ``BaseSolver.sample``.

        """
        self.solver = solver or VeloxQSolver()
        if not isinstance(self.solver, BaseSolver):
            msg = f"solver must be a 'BaseSolver'; got {type(self.solver)!r}."
            raise TypeError(msg)

        try:
            self.input, self.output = fields or {'problem', 'samples'}
        except ValueError as exc:
            msg = ('fields must contain exactly two elements: '
                   'input and output field names.')
            raise ValueError(msg) from exc

        super().__init__(**runopts)

    def next(self, state: State, **runopts) -> State:
        """Submit the state's problem to VeloxQ and return an updated state."""
        instance = state[self.input]

        result = self.solver.sample(
            instance,
            name=runopts.get('name'),
            force=runopts.get('force', False),
            problem=runopts.get('problem'),
        )

        return state.updated(**{self.output: result})
