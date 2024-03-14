import logging
import warnings
import dask
import os
import asyncio

from .core import Job, JobQueueCluster, job_parameters, cluster_parameters
from distributed.deploy.spec import ProcessInterface
from distributed.scheduler import Scheduler
from distributed.core import Status
from distributed.utils import NoOpAwaitable
from .support import *

from .utilities import *

from .common import logger

DEFAULT_REQUEST_QUANTITY = 1

class SlurmJob(Job):
    # Override class variables
    cancel_command = "scancel"

    def __init__(
        self,
        scheduler=None,
        name=None,
        queue=None,
        project=None,
        account=None,
        walltime=None,
        log_directory=None,
        container=None,
        comm_port=None,
        tag=None,
        hardware=None,
        logs_location=None,
        logger=True,
        shared_lock=asyncio.Lock(),
        **base_class_kwargs
    ):
        super().__init__(
            scheduler=scheduler, name=name, hardware=hardware, comm_port=comm_port, \
            container=container, tag=tag, **base_class_kwargs
        )

        self.scheduler = scheduler
        self.job_id = None
        self.shared_lock = shared_lock

        self.log_directory = log_directory
        if self.log_directory is not None:
            if not os.path.exists(self.log_directory):
                os.makedirs(self.log_directory)
        
        if project is not None:
            warn = (
                "project has been renamed to account as this kwarg was used wit -A option. "
                "You are still using it (please also check config files). "
                "If you did not set account yet, project will be respected for now, "
                "but it will be removed in a future release. "
                "If you already set account, project is ignored and you can remove it."
            )
            warnings.warn(warn, FutureWarning)
            if not account:
                account = project

        self.name = name

        job_name = f"{self.name}-job"

        self.slurm_cmd = salloc_command(account=account, name=job_name, nodes=DEFAULT_REQUEST_QUANTITY, 
                                        partition=queue, time=walltime)
        self.logs_file = None

        if logger:
            self.logs_file = os.path.abspath(os.path.join(os.getcwd(), logs_location, f"{self.name}-{self.tag}.log"))
            print(f"{self.name=} {self.tag=}")

        if hardware is None:
            raise ValueError(
                "Hardware resources not specified. These are needed for the workers to know"
                "when to request more hardware resources. Please try again"
            )

        self.hardware = hardware
        
        # All the wanted commands should be set here
        self.send_command = self.container.get_command()
        self.send_command.extend(self.command_args)

    async def _get_resources(self, command):
        out = await self._call(command, self.comm_port)
        return out
    
    async def _srun_command(self, command):
        prefix = ["srun", f"--jobid={self.job_id}"]
        command = prefix + command
        out = await self._call(command, self.comm_port)
        return out
    
    async def _ssh_command(self, command):
        prefix = ["ssh", self.job_node]
        if self.logs_file:
            suffix = [f">{self.logs_file}", "2>&1", "&"]
            command = command + suffix
        command = list(map(str, command))
        command_str = " ".join(command)
        command = prefix + [f"\"{command_str}\""]
        out = await self._call(command, self.comm_port)
        return out

    async def start(self):
        logger.debug("Starting worker: %s", self.name)

        async with self.shared_lock:
            while self.job_id is None:
                self.job_node = self.hardware.check_availability(self.cpus, self.memory)
                if self.job_node is None:
                    break
                job_id = self.hardware.get_node_jobid(self.job_node)
                out = await self._run_command(jobcheck_command(job_id))
                match = re.search(self.job_id_regexp, out)
                if match is None:
                    self.hardware.remove_jobid_nodes(job_id)
                else:
                    self.job_id = match.groupdict().get("job_id")
            if self.job_node == None:
                out = await self._get_resources(self.slurm_cmd)
                job_name = f"{self.name}-job"
                job_id = await self._run_command(jobid_command(job_name))
                self.job_id = job_id
                nodelist = await self._run_command(nodelist_command(job_name))
                nodes = parse_nodelist(nodelist)
                worker_memories = await self._srun_command(memory_command())
                worker_cpus = await self._srun_command(core_command())
                worker_memories = worker_memories.split('\n')
                worker_cpus = worker_cpus.split('\n')
                for index in range(0, len(nodes)):
                    node = nodes[index]
                    alloc_memory = int(worker_memories[index])
                    alloc_cpus = int(worker_cpus[index])
                    self.hardware.assign_resources(node=node, cpus=alloc_cpus, memory=alloc_memory, jobid=self.job_id)
                self.job_node = self.hardware.check_availability(self.cpus, self.memory)
            _ = await self._ssh_command(self.send_command)
            self.hardware.utilize_resources(self.job_node, self.cpus, self.memory, self.job_id)
            self.launched.append(self.name)

        logger.debug("Starting job: %s", self.job_id)
        await ProcessInterface.start(self)

    async def close(self):
        async with self.shared_lock:
            self.hardware.release_resources(self.job_node, self.cpus, self.memory, self.job_id)
            if not self.hardware.has_active_nodes(self.job_id):
                self.hardware.remove_jobid_nodes(self.job_id)
                await SlurmJob._close_job(self.job_id, self.cancel_command, self.comm_port)

                

class SlurmCluster(JobQueueCluster):
    __doc__ = """ Launch Dask on a SLURM cluster

    Parameters
    ----------
    queue : str
        Destination queue for each worker job. 
    project : str
        Deprecated: use ``account`` instead. This parameter will be removed in a future version.
    account : str
        Accounting string associated with each worker job. 
    {job}
    {cluster}
    walltime : str
        Walltime for each worker job.
        
    """.format(
        job=job_parameters, cluster=cluster_parameters
    )
    job_cls = SlurmJob
    
    def __init__(
        self,
        job_cls: Job = SlurmJob,
        # Cluster keywords
        loop=None,
        security=None,
        shared_temp_directory=None,
        silence_logs="error",
        name=None,
        asynchronous=False,
        # Slurm options
        account=None,
        queue=None,
        walltime=None,
        # Scheduler-only keywords
        dashboard_address=None,
        host=None,
        scheduler_options={},
        scheduler_cls=Scheduler,  # Use local scheduler for now
        # Options for both scheduler and workers
        interface=None,
        protocol=None,
        # Job keywords
        comm_port=None,
        path_overwrite=True,
        **job_kwargs
    ):
        if comm_port is None:
            raise ValueError(
                "Communicator port not given. You must specify the communicator port"
                "for the workers to be launched. Please try again"
            )
        self.comm_port = comm_port
        self.resource_dict = get_resource_dict()
        self.hardware = HardwareResources()
        self.shared_lock = asyncio.Lock()
        self.launched = []
        self.logs_location = create_logs_folder("SlurmCluster")
        
        super().__init__( 
            job_cls=job_cls, 
            loop=loop, 
            security=security, 
            shared_temp_directory=shared_temp_directory, 
            silence_logs=silence_logs, 
            name=name, 
            asynchronous=asynchronous, 
            dashboard_address=dashboard_address, 
            host=host, 
            scheduler_options=scheduler_options, 
            scheduler_cls=scheduler_cls, 
            interface=interface, 
            protocol=protocol, 
            account=account,
            queue=queue,
            hardware=self.hardware,
            path_overwrite=path_overwrite,
            comm_port=comm_port,
            shared_lock=self.shared_lock,
            walltime=walltime,
            launched=self.launched,
            logs_location=self.logs_location,
            **job_kwargs)
        
    async def remove_launched_worker(self, worker):
        async with self.shared_lock:
            self.launched.remove(worker)

    def add_worker(self, tag, n=0):
        if tag not in self.containers:
            logger.error(f"The tag ({tag}) given is not a recognized tag for any of the containers."
                         "Please add a container with this tag to the cluster by using"
                         "add_container() and try again.")
            return
        to_close = set(self.launched) - set(self.workers)
        for worker in to_close:
            del self.worker_spec[worker]
            asyncio.run(self.remove_launched_worker(worker))
        if self.status not in (Status.closing, Status.closed):
            for _ in range(n):
                print(f"BEFORE GENERATE SPEC {self.worker_spec}")
                new_worker = self.new_worker_spec(tag)
                self.worker_spec.update(dict(new_worker))
                print(f"INSIDE ADD CONT AFTER SELF SPEC UPDATE {self.worker_spec=}")
        self.loop.add_callback(self._correct_state)
        if self.asynchronous:
            return NoOpAwaitable() 

    def add_container(self, tag, dirs, path=None, cpus=None, memory=None):
        tag = tag.lower()
        self.model_configs.update_dict(tag, 'Dirs', dirs)
        if path:
            self.model_configs.update_dict(tag, 'Path', path)
        if cpus:
            self.model_configs.update_dict(tag, 'CPUs', cpus)
        if memory:
            self.model_configs.update_dict(tag, 'Memory', memory)
        self.containers[tag] = Container(name=tag, spec_dict=self.model_configs.config_dict[tag])
    
    @staticmethod
    def set_default_request_quantity(nodes):
        global DEFAULT_REQUEST_QUANTITY
        DEFAULT_REQUEST_QUANTITY = nodes
    