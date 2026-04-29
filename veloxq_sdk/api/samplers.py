"""VeloxQ API Samplers Module.

This module provides classes and methods for creating and managing samplers instances
in the VeloxQ API. Samplers included here are responsible for running Solvers with
specified initial states, also implementing hybrid.Runnable.

"""
import hybrid

from dimod.sampleset import SampleSet

from veloxq_sdk.api.backends import BaseBackend
from veloxq_sdk.api.solvers import VeloxQParameters, VeloxQSolver, SBMSolver


class SolverWrappingSampler(hybrid.traits.ProblemSampler, hybrid.traits.SISO, hybrid.Runnable):
    """Adapt a `BaseSolver` to the `hybrid.Runnable`/ SISO sampler interface.

    The wrapped solver samples the problem stored in the configured input field
    and writes the result to the configured output field.
    """

    def __init__(
        self,
        solver: BaseSolver,
        *,
        fields: tuple[str, str] | None = None,
        **sample_kwargs,
    ):
        """Initialize the sampler.

        Args:
            solver: Solver instance to wrap.
            fields: Optional ``(input, output)`` state fields. Defaults to
                ``("problem", "samples")``.
            **sample_kwargs: Forwarded to `hybrid.Runnable`.
        """
        super().__init__(**sample_kwargs)
        fields = fields or ('problem', 'samples')
        self.input, self.output = fields
        self.solver = solver


    def next(self, state: hybrid.State, **sample_kwargs) -> hybrid.State:
        """Run the wrapped solver and return the updated hybrid state."""
        instance = state[self.input]
        init_state = state[self.output]
        if not isinstance(init_state, SampleSet):
            init_state = None
        result = self.solver.sample(
            instance,
            name=sample_kwargs.get('name'),
            force=sample_kwargs.get('force', False),
            init_state=init_state,
            problem=sample_kwargs.get('problem'),
        )
        if len(result) > len(init_state):
            result = result.slice(0, len(init_state), sorted_by='energy')
        result = result.relabel_variables(
            dict(zip(result.variables, init_state.variables)),
            inplace=False,
        )
        return state.updated(**{self.output: result})


class VeloxQSampler(SolverWrappingSampler):
    """`SolverWrappingSampler` using `VeloxQSolver` by default."""

    solver_cls: type[BaseSolver] = VeloxQSolver

    def __init__(
        self,
        *args,
        parameters: VeloxQParameters | None = None,
        backend: BaseBackend | None = None,
        fields: tuple[str, str] | None = None,
        **sample_kwargs,
    ):
        """Initialize a VeloxQ-backed hybrid sampler.

        Args:
            *args: Forwarded to `SolverWrappingSampler`.
            parameters: Optional solver parameters. Defaults to the solver
                class field default.
            backend: Optional solver backend. Defaults to the solver class
                field default.
            fields: Optional ``(input, output)`` state fields.
            **sample_kwargs: Forwarded to `SolverWrappingSampler`.
        """
        parameters = parameters or self.solver_cls.model_fields["parameters"].default_factory()
        backend = backend or self.solver_cls.model_fields["backend"].default
        super().__init__(
            self.solver_cls(parameters=parameters, backend=backend),
            *args,
            fields=fields,
            **sample_kwargs
        )


class SBMSampler(SolverWrappingSampler):
    """`SolverWrappingSampler` using `SBMSolver` by default."""

    solver_cls: type[BaseSolver] = SBMSolver

    def __init__(
        self,
        *args,
        parameters: VeloxQParameters | None = None,
        backend: BaseBackend | None = None,
        fields: tuple[str, str] | None = None,
        **sample_kwargs,
    ):
        """Initialize an SBM-backed hybrid sampler.

        Args:
            *args: Forwarded to `SolverWrappingSampler`.
            parameters: Optional solver parameters. Defaults to the solver
                class field default.
            backend: Optional solver backend. Defaults to the solver class
                field default.
            fields: Optional ``(input, output)`` state fields.
            **sample_kwargs: Forwarded to `SolverWrappingSampler`.
        """
        parameters = parameters or self.solver_cls.model_fields["parameters"].default_factory()
        backend = backend or self.solver_cls.model_fields["backend"].default
        super().__init__(
            self.solver_cls(parameters=parameters, backend=backend),
            *args,
            fields=fields,
            **sample_kwargs
        )
