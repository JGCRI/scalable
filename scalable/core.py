from contextlib import contextmanager, suppress
import logging
import os
import re
import shlex
import sys
import abc
import tempfile
import copy
import warnings


from dask.utils import parse_bytes

from distributed.core import Status
from distributed.deploy.spec import ProcessInterface, SpecCluster
from distributed.scheduler import Scheduler
from distributed.security import Security

from .utilities import *
from .support import *

from .common import logger

DEFAULT_WORKER_COMMAND = "distributed.cli.dask_worker"

job_parameters = """
    cores : int
        DEPRECATED - Not recommended to specify this
        ~~ Total number of cores per job ~~
        DEPRECATED - Specifying this may change expected behaviour in unknown ways
    memory: str
        DEPRECATED - Not recommended to specify this
        ~~ Total amount of memory per job ~~
        DEPRECATED - Specifying this may change expected behaviour in unknown ways
    processes : int
        DEPRECATED - Not recommended to specify this
        ~~ Cut the job up into this many processes. Good for GIL workloads or for
        nodes with many cores.
        By default, ``process ~= sqrt(cores)`` so that the number of processes
        and the number of threads per process is roughly the same. ~~
        DEPRECATED - Specifying this may change expected behaviour in unknown ways
    interface : str
        Network interface like 'eth0' or 'ib0'. This will be used both for the
        Dask scheduler and the Dask workers interface. If you need a different
        interface for the Dask scheduler you can pass it through
        the ``scheduler_options`` argument:
        ``interface=your_worker_interface, scheduler_options={'interface': your_scheduler_interface}``.
    nanny : bool
        Whether or not to start a nanny process
    local_directory : str
        Dask worker local directory for file spilling.
    death_timeout : float
        Seconds to wait for a scheduler before closing workers
    extra : list
        Deprecated: use ``worker_extra_args`` instead. This parameter will be removed in future.
    worker_command : list
        Command to run when launching a worker.  Defaults to "distributed.cli.dask_worker"
    worker_extra_args : list
        Additional arguments to pass to `dask-worker`
    log_directory : str
        Directory to use for job scheduler logs.
    python : str
        Python executable used to launch Dask workers.
        Defaults to the Python that is submitting these jobs
    config_name : str
        Section to use from jobqueue.yaml configuration file.
    name : str
        Name of Dask worker.  This is typically set by the Cluster
""".strip()


cluster_parameters = """
    silence_logs : str
        Log level like "debug", "info", or "error" to emit here if the
        scheduler is started locally
    asynchronous : bool
        Whether or not to run this cluster object with the async/await syntax
    security : Security or Bool
        A dask.distributed security object if you're using TLS/SSL.  If True,
        temporary self-signed credentials will be created automatically.
    scheduler_options : dict
        Used to pass additional arguments to Dask Scheduler. For example use
        ``scheduler_options={'dashboard_address': ':12435'}`` to specify which
        port the web dashboard should use or ``scheduler_options={'host': 'your-host'}``
        to specify the host the Dask scheduler should run on. See
        :class:`distributed.Scheduler` for more details.
    scheduler_cls : type
        Changes the class of the used Dask Scheduler. Defaults to  Dask's
        :class:`distributed.Scheduler`.
    shared_temp_directory : str
        Shared directory between scheduler and worker (used for example by temporary
        security certificates) defaults to current working directory if not set.
""".strip()


class Job(ProcessInterface, abc.ABC):
    """ Base class to launch Dask workers on Job queues

    This class should not be used directly, use a class appropriate for
    your queueing system (e.g. PBScluster or SLURMCluster) instead.

    Parameters
    ----------
    {job_parameters}
    job_extra : list or dict
        Deprecated: use ``job_extra_directives`` instead. This parameter will be removed in a future version.
    job_extra_directives : list or dict
        Unused in this base class:
        List or dict of other options for the queueing system. See derived classes for specific descriptions.

    Attributes
    ----------
    submit_command: str
        Abstract attribute for job scheduler submit command,
        should be overridden
    cancel_command: str
        Abstract attribute for job scheduler cancel command,
        should be overridden

    See Also
    --------
    PBSCluster
    SLURMCluster
    SGECluster
    OARCluster
    LSFCluster
    MoabCluster
    """.format(
        job_parameters=job_parameters
    )

    _script_template = """
%(shebang)s

%(job_header)s
%(job_script_prologue)s
%(worker_command)s
""".lstrip()

    # Following class attributes should be overridden by extending classes.
    submit_command = None
    cancel_command = None
    job_id_regexp = r"(?P<job_id>\d+)"

    @abc.abstractmethod
    def __init__(
        self,
        scheduler=None,
        name=None,
        cpus=None,
        memory=None,
        processes=None,
        nanny=True,
        protocol=None,
        security=None,
        interface=None,
        death_timeout=None,
        local_directory=None,
        extra=None,
        worker_command=DEFAULT_WORKER_COMMAND,
        worker_extra_args=[],
        log_directory=None,
        python=sys.executable,
        job_name=None,
        comm_port=None,
        hardware=None, 
        tag=None,
        container=None,
        launched=None,
    ):
        self.scheduler = scheduler
        self.job_id = None

        self.launched = False

        super().__init__()

        if container is None:
            raise ValueError(
                "Container cannot be None. The information about launching the worker\
                    is located inside the container object."
            )
        
        if launched is None:
            raise ValueError(
                "Launched list is None. Every worker needs a launched list for the cluster\
                    to be able to monitor the workers effectively. Please try again."
            )
        
        self.launched = launched
        
        self.container = container

        if tag is None:
            raise ValueError(
                "Each worker is required to have a tag. Please try again."
            )
        
        self.tag = tag

        if hardware is None:
            raise ValueError(
                "No hardware resources object. Please try again."
            )
        
        self.hardware = hardware

        container_info = self.container.get_info_dict()

        if cpus is None:
            cpus = container_info['CPUs']
        if memory is None:
            memory = container_info['Memory']
        self.cpus = cpus
        self.memory = memory
        processes = 1
        if extra is not None:
            warn = (
                "extra has been renamed to worker_extra_args. "
                "You are still using it (even if only set to []; please also check config files). "
                "If you did not set worker_extra_args yet, extra will be respected for now, "
                "but it will be removed in a future release. "
                "If you already set worker_extra_args, extra is ignored and you can remove it."
            )
            warnings.warn(warn, FutureWarning)
            if not worker_extra_args:
                worker_extra_args = extra        

        if comm_port is None:
            raise ValueError(
                "Communicator port not given. You must specify the communicator port \
                for the workers to be launched. Please try again"
            )
        
        self.comm_port = comm_port
        # This attribute should be set in the derived class

        if interface:
            worker_extra_args = worker_extra_args + ["--interface", interface]
        if protocol:
            worker_extra_args = worker_extra_args + ["--protocol", protocol]
        if security:
            worker_security_dict = security.get_tls_config_for_role("worker")
            security_command_line_list = [
                ["--tls-" + key.replace("_", "-"), value]
                for key, value in worker_security_dict.items()
                # 'ciphers' parameter does not have a command-line equivalent
                if key != "ciphers"
            ]
            security_command_line = sum(security_command_line_list, [])
            worker_extra_args = worker_extra_args + security_command_line

        # Keep information on process, cores, and memory, for use in subclasses
        self.worker_memory = parse_bytes(self.memory) if self.memory is not None else None
        self.worker_processes = processes
        #self.worker_cores = cores
        self.name = name
        self.job_name = job_name


        # dask-worker command line build
        dask_worker_command = "%(python)s -m %(worker_command)s" % dict(
            python="python3",
            worker_command=worker_command
        )

        command_args = [dask_worker_command, self.scheduler]

        # common
        command_args += ["--name", self.name]
        command_args += ["--nthreads", self.cpus]
        command_args += ["--memory-limit", f"{self.worker_memory}GB"]

        #  distributed.cli.dask_worker specific
        if worker_command == "distributed.cli.dask_worker":
            command_args += ["--nworkers", processes]
            command_args += ["--nanny" if nanny else "--no-nanny"]

        if death_timeout is not None:
            command_args += ["--death-timeout", death_timeout]
        if local_directory is not None:
            command_args += ["--local-directory", local_directory]
        if tag is not None:
            command_args += ["--resources", f"\'{tag}\'=1"]
        if worker_extra_args is not None:
            command_args += worker_extra_args
        
        self.command_args = command_args

        self._command_template = " ".join(map(str, command_args))

        self.log_directory = log_directory
        if self.log_directory is not None:
            if not os.path.exists(self.log_directory):
                os.makedirs(self.log_directory)

    async def _submit_job(self, script_filename):
        return await self._call(shlex.split(self.submit_command) + [script_filename])
    
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
        cmd: List(str))
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
        The stdout produced by the command, as string.

        Raises
        ------
        RuntimeError if the command exits with a non-zero exit code
        """
        cmd = list(map(str, cmd))
        cmd += "\n"
        cmd_str = " ".join(cmd)
        logger.debug(
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
        out = out.decode()
        out = out.strip()
        return out


class JobQueueCluster(SpecCluster):
    __doc__ = """ Deploy Dask on a Job queuing system

    This is a superclass, and is rarely used directly.  It is more common to
    use an object like SLURMCluster others.

    However, it can be used directly if you have a custom ``Job`` type.
    This class relies heavily on being passed a ``Job`` type that is able to
    launch one Job on a job queueing system.

    Parameters
    ----------
    Job : Job
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
        security=None,
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
        # Job keywords
        path_overwrite=True,
        **job_kwargs
    ):
        self.status = Status.created

        self.specifications = {}

        default_job_cls = getattr(type(self), "job_cls", None)
        self.job_cls = default_job_cls
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

        if protocol is None and security is not None:
            protocol = "tls://"

        if security is True:
            try:
                security = Security.temporary()
            except ImportError:
                raise ImportError(
                    "In order to use TLS without pregenerated certificates `cryptography` is required,"
                    "please install it using either pip or conda"
                )
            
        self.model_configs = ModelConfig(path_overwrite=path_overwrite)
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

        self.shared_temp_directory = shared_temp_directory

        job_kwargs["interface"] = interface
        job_kwargs["protocol"] = protocol
        job_kwargs["security"] = self._get_worker_security(security)

        self._job_kwargs = job_kwargs

        worker = {"cls": self.job_cls, "options": self._job_kwargs}
        if "processes" in self._job_kwargs and self._job_kwargs["processes"] > 1:
            warn = (
                "Processes are not supposed to be defined or specified when launching the cluster."
                "The value for processes is being ignored as it is set internally."
            )
            warnings.warn(warn, FutureWarning)

        self.containers = {}

        super().__init__(
            scheduler=scheduler,
            worker=worker,
            loop=loop,
            security=security,
            silence_logs=silence_logs,
            asynchronous=asynchronous,
            name=name,
        )

    def _new_worker_name(self, worker_number):
        """Returns new worker name.

        Base worker name on cluster name. This makes it easier to use job
        arrays within Dask-Jobqueue.
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
        d: dict mapping names to worker specs

        See Also
        --------
        scale
        """
        if tag not in self.specifications:
            self.specifications[tag] = copy.deepcopy(self.new_spec)
            if tag not in self.containers:
                logger.error(f"The tag ({tag}) given is not a recognized tag for any of the containers."
                            "Please add a container with this tag to the cluster by using"
                            "add_container() and try again. User error at this point shouldn't happen."
                            "Likely a bug.")
                raise ValueError()
            self.specifications[tag]["options"]["container"] = self.containers[tag]
            self.specifications[tag]["options"]["tag"] = tag
        new_worker_name = f"{self._new_worker_name(self._i)}-{tag}"
        while new_worker_name in self.worker_spec:
            self._i += 1
            new_worker_name = f"{self._new_worker_name(self._i)}-{tag}"

        return {new_worker_name: self.specifications[tag]}

    def _get_worker_security(self, security):
        """Dump temporary parts of the security object into a shared_temp_directory"""
        if security is None:
            return None

        worker_security_dict = security.get_tls_config_for_role("worker")

        # dumping of certificates only needed if multiline in-memory keys are contained
        if not any(
            [
                (value is not None and "\n" in value)
                for value in worker_security_dict.values()
            ]
        ):
            return security
        # a shared temp directory should be configured correctly
        elif self.shared_temp_directory is None:
            shared_temp_directory = os.getcwd()
            warnings.warn(
                "Using a temporary security object without explicitly setting a shared_temp_directory: \
writing temp files to current working directory ({}) instead. You can set this value by \
using dask for e.g. `dask.config.set({{'jobqueue.pbs.shared_temp_directory': '~'}})`\
or by setting this value in the config file found in `~/.config/dask/jobqueue.yaml` ".format(
                    shared_temp_directory
                ),
                category=UserWarning,
            )
        else:
            shared_temp_directory = os.path.expanduser(
                os.path.expandvars(self.shared_temp_directory)
            )

        security = copy.copy(security)

        for key, value in worker_security_dict.items():
            # dump worker in-memory keys for use in job_script
            if value is not None and "\n" in value:
                try:
                    f = tempfile.NamedTemporaryFile(
                        mode="wt",
                        prefix=".dask-jobqueue.worker." + key + ".",
                        dir=shared_temp_directory,
                    )
                except OSError as e:
                    raise OSError(
                        'failed to dump security objects into shared_temp_directory({})"'.format(
                            shared_temp_directory
                        )
                    ) from e

                # make sure that the file is bound to life time of self by keeping a reference to the file handle
                setattr(self, "_job_" + key, f)
                f.write(value)
                f.flush()
                # allow expanding of vars and user paths in remote script
                if self.shared_temp_directory is not None:
                    fname = os.path.join(
                        self.shared_temp_directory, os.path.basename(f.name)
                    )
                else:
                    fname = f.name
                setattr(
                    security,
                    "tls_" + ("worker_" if key != "ca_file" else "") + key,
                    fname,
                )

        return security

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

        return super().scale(jobs, memory=memory, cores=cores)

    def adapt(
        self, *args, minimum_jobs: int = None, maximum_jobs: int = None, **kwargs
    ):
        """Scale Dask cluster automatically based on scheduler activity.

        Parameters
        ----------
        minimum : int
           Minimum number of workers to keep around for the cluster
        maximum : int
           Maximum number of workers to keep around for the cluster
        minimum_memory : str
           Minimum amount of memory for the cluster
        maximum_memory : str
           Maximum amount of memory for the cluster
        minimum_jobs : int
           Minimum number of jobs
        maximum_jobs : int
           Maximum number of jobs
        **kwargs :
           Extra parameters to pass to dask.distributed.Adaptive

        See Also
        --------
        dask.distributed.Adaptive : for more keyword arguments
        """

        if minimum_jobs is not None:
            kwargs["minimum"] = minimum_jobs * self._dummy_job.worker_processes
        if maximum_jobs is not None:
            kwargs["maximum"] = maximum_jobs * self._dummy_job.worker_processes
        return super().adapt(*args, **kwargs)
