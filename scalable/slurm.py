import os

from .core import Job, JobQueueCluster, job_parameters, cluster_parameters
from distributed.deploy.spec import ProcessInterface
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
        account=None,
        walltime=None,
        log_directory=None,
        container=None,
        comm_port=None,
        tag=None,
        hardware=None,
        logs_location=None,
        logger=True,
        shared_lock=None,
        **base_class_kwargs
    ):
        super().__init__(
            scheduler=scheduler, name=name, hardware=hardware, comm_port=comm_port, \
            container=container, tag=tag, **base_class_kwargs
        )

        self.shared_lock = shared_lock

        job_name = f"{self.name}-job"

        self.slurm_cmd = salloc_command(account=account, name=job_name, nodes=DEFAULT_REQUEST_QUANTITY, 
                                        partition=queue, time=walltime)
        self.logs_file = None

        if logger:
            self.logs_file = os.path.abspath(os.path.join(os.getcwd(), logs_location, f"{self.name}-{self.tag}.log"))
        
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
    
    @staticmethod
    def set_default_request_quantity(nodes):
        global DEFAULT_REQUEST_QUANTITY
        DEFAULT_REQUEST_QUANTITY = nodes
    