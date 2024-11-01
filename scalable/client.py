from dask.typing import no_default
from distributed import Client
from distributed.diagnostics.plugin import SchedulerPlugin

from .common import logger
from .slurm import SlurmCluster


class SlurmSchedulerPlugin(SchedulerPlugin):
    def __init__(self, cluster):
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

    def __init__(self, cluster, *args, **kwargs):
        super().__init__(address = cluster, *args, **kwargs)
        if isinstance(cluster, SlurmCluster):
            self.register_scheduler_plugin(SlurmSchedulerPlugin(None))
    
    def submit(self, func, *args, tag=None, n=1, **kwargs):
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
        return super().submit(func, resources=resources, *args, **kwargs)
    
    def cancel(self, futures, *args, **kwargs):
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
    
    def close(self, timeout=no_default):
        """Close this client

        Clients will also close automatically when your Python session ends

        Parameters
        ----------
        timeout : number
            Time in seconds after which to raise a
            ``dask.distributed.TimeoutError``

        """
        return super().close(timeout)
    
    def map(self, func, parameters, tag, n, *args, **kwargs):
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
        return super().map(func=func, iterables=parameters, resources=resources, *args, **kwargs)
    
    def get_versions(self, check=False, packages = None):
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
    