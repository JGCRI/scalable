from collections.abc import Awaitable
from distributed import Scheduler, Client
from distributed.diagnostics.plugin import SchedulerPlugin


from .common import logger
from .slurm import SlurmJob, SlurmCluster

class SlurmSchedulerPlugin(SchedulerPlugin):

    def __init__(self, cluster):
        self.cluster = cluster
        super().__init__()    
    

class ScalableClient(Client):

    def __init__(self, cluster, *args, **kwargs):
        super().__init__(address = cluster, *args, **kwargs)
        if isinstance(cluster, SlurmCluster):
            self.register_scheduler_plugin(SlurmSchedulerPlugin(None))
    
    def submit(
        self,
        func,
        *args,
        key=None,
        workers=None,
        tag=None,
        n=1,
        retries=None,
        priority=0,
        fifo_timeout="100 ms",
        allow_other_workers=False,
        actor=False,
        actors=False,
        pure=True,
        **kwargs,
    ):
        """Submit a function application to the scheduler

        Parameters
        ----------
        func : callable
            Callable to be scheduled as ``func(*args,**kwargs)``. If ``func`` 
            returns a coroutine, it will be run on the main event loop of a 
            worker. Otherwise ``func`` will be run in a worker's task executor 
            pool (see ``Worker.executors`` for more information.)
        \*args : tuple
            Optional positional arguments
        key : str
            Unique identifier for the task.  Defaults to function-name and hash
        workers : string or iterable of strings
            A set of worker addresses or hostnames on which computations may be
            performed. Leave empty to default to all workers (common case)
        tag : str (optional)
            User-defined tag for the container that can run func. If not 
            provided, func is assigned to be ran on a random container.
        n : int (default 1)
            Number of workers needed to run this task. Meant to be used with 
            tag. Multiple workers can be useful for application level 
            distributed computing.
        retries : int (default to 0)
            Number of allowed automatic retries if the task fails
        priority : Number
            Optional prioritization of task.  Zero is default.
            Higher priorities take precedence
        fifo_timeout : str timedelta (default '100ms')
            Allowed amount of time between calls to consider the same priority
        allow_other_workers : bool (defaults to False)
            Used with ``workers``. Indicates whether or not the computations
            may be performed on workers that are not in the `workers` set(s).
        actor : bool (default False)
            Whether this task should exist on the worker as a stateful actor.
        actors : bool (default False)
            Alias for `actor`
        pure : bool (defaults to True)
            Whether or not the function is pure.  Set ``pure=False`` for
            impure functions like ``np.random.random``. Note that if both
            ``actor`` and ``pure`` kwargs are set to True, then the value
            of ``pure`` will be reverted to False, since an actor is stateful.
        \*\*kwargs : dict
            Optional key-value pairs to be passed to the function.

        Examples
        --------
        >>> c = client.submit(add, a, b)

        Notes
        -----
        The current implementation of a task graph resolution searches for 
        occurrences of ``key`` and replaces it with a corresponding ``Future`` 
        result. That can lead to unwanted substitution of strings passed as 
        arguments to a task if these strings match some ``key`` that already 
        exists on a cluster. To avoid these situations it is required to use 
        unique values if a ``key`` is set manually. See 
        https://github.com/dask/dask/issues/9969 to track progress on resolving 
        this issue.

        Returns
        -------
        Future
            If running in asynchronous mode, returns the future. Otherwise
            returns the concrete value

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
        return super().submit(func, 
                              *args, 
                              key=key, 
                              workers=workers, 
                              resources=resources, 
                              retries=retries, 
                              priority=priority, 
                              fifo_timeout=fifo_timeout, 
                              allow_other_workers=allow_other_workers, 
                              actor=actor, 
                              actors=actors, 
                              pure=False, 
                              **kwargs)

    
    
    
    
        
