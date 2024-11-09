import os

from collections.abc import Awaitable
from distributed.core import Status
from distributed.deploy.spec import ProcessInterface

from .common import logger
from .core import Job, JobQueueCluster, cluster_parameters, job_parameters
from .support import *
from .utilities import *

DEFAULT_REQUEST_QUANTITY = 1
RECOVERY_DELAY = 3

class SlurmJob(Job):

    # Override class variables
    cancel_command = "scancel"

    def __init__(
        self,
        scheduler=None,
        name=None,
        queue=None,
        account=None,
        walltime=None,
        container=None,
        comm_port=None,
        tag=None,
        hardware=None,
        logs_location=None,
        shared_lock=None,
        worker_env_vars=None,
        **base_class_kwargs
    ):
        super().__init__(
            scheduler=scheduler, name=name, hardware=hardware, comm_port=comm_port, \
            container=container, tag=tag, shared_lock=shared_lock, **base_class_kwargs
        )

        job_name = f"{self.name}-job"

        self.slurm_cmd = salloc_command(account=account, name=job_name, nodes=DEFAULT_REQUEST_QUANTITY, 
                                        partition=queue, time=walltime)
        
        self.job_name = job_name
        self.job_id = None
        self.job_node = None
        self.log_file = None

        if logs_location is not None:
            self.log_file = os.path.abspath(os.path.join(logs_location, f"{self.name}-{self.tag}.log"))
        
        self.send_command = self.container.get_command(worker_env_vars)
        self.send_command.extend(self.command_args)
    
    async def _srun_command(self, command):
        prefix = ["srun", f"--jobid={self.job_id}"]
        command = prefix + command
        out = await self._run_command(command)
        return out
    
    async def _ssh_command(self, command):
        prefix = ["ssh", self.job_node]
        if self.log_file:
            suffix = [f">> {self.log_file}", "2>&1", "&"]
            command = command + suffix
        command = list(map(str, command))
        command_str = " ".join(command)
        command = prefix + [f"\"{command_str}\""]
        out = await self._run_command(command)
        return out
    
    async def _check_valid_job_id(self, job_id):
        out = await self._run_command(jobcheck_command(job_id))
        match = re.search(self.job_id_regexp, out)
        return match

    async def start(self):
        """Start function for the worker.

        The worker sets itself up by requesting or consuming necessary 
        resources and adding itself as an active worker to the cluster. 
        All cases such as there being no active or available nodes are handled 
        by this function. Called by the parent classes when scaling the workers.
        """
        logger.debug("Starting worker: %s", self.name)

        async with self.shared_lock:
            while self.job_id is None:
                self.job_node = self.hardware.get_available_node(self.cpus, self.memory)
                if self.job_node is None:
                    break
                job_id = self.hardware.get_node_jobid(self.job_node)
                match = await self._check_valid_job_id(job_id)
                if match is None:
                    self.hardware.remove_jobid_nodes(job_id)
                else:
                    self.job_id = match.groupdict().get("job_id")
            if self.job_node == None:
                out = await self._run_command(self.slurm_cmd)
                job_id = await self._run_command(jobid_command(self.job_name))
                self.job_id = job_id
                nodelist = await self._run_command(nodelist_command(self.job_name))
                nodes = parse_nodelist(nodelist)
                worker_memories = await self._srun_command(memory_command())
                worker_cpus = await self._srun_command(core_command())
                worker_memories = worker_memories.split('\n')
                worker_cpus = worker_cpus.split('\n')
                for index in range(0, len(nodes)):
                    node = nodes[index]
                    alloc_memory = int(worker_memories[index])
                    alloc_cpus = int(worker_cpus[index])
                    if not self.hardware.assign_resources(node=node, cpus=alloc_cpus, memory=alloc_memory, jobid=self.job_id):
                        stored_job_id = self.hardware.get_node_jobid(node)
                        match = await self._check_valid_job_id(stored_job_id)
                        if match is None:
                            self.hardware.remove_jobid_nodes(stored_job_id)
                            assert self.hardware.assign_resources(node=node, cpus=alloc_cpus, memory=alloc_memory, jobid=self.job_id)
                        else:
                            raise ValueError(f"Node {node} is already assigned to job {stored_job_id}")
                self.job_node = self.hardware.get_available_node(self.cpus, self.memory)
            _ = await self._ssh_command(self.send_command)
            self.hardware.utilize_resources(self.job_node, self.cpus, self.memory, self.job_id)
            self.launched.append((self.name, self.tag))

        logger.debug("Starting job: %s", self.job_id)
        await ProcessInterface.start(self)

    async def close(self):
        """Close function for the worker.
        
        The worker releases the resources it was utilizing and removes itself."""
        async with self.shared_lock:
            if self.hardware.is_assigned(self.job_id):
                match = await self._check_valid_job_id(self.job_id)
                if match is None:
                    self.hardware.remove_jobid_nodes(self.job_id)
                else:
                    self.hardware.release_resources(self.job_node, self.cpus, self.memory, self.job_id)
                    if not self.hardware.has_active_nodes(self.job_id):
                        self.hardware.remove_jobid_nodes(self.job_id)
                        await SlurmJob._close_job(self.job_id, self.cancel_command, self.comm_port)
            cluster = self._cluster()
            if self.tag in self.removed and self.removed[self.tag] > 0:
                self.removed[self.tag] -= 1
            elif cluster.status not in (Status.closing, Status.closed):
                cluster.loop.call_later(RECOVERY_DELAY, cluster._correct_state)

class SlurmCluster(JobQueueCluster):
    __doc__ = """Launch Dask on a SLURM cluster. Inherits the JobQueueCluster 
    class.

    Parameters
    ----------
    {cluster}
    *args : tuple
        Positional arguments to pass to JobQueueCluster.
    **kwargs : dict
        Keyword arguments to pass to JobQueueCluster.
    """.format(
        cluster=cluster_parameters
    )
    job_cls = SlurmJob

    def close(self, timeout: float | None = None) -> Awaitable[None] | None:
        """Close the cluster

        This closes all running jobs and the scheduler. Pending jobs belonging
        to the user are also cancelled."""
        active_jobs = self.hardware.get_active_jobids()
        jobs_command = "squeue -o \"%i %t\" -u $(whoami) | sed '1d'"
        result = subprocess.run(jobs_command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, shell=True)
        if result.returncode == 0:
            jobs_states = result.stdout.decode('utf-8').split('\n')
            jobid_states = [job.split() for job in jobs_states if job]
            for job_info in jobid_states:
                if job_info[1] == "PD":
                    active_jobs.append(job_info[0])
        for job_id in active_jobs:
            cancel_job_command = f"scancel {job_id}"
            result = subprocess.run(cancel_job_command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, shell=True)
            if result.returncode == 0:
                self.hardware.remove_jobid_nodes(job_id)
                logger.info(f"Cancelled job: {job_id}")
            else:
                logger.error(f"Failed to cancel job: {job_id}")
        
        return super().close(timeout)
    
    @staticmethod
    def set_default_request_quantity(nodes):
        """Set the default number of nodes to request when scaling the cluster.

        Static Function. Does not require an instance of the class.

        If set to 1 (the original default), the cluster will request one 
        hardware node at a time when scaling. If set to a higher number, like 5,
        the cluster will request 5 hardware nodes at a time when scaling. This
        is helpful when each worker may need almost all the resources of a 
        node and it is more efficient to request multiple nodes at once.

        Parameters
        ----------
        nodes : int
            Number of nodes to request when scaling the cluster.
        """
        global DEFAULT_REQUEST_QUANTITY
        DEFAULT_REQUEST_QUANTITY = nodes
    