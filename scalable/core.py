from contextlib import suppress
import os
import re
import shlex
import sys
import abc
import tempfile
import threading
import time
import copy
import warnings
import asyncio

from dask.utils import parse_bytes

from distributed.core import Status
from distributed.deploy.spec import ProcessInterface, SpecCluster
from distributed.scheduler import Scheduler
from distributed.security import Security
from distributed.utils import NoOpAwaitable

from .utilities import *
from .support import *

from .common import logger

DEFAULT_WORKER_COMMAND = "distributed.cli.dask_worker"

# The length of the period (in mins) to check and account for dead workers
CHECK_DEAD_WORKER_PERIOD = 1

job_parameters = """
    cpus : int
        Akin to the number of cores the current job should have available.
    memory : str
        Amount of memory the current job should have available.
    nanny : bool
        Whether or not to start a nanny process.
    interface : str
        Network interface like 'eth0' or 'ib0'. This will be used both for the
        Dask scheduler and the Dask workers interface. If you need a different
        interface for the Dask scheduler you can pass it through
        the ``scheduler_options`` argument: ``interface=your_worker_interface, 
        scheduler_options={'interface': your_scheduler_interface}``.
    death_timeout : float
        Seconds to wait for a scheduler before closing workers
    local_directory : str
        Dask worker local directory for file spilling.
    worker_command : list
        Command to run when launching a worker. Defaults to 
        "distributed.cli.dask_worker"
    worker_extra_args : list
        Additional arguments to pass to `dask-worker`
    python : str
        Python executable used to launch Dask workers.
        Defaults to the Python that is submitting these jobs
    hardware : HardwareResources
        A shared object containing the hardware resources available to the
        cluster.
    tag : str
        The tag or the container type of the worker to be launched.
    container : Container
        The container object containing the information about launching the 
        worker.
    launched : list
        A list of launched workers which is shared across all workers and the 
        cluster object to keep track of the workers that have been launched.
    
""".strip()


cluster_parameters = """
    silence_logs : str
        Log level like "debug", "info", or "error" to emit here if the
        scheduler is started locally
    asynchronous : bool
        Whether or not to run this cluster object with the async/await syntax
    name : str
        The name of the cluster, which would also be used to name workers. 
        Defaults to class name. 
    scheduler_options : dict
        Used to pass additional arguments to Dask Scheduler. For example use
        ``scheduler_options={'dashboard_address': ':12435'}`` to specify which
        port the web dashboard should use or 
        ``scheduler_options={'host': 'your-host'}`` to specify the host the Dask 
        scheduler should run on. See :class:`distributed.Scheduler` for more 
        details.
    scheduler_cls : type
        Changes the class of the used Dask Scheduler. Defaults to  Dask's
        :class:`distributed.Scheduler`.
    shared_temp_directory : str
        Shared directory between scheduler and worker (used for example by 
        temporary security certificates) defaults to current working directory 
        if not set.
    comm_port : int
        The network port on which the cluster can contact the host 
    config_overwrite : bool
        Remake model config_dict with available containers and their paths only. 
        Defaults to False.
    logs_location : str
        The location to store worker logs. Default to the logs folder in the 
        current directory.

""".strip()


class Job(ProcessInterface, abc.ABC):
    """ Base class to launch Dask workers on Job queues

    This class should not be used directly, use a class appropriate for
    your queueing system (e.g. PBScluster or SLURMCluster) instead.

    Parameters
    ----------
    {job_parameters}

    Attributes
    ----------
    cancel_command: str
        Abstract attribute for job scheduler cancel command,
        should be overridden

    Methods
    -------
    close()
        Close the current worker

    See Also
    --------
    SLURMCluster
    """.format(job_parameters=job_parameters)

    # Following class attributes should be overridden by extending classes.
    cancel_command = None
    job_id_regexp = r"(?P<job_id>\d+)"

    @abc.abstractmethod
    def __init__(
        self,
        scheduler=None,
        name=None,
        cpus=None,
        memory=None,
        nanny=True,
        protocol=None,
        security=None,
        interface=None,
        death_timeout=None,
        local_directory=None,
        worker_command=DEFAULT_WORKER_COMMAND,
        worker_extra_args=[],
        python=sys.executable,
        comm_port=None,
        hardware=None, 
        tag=None,
        container=None,
        launched=None,
        shared_lock=None,
    ):
        """
        Parameters
        ----------
        {job_parameters}
        """.format(job_parameters=job_parameters)
        
        if container is None:
            raise ValueError(
                "Container cannot be None. The information about launching the worker "
                "is located inside the container object."
            )
        
        if launched is None:
            raise ValueError(
                "Launched list is None. Every worker needs a launched list for the cluster "
                "to be able to monitor the workers effectively. Please try again."
            )

        if tag is None:
            raise ValueError(
                "Each worker is required to have a tag. Please try again."
            )
        
        if hardware is None:
            raise ValueError(
                "No hardware resources object. Please try again."
            )
        
        if comm_port is None:
            raise ValueError(
                "Communicator port not given. You must specify the communicator port "
                "for the workers to be launched. Please try again"
            )
        
        if security is not None:
            raise ValueError(
                "Security is not supported. Please try again."
            )
        
        if shared_lock is None:
            logger.warning("No shared async lock provided. This could lead to race conditions.")
        
        self.comm_port = comm_port
        self.tag = tag
        self.launched = launched
        self.container = container
        self.scheduler = scheduler
        self.hardware = hardware
        self.name = name
        self.shared_lock = shared_lock
        self.job_id = None

        super().__init__()

        container_info = self.container.get_info_dict()
        
        if cpus is None:
            cpus = container_info['CPUs']
        if memory is None:
            memory = container_info['Memory']
        self.cpus = cpus
        self.memory = memory
        processes = 1        

        if interface and "--interface" not in worker_extra_args:
            worker_extra_args.extend(["--interface", interface])
        if protocol and "--protocol" not in worker_extra_args:
            worker_extra_args.extend(["--protocol", protocol])

        # Keep information on process, cores, and memory, for use in subclasses
        self.worker_memory = parse_bytes(self.memory) if self.memory is not None else None
        
        # dask-worker command line build
        dask_worker_command = "%(python)s -m %(worker_command)s" % dict(
            python="python3",
            worker_command=worker_command
        )

        command_args = [dask_worker_command, self.scheduler]

        # common
        command_args.extend(["--name", self.name])
        command_args.extend(["--nthreads", self.cpus])
        command_args.extend(["--memory-limit", f"{self.worker_memory}GB"])

        #  distributed.cli.dask_worker specific
        if worker_command == "distributed.cli.dask_worker":
            command_args.extend(["--nworkers", processes])
            command_args.extend(["--nanny" if nanny else "--no-nanny"])

        if death_timeout is not None:
            command_args.extend(["--death-timeout", death_timeout])
        if local_directory is not None:
            command_args.extend(["--local-directory", local_directory])
        if tag is not None:
            command_args.extend(["--resources", f"\'{tag}\'=1"])
        if worker_extra_args is not None:
            command_args.extend(worker_extra_args)
        
        self.command_args = command_args

        self._command_template = " ".join(map(str, command_args))
    
    async def _run_command(self, command):
        out = await self._call(command, self.comm_port)
        return out

    def _job_id_from_submit_output(self, out):
        match = re.search(self.job_id_regexp, out)
        if match is None:
            msg = (
                "Could not parse job id from submission command "
                "output.\nJob id regexp is {!r}\nSubmission command "
                "output is:\n{}".format(self.job_id_regexp, out)
            )
            raise ValueError(msg)

        job_id = match.groupdict().get("job_id")
        if job_id is None:
            msg = (
                "You need to use a 'job_id' named group in your regexp, e.g. "
                "r'(?P<job_id>\\d+)'. Your regexp was: "
                "{!r}".format(self.job_id_regexp)
            )
            raise ValueError(msg)

        return job_id

    async def close(self):
        """
        Close the current worker. 
        """
        logger.debug("Stopping worker: %s job: %s", self.name, self.job_id)
        await self._close_job(self.job_id, self.cancel_command, self.comm_port)

    @classmethod
    async def _close_job(cls, job_id, cancel_command, port):
        with suppress(RuntimeError):  # deleting job when job already gone
            await cls._call(shlex.split(cancel_command) + [job_id], port)
        logger.debug("Closed job %s", job_id)

    @staticmethod
    async def _call(cmd, port):
        """Call a command using asyncio.create_subprocess_exec.

        This centralizes calls out to the command line, providing consistent
        outputs, logging, and an opportunity to go asynchronous in the future.

        Parameters
        ----------
        cmd: List(str)
            A command, each of which is a list of strings to hand to
            asyncio.create_subprocess_exec
        port: int
            A port number between 0-65535 signifying the port that the 
            communicator program is running on the host

        Examples
        --------
        >>> self._call(['ls', '/foo'], 1919)

        Returns
        -------
        str
            The stdout produced by the command, as string.

        Raises
        ------
        RuntimeError if the command exits with a non-zero exit code
        """
        cmd = list(map(str, cmd))
        cmd += "\n"
        cmd_str = " ".join(cmd)
        logger.info(
            "Executing the following command to command line\n{}".format(cmd_str)
        )

        proc = await get_cmd_comm(port=port)
        if proc.returncode is not None:
            raise RuntimeError(
                "Communicator exited prematurely.\n"
                "Exit code: {}\n"
                "Command:\n{}\n"
                "stdout:\n{}\n"
                "stderr:\n{}\n".format(proc.returncode, cmd_str, proc.stdout, proc.stderr)
            )
        send = bytes(cmd_str, encoding='utf-8')
        out, _ = await proc.communicate(input=send)
        await proc.wait()
        out = out.decode()
        out = out.strip()
        return out


class JobQueueCluster(SpecCluster):
    __doc__ = """
    Deploy Dask on a Job queuing system

    This is a superclass, and is rarely used directly.  It is more common to
    use an object like SLURMCluster others.

    However, it can be used directly if you have a custom ``Job`` type.
    This class relies heavily on being passed a ``Job`` type that is able to
    launch one Job on a job queueing system.

    Parameters
    ----------
    job_cls : Job
        A class that can be awaited to ask for a single Job
    {cluster_parameters}
    """.format(
        cluster_parameters=cluster_parameters
    )

    def __init__(
        self,
        job_cls: Job = None,
        # Cluster keywords
        loop=None,
        shared_temp_directory=None,
        silence_logs="error",
        name=None,
        asynchronous=False,
        # Scheduler-only keywords
        dashboard_address=None,
        host=None,
        scheduler_options={},
        scheduler_cls=Scheduler,  # Use local scheduler for now
        # Options for both scheduler and workers
        interface=None,
        protocol=None,
        # Custom keywords
        config_overwrite=True,
        comm_port=None,
        logs_location=None,
        **job_kwargs
    ):
        
        if comm_port is None:
            raise ValueError(
                "Communicator port not given. You must specify the communicator port "
                "for the workers to be launched. Please try again"
            )

        if job_cls is not None:
            self.job_cls = job_cls

        if self.job_cls is None:
            raise ValueError(
                "You need to specify a Job type. Two cases:\n"
                "- you are inheriting from JobQueueCluster (most likely): you need to add a 'job_cls' class variable "
                "in your JobQueueCluster-derived class {}\n"
                "- you are using JobQueueCluster directly (less likely, only useful for tests): "
                "please explicitly pass a Job type through the 'job_cls' parameter.".format(
                    type(self)
                )
            )

        if dashboard_address is not None:
            raise ValueError(
                "Please pass 'dashboard_address' through 'scheduler_options': use\n"
                'cluster = {0}(..., scheduler_options={{"dashboard_address": ":12345"}}) rather than\n'
                'cluster = {0}(..., dashboard_address="12435")'.format(
                    self.__class__.__name__
                )
            )

        if host is not None:
            raise ValueError(
                "Please pass 'host' through 'scheduler_options': use\n"
                'cluster = {0}(..., scheduler_options={{"host": "your-host"}}) rather than\n'
                'cluster = {0}(..., host="your-host")'.format(self.__class__.__name__)
            )
        
        security = None

        if protocol is None and security is not None:
            protocol = "tls://"
        
        self.comm_port = comm_port
        self.hardware = HardwareResources()
        self.shared_lock = asyncio.Lock()
        self.launched = []
        self.status = Status.created
        self.specifications = {}
        self.model_configs = ModelConfig(path_overwrite=config_overwrite)
        self.exited = False
        
        default_scheduler_options = {
            "protocol": protocol,
            "dashboard_address": ":8787",
            "security": security,
        }

        # scheduler_options overrides parameters common to both workers and scheduler
        scheduler_options = dict(default_scheduler_options, **scheduler_options)

        # Use the same network interface as the workers if scheduler ip has not
        # been set through scheduler_options via 'host' or 'interface'
        if "host" not in scheduler_options and "interface" not in scheduler_options:
            scheduler_options["interface"] = interface

        scheduler = {
            "cls": scheduler_cls,
            "options": scheduler_options,
        }

        
        self.logs_location = logs_location
        if self.logs_location is None:
            directory_name = self.job_cls.__name__.replace("Job", "") + "Cluster"
            self.logs_location = create_logs_folder("logs", directory_name)

        self.shared_temp_directory = shared_temp_directory
        
        job_kwargs["interface"] = interface
        job_kwargs["protocol"] = protocol
        job_kwargs["security"] = security
        job_kwargs["comm_port"] = self.comm_port
        job_kwargs["hardware"] = self.hardware
        job_kwargs["shared_lock"] = self.shared_lock
        job_kwargs["logs_location"] = self.logs_location
        job_kwargs["launched"] = self.launched
        self._job_kwargs = job_kwargs

        worker = {"cls": self.job_cls, "options": self._job_kwargs}

        self.containers = {}

        super().__init__(
            scheduler=scheduler,
            worker=worker,
            security=security,
            loop=loop,
            silence_logs=silence_logs,
            asynchronous=asynchronous,
            name=name,
        )

        # timerThread = threading.Thread(target=self._check_dead_workers)
        # timerThread.daemon = True
        self.thread_lock = threading.Lock()
        # timerThread.start()
        # self.loop.add_callback(self._check_dead_workers)
        

    async def remove_launched_worker(self, worker):
        print(self.shared_lock)
        async with self.shared_lock:
            self.launched.remove(worker)

    def add_worker(self, tag=None, n=0):
        """Add workers to the cluster. 
        
        This is also the function which syncs the cluster to recognize any 
        dead, expired, or revoked workers. Cleaning up such workers and 
        relaunching them is done here. Only cleanup and replacement of dead 
        workers is performed when called with no or defalt arguments. 

        Parameters
        ----------
        tag: str
            The tag or the container type of the worker to be launched 
            usually associated with the programs stored in the container.
            Examples could include "gcam" for the gcam container and 
            "stitches" for the stitches container.
        n: int
            The number of workers desired to be launched with the given tag. 

        Examples
        --------
        >>> cluster.add_worker("gcam", 4)
        
        """
        with self.thread_lock:
            if self.exited:
                return
            if tag is not None and tag not in self.containers:
                logger.error(f"The tag ({tag}) given is not a recognized tag for any of the containers. "
                            "Please add a container with this tag to the cluster by using "
                            "add_container() and try again.")
                return
            tags = [tag for _ in range(n)]
            current_workers = [worker for worker in self.workers.keys()]
            to_relaunch = [worker for worker in self.launched if worker[0] not in current_workers]
            for worker in to_relaunch:
                del self.worker_spec[worker[0]]
                asyncio.run(self.remove_launched_worker(worker))
            tags.extend([worker[1] for worker in to_relaunch])
            if self.status not in (Status.closing, Status.closed):
                for tag in tags:
                    new_worker = self.new_worker_spec(tag)
                    self.worker_spec.update(dict(new_worker))
                self.loop.add_callback(self._correct_state)
        if self.asynchronous:
            return NoOpAwaitable() 
        
    async def _check_dead_workers(self):
        """Periodically check for dead workers. 
        
        This function essentially calls self.add_worker() with default 
        parameters which only syncs the cluster to the current state of 
        the workers. Any dead workers may be relaunched. 
        """
        next_call = time.time()
        while not self.exited:
            self.add_worker()
            next_call = next_call + (60 * CHECK_DEAD_WORKER_PERIOD)
            time.sleep(next_call - time.time())

    def add_container(self, tag, dirs, path=None, cpus=None, memory=None):
        """Add containers to enable them launching as workers. 
        
        The required dependencies for the workers are assumed to be in the 
        container at the given (or stored) path. The informaton given about the 
        container will be written to the config_dict. 

        Parameters
        ----------
        tag : str
            The tag or the container type of the worker to be launched. 
            Example could include "gcam" for the gcam container and "stitches" 
            for the stitches container.
        dirs : dict
            A dictionary of path-on-worker:path-on-host pairs where 
            path-on-worker is a path mounted to path-on-host. When the worker
            tries to access path-on-worker, it essentially accesssing 
            path-on-work. List of volume/bind mounts.
        path : str
            The path at which the container is located at
        cpus : int
            The number of cpus/processor cores to be reserved for this container
        memory : str
            The amount of memory to be reserved for this container
        """
        tag = tag.lower()
        self.model_configs.update_dict(tag, 'Dirs', dirs)
        if path:
            self.model_configs.update_dict(tag, 'Path', path)
        if cpus:
            self.model_configs.update_dict(tag, 'CPUs', cpus)
        if memory:
            self.model_configs.update_dict(tag, 'Memory', memory)
        self.containers[tag] = Container(name=tag, spec_dict=self.model_configs.config_dict[tag])

    def _new_worker_name(self, worker_number):
        """Returns new worker name.

        Base worker name on cluster name. This makes it easier to use job
        arrays within Dask-Jobqueue.

        Parameters
        ----------
        worker_number : int
           Worker number
        
        Returns
        -------
        str
           New worker name
        """
        return "{cluster_name}-{worker_number}".format(
            cluster_name=self._name, worker_number=worker_number
        )
    
    def new_worker_spec(self, tag):
        """Return name and spec for the next worker

        Parameters
        ----------
        tag : str
           tag for the workers

        Returns
        -------
        dict
            Dictionary containing the name and spec for the next worker
        """
        if tag not in self.specifications:
            self.specifications[tag] = copy.copy(self.new_spec)
            if tag not in self.containers:
                raise ValueError(f"The tag ({tag}) given is not a recognized tag for any of the containers."
                                "Please add a container with this tag to the cluster by using"
                                "add_container() and try again. User error at this point shouldn't happen."
                                "Likely a bug.")
            self.specifications[tag]["options"] = copy.copy(self.new_spec["options"])
            self.specifications[tag]["options"]["container"] = self.containers[tag]
            self.specifications[tag]["options"]["tag"] = tag
        self._i += 1
        new_worker_name = f"{self._new_worker_name(self._i)}-{tag}"
        while new_worker_name in self.worker_spec:
            self._i += 1
            new_worker_name = f"{self._new_worker_name(self._i)}-{tag}"

        return {new_worker_name: self.specifications[tag]}

    def scale(self, n=None, jobs=0, memory=None, cores=None):
        """Scale cluster to specified configurations.

        Parameters
        ----------
        n : int
           Target number of workers
        jobs : int
           Target number of jobs
        memory : str
           Target amount of memory
        cores : int
           Target number of cores

        """
        logger.warn("This function must only be called internally on exit. " +
                    "Any calls made explicity or during execution can result " +
                    "in undefined behavior. " + "If called accidentally, an " +
                    "immediate shutdown and restart of the cluster is recommended.")
        self.exited = True
        return super().scale(jobs, memory=memory, cores=cores)
    
    
