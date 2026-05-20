"""Client extensions for scalable clusters."""

from __future__ import annotations

import functools
import time
import uuid
from collections.abc import Iterable
from typing import Any

from dask.typing import no_default
from distributed import Client
from distributed.diagnostics.plugin import SchedulerPlugin

from .slurm import SlurmCluster
from .telemetry.runtime import task_context


class SlurmSchedulerPlugin(SchedulerPlugin):
    """Scheduler plugin placeholder used for Slurm-backed clients."""

    def __init__(self, cluster: Any) -> None:
        """Initialize the plugin.

        Parameters
        ----------
        cluster : Any
            Cluster reference used by distributed callbacks.
        """
        self.cluster = cluster
        super().__init__()

class ScalableClient(Client):
    """Client for submitting tasks to a Dask cluster. Inherits the dask
    client object. 

    Parameters
    ----------
    cluster : Cluster
        The cluster object to connect to for submitting tasks. 
    """

    def __init__(self, cluster: Any, *args: Any, **kwargs: Any) -> None:
        """Initialize a client bound to an existing cluster/scheduler."""
        super().__init__(address=cluster, *args, **kwargs)
        self._telemetry_store = None
        if isinstance(cluster, SlurmCluster):
            self.register_scheduler_plugin(SlurmSchedulerPlugin(None))

    def set_telemetry_store(self, store: Any) -> None:
        """Attach an active telemetry store for task lifecycle instrumentation."""
        self._telemetry_store = store

    def _record_future(
        self,
        *,
        future: Any,
        task_id: str,
        task_name: str,
        component: str | None,
        tag: str | None,
        function_name: str,
        requested_workers: int,
        submitted_at: float,
    ) -> None:
        store = self._telemetry_store
        if store is None:
            return

        store.record_task_submission(
            task_id=task_id,
            task_name=task_name,
            component=component,
            tag=tag,
            function_name=function_name,
            requested_workers=requested_workers,
        )

        def _on_done(done_future: Any) -> None:
            state = "succeeded"
            worker = getattr(done_future, "key", None)
            error_type = None
            error_message = None

            try:
                if done_future.cancelled():
                    state = "cancelled"
                else:
                    exc = done_future.exception()
                    if exc is not None:
                        state = "failed"
                        error_type = type(exc).__name__
                        error_message = str(exc)
            except Exception as callback_exc:  # pragma: no cover - defensive
                state = "failed"
                error_type = type(callback_exc).__name__
                error_message = str(callback_exc)

            _ = submitted_at
            store.record_task_result(
                task_id=task_id,
                task_name=task_name,
                component=component,
                tag=tag,
                function_name=function_name,
                requested_workers=requested_workers,
                state=state,
                worker=worker,
                error_type=error_type,
                error_message=error_message,
            )

        future.add_done_callback(_on_done)

    def submit(
        self,
        func: Any,
        *args: Any,
        tag: str | None = None,
        n: int = 1,
        **kwargs: Any,
    ) -> Any:
        """Submit a function to be ran by workers in the cluster.

        Parameters
        ----------
        func : function
            Function to be scheduled for execution.
        *args : tuple
            Optional positional arguments to pass to the function.
        tag : str (optional)
            User-defined tag for the container that can run func. If not 
            provided, func is assigned to be ran on a random container.
        n : int (default 1)
            Number of workers needed to run this task. Meant to be used with 
            tag. Multiple workers can be useful for application level 
            distributed computing.
        **kwargs : dict (optional)
            Optional key-value pairs to be passed to the function.

        Examples
        --------
        >>> c = client.submit(add, a, b)

        Returns
        -------
        Future
            Returns the future object that runs the function.

        Raises
        ------
        TypeError
            If 'func' is not callable, a TypeError is raised.
        ValueError
            If 'allow_other_workers'is True and 'workers' is None, a
            ValueError is raised.
        """
        resources = None
        if tag is not None:
            resources = {tag: n}

        task_name = str(kwargs.pop("_scalable_task_name", getattr(func, "__name__", "task")))
        function_name = getattr(func, "__qualname__", getattr(func, "__name__", repr(func)))

        @functools.wraps(func)
        def _wrapped(*wrapped_args: Any, **wrapped_kwargs: Any) -> Any:
            with task_context(task_name=task_name, component=tag, tag=tag):
                return func(*wrapped_args, **wrapped_kwargs)

        submitted_at = time.monotonic()
        future = super().submit(_wrapped, resources=resources, *args, **kwargs)

        self._record_future(
            future=future,
            task_id=uuid.uuid4().hex,
            task_name=task_name,
            component=tag,
            tag=tag,
            function_name=function_name,
            requested_workers=n,
            submitted_at=submitted_at,
        )
        return future
    
    def cancel(self, futures: Any, *args: Any, **kwargs: Any) -> Any:
        """
        Cancel running futures
        This stops future tasks from being scheduled if they have not yet run
        and deletes them if they have already run.  After calling, this result
        and all dependent results will no longer be accessible

        Parameters
        ----------
        futures : future | future, list
            One or more futures to cancel (as a list). 
        *args : tuple
            Positional arguments to pass to dask client's cancel method.
        **kwargs : dict
            Keyword arguments to pass to dask client's cancel method.
        """
        return super().cancel(futures, *args, **kwargs)
    
    def close(self, timeout: Any = no_default) -> Any:
        """Close this client

        Clients will also close automatically when your Python session ends

        Parameters
        ----------
        timeout : number
            Time in seconds after which to raise a
            ``dask.distributed.TimeoutError``

        """
        return super().close(timeout)
    
    def map(
        self,
        func: Any,
        *parameters: Iterable[Any],
        tag: str | None = None,
        n: int = 1,
        **kwargs: Any,
    ) -> Any:
        """Map a function on multiple sets of arguments to run the function
        multiple times with different inputs. 

        Parameters
        ----------
        func : function
            Function to be scheduled for execution. 
        parameters : list of lists
            Lists of parameters to be passed to the function. The first list
            should have the first parameter values, the second list should have
            the second parameter values, and so on. The lists should be of the
            same length.
        tag : str (optional)
            User-defined tag for the container that can run func. If not 
            provided, func is assigned to be ran on a random container.
        n : int (default 1)
            Number of workers needed to run this task. Meant to be used with 
            tag. Multiple workers can be useful for application level 
            distributed computing.
        *args : tuple
            Positional arguments to pass to dask client's map method.
        **kwargs : dict
            Keyword arguments to pass to dask client's map method.
        
        Examples
        --------
        >>> def add(a, b): ...
        >>> L = client.map(add, [[1, 2, 3], [4, 5, 6]])  

        Returns
        -------
        List of futures
            Returns a list of future objects, each for a separate run of the 
            function with the given parameters.
        """
        resources = None
        if tag is not None:
            resources = {tag: n}
        base_task_name = str(kwargs.pop("_scalable_task_name", getattr(func, "__name__", "task")))
        function_name = getattr(func, "__qualname__", getattr(func, "__name__", repr(func)))

        @functools.wraps(func)
        def _wrapped(*wrapped_args: Any, **wrapped_kwargs: Any) -> Any:
            with task_context(task_name=base_task_name, component=tag, tag=tag):
                return func(*wrapped_args, **wrapped_kwargs)

        submitted_at = time.monotonic()
        futures = super().map(_wrapped, *parameters, resources=resources, **kwargs)

        for index, future in enumerate(futures):
            self._record_future(
                future=future,
                task_id=uuid.uuid4().hex,
                task_name=f"{base_task_name}[{index}]",
                component=tag,
                tag=tag,
                function_name=function_name,
                requested_workers=n,
                submitted_at=submitted_at,
            )
        return futures
    
    def get_versions(
        self, check: bool = False, packages: list[str] | None = None
    ) -> Any:
        """Return version info for the scheduler, all workers and myself

        Parameters
        ----------
        check : bool
            Raise ValueError if all required & optional packages do not match.
            Default is False.
        packages : list
            Extra package names to check.

        Examples
        --------
        >>> c.get_versions()

        >>> c.get_versions(packages=['sklearn', 'geopandas'])
        """
        return super().get_versions(check, packages)
    
