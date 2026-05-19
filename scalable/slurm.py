import asyncio
import os
import re
import warnings
from collections.abc import Awaitable

from distributed.core import Status
from distributed.deploy.spec import ProcessInterface

from .common import logger
from .core import Job, JobQueueCluster, cluster_parameters, job_parameters
from .support import *  # noqa: F401,F403 - re-exported helpers
from .utilities import *  # noqa: F401,F403 - re-exported helpers

DEFAULT_REQUEST_QUANTITY = 1
RECOVERY_DELAY = 3


def _try_get_running_loop():
    """Return the running event loop, or ``None`` if we're not inside one."""
    try:
        return asyncio.get_running_loop()
    except RuntimeError:
        return None

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
        active_job_ids=None,
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
        self.active_job_ids = active_job_ids
        self.job_id = None
        self.job_node = None
        self.log_file = None
        self.deleted = False

        if logs_location is not None:
            self.log_file = os.path.abspath(os.path.join(logs_location, f"{self.name}-{self.tag}.log"))
        
        apptainer_version = os.getenv("APPTAINER_VERSION", None)

        self.send_command = apptainer_module_command(apptainer_version) + [";"] + \
                            self.container.get_command(worker_env_vars) + self.command_args
    
    async def _srun_command(self, command):
        prefix = ["srun", f"--jobid={self.job_id}"]
        command = prefix + command
        out = await self._run_command(command)
        return out
    
    async def _ssh_command(self, command):
        prefix = ["ssh", self.job_node]
        suffix = []
        if self.log_file:
            suffix = [f">> {self.log_file}", "2>&1"]
        suffix.append("&")
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
        # All workers are async so a lock is needed to prevent race conditions
        # while updating shared data
        async with self.shared_lock:
            # Check if the worker has a "job_id". A "job_id" corresponds to a 
            # SLURM job. If the worker does not have a "job_id", it means that 
            # the worker is not running on a SLURM job or that the physical 
            # resources are not available. 
            while self.job_id is None:
                # Get an available node
                self.job_node = self.hardware.get_available_node(self.cpus, self.memory)
                # If no available node, break
                if self.job_node is None:
                    break
                # Get the node's job id and check if it is still valid
                job_id = self.hardware.get_node_jobid(self.job_node)
                match = await self._check_valid_job_id(job_id)
                if match is None:
                    self.hardware.remove_jobid_nodes(job_id)
                else:
                    self.job_id = match.groupdict().get("job_id")
                # Keep repeating until a valid node is found or none are found
            # If the worker does not have a job node, it means that it didn't
            # find it and a new job needs to be created with one.
            if self.job_node is None:
                # Run slurm commands to create a new job. We don't capture
                # the output here because the job id and node list are
                # retrieved by separate ``squeue`` invocations below.
                await self._run_command(self.slurm_cmd)
                # Parse job ids and nodes of the new job creation
                job_id = await self._run_command(jobid_command(self.job_name))
                self.job_id = job_id
                self.active_job_ids.append(job_id)
                nodelist = await self._run_command(nodelist_command(self.job_name))
                nodes = parse_nodelist(nodelist)
                # Get the memory and cpu allocation for each node
                worker_memories = await self._srun_command(memory_command())
                worker_cpus = await self._srun_command(core_command())
                worker_memories = worker_memories.split('\n')
                worker_cpus = worker_cpus.split('\n')
                for index in range(0, len(nodes)):
                    node = nodes[index]
                    alloc_memory = int(worker_memories[index])
                    alloc_cpus = int(worker_cpus[index])
                    # Assign the new resources given by the slurm job 
                    if not self.hardware.assign_resources(node=node, cpus=alloc_cpus, memory=alloc_memory, jobid=self.job_id):
                        stored_job_id = self.hardware.get_node_jobid(node)
                        match = await self._check_valid_job_id(stored_job_id)
                        if match is None:
                            self.hardware.remove_jobid_nodes(stored_job_id)
                            assert self.hardware.assign_resources(node=node, cpus=alloc_cpus, memory=alloc_memory, jobid=self.job_id)
                        else:
                            raise ValueError(f"Node {node} is already assigned to job {stored_job_id}")
                # Finally, the worker is assigned to the job node
                self.job_node = self.hardware.get_available_node(self.cpus, self.memory)
            # Send the command to launch the worker on the node
            _ = await self._ssh_command(self.send_command)
            loop = _try_get_running_loop()
            if loop is not None:
                loop.create_task(self.check_launched_worker())
            else:  # pragma: no cover - SpecCluster always runs us inside a loop
                logger.debug(
                    "No running event loop while starting %s; skipping "
                    "launch watchdog.",
                    self.name,
                )
            # Mark resources as utilized
            self.hardware.utilize_resources(self.job_node, self.cpus, self.memory, self.job_id)
            # Add the worker to the "launched" list. This list is used to 
            # determine if the worker had already been launched in the past. 
            # This is important because it can determine if the worker 
            # was launched and then died instead of still waiting for the 
            # connection. 
            self.launched.append((self.name, self.tag))
        
        await ProcessInterface.start(self)

    async def close(self):
        """Close function for the worker.
        
        The worker releases the resources it was utilizing and removes itself."""
        if self.deleted:
            return
        async with self.shared_lock:
            # Check if the worker has a job id.
            if self.hardware.is_assigned(self.job_id):
                # If the job id is not valid, just remove the job id from the 
                # hardware bookkeeping.
                match = await self._check_valid_job_id(self.job_id)
                if match is None:
                    self.hardware.remove_jobid_nodes(self.job_id)
                # If the job id is valid, release the resources. 
                else:
                    self.hardware.release_resources(self.job_node, self.cpus, self.memory, self.job_id)
                    # If however, no active nodes (no workers on any of the 
                    # nodes in the id) remain after the resources were released, 
                    # then close the job altogether. This makes it so the last 
                    # worker removed from the job will close the job.
                    if not self.hardware.has_active_nodes(self.job_id):
                        self.hardware.remove_jobid_nodes(self.job_id)
                        await SlurmJob._close_job(self.job_id, self.cancel_command, self.comm_port)
            cluster = self._cluster()
            # If a tag exists in the removed dict with a value greater than 0,
            # it means that that many workers are to be removed from the 
            # cluster with the same tag. So, if the tag of the worker is in
            # the removed dict, then it was supposed to be removed. Deleted is 
            # set to true to prevent running this function again if called.
            if self.tag in self.removed and self.removed[self.tag] > 0:
                self.removed[self.tag] -= 1
                self.deleted = True
            # If that's not the case, then this worker was not supposed to be 
            # removed but it died for some other reason. In that case, 
            # the worker needs to be brought back to life. The cluster will 
            # "correct its state" by making sure that the number of workers 
            # needed matches the number of workers running after the delay. 
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
        """Close the cluster.

        This closes all running jobs and the scheduler. Pending jobs belonging
        to the user are also cancelled.

        The method is robust whether or not it is called from an active event
        loop:

        * In a synchronous context (no running loop), each ``scancel`` is
          dispatched via :func:`asyncio.run`.
        * In an asynchronous context (a running loop), the cancellations are
          scheduled as background tasks; we **do not** call
          :func:`asyncio.run` because doing so raises
          ``RuntimeError: asyncio.run() cannot be called from a running event
          loop``.
        """
        active_jobs = list(self.active_job_ids)
        loop = _try_get_running_loop()

        for job_id in active_jobs:
            cancel_job_command = ["scancel", str(job_id)]
            coro = self.job_cls._call(cancel_job_command, self.comm_port)
            try:
                if loop is None:
                    result = asyncio.run(coro)
                    self._handle_cancel_result(job_id, result)
                else:
                    task = loop.create_task(coro)
                    task.add_done_callback(
                        lambda t, jid=job_id: self._handle_cancel_result(
                            jid,
                            t.result() if t.exception() is None else "",
                        )
                    )
            except Exception as exc:  # pragma: no cover - defensive
                logger.error("Error while cancelling job %s: %s", job_id, exc)

        return super().close(timeout)

    def _handle_cancel_result(self, job_id, result):
        """Bookkeeping for a single ``scancel`` result.

        Parameters
        ----------
        job_id : str
            Slurm job id we attempted to cancel.
        result : str
            Stdout from the ``scancel`` invocation. Empty string indicates
            success.
        """
        if not result:
            self.hardware.remove_jobid_nodes(job_id)
            logger.info("Cancelled job: %s", job_id)
        else:
            logger.error("Failed to cancel job %s: %s", job_id, result)

    @staticmethod
    def set_default_request_quantity(nodes):
        """Set the process-global default number of nodes per Slurm job.

        .. deprecated::
            Pass ``request_quantity=`` to a future ``SlurmScheduler`` (medium-
            term plan item M2) instead. The class-level mutation persists
            across tests and prevents per-cluster customization.

        Parameters
        ----------
        nodes : int
            Number of nodes to request when scaling the cluster.
        """
        warnings.warn(
            "SlurmCluster.set_default_request_quantity mutates a process-wide "
            "global; per-cluster configuration support is planned. The static "
            "setter will be removed once the SlurmScheduler refactor lands.",
            DeprecationWarning,
            stacklevel=2,
        )
        global DEFAULT_REQUEST_QUANTITY
        DEFAULT_REQUEST_QUANTITY = nodes
