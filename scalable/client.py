import subprocess

from collections.abc import Awaitable
from distributed import Scheduler, Client
from distributed.diagnostics.plugin import SchedulerPlugin


from .common import logger
from .slurm import SlurmJob, SlurmCluster

class SlurmSchedulerPlugin(SchedulerPlugin):

    def __init__(self, cluster):
        self.cluster = cluster
        super().__init__()

    def remove_client(self, scheduler: Scheduler, client: str) -> None:
        active_jobs_command = f"squeue -o %i -u $(whoami) | sed '1d'"
        result = subprocess.run(active_jobs_command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, shell=True)
        if result.returncode == 0:
            active_jobs = result.stdout.decode('utf-8').split('\n')
            for job_id in active_jobs:
                if job_id:
                    cancel_job_command = f"scancel {job_id}"
                    result = subprocess.run(cancel_job_command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, shell=True)
                    if result.returncode == 0:
                        logger.info(f"Cancelled job: {job_id}")
                    else:
                        logger.error(f"Failed to cancel job: {job_id}")
        else:
            logger.error("Failed to run squeue command. Please check for active jobs manually by running: \n"
                         "squeue | grep $(whoami)")
            return    
    

class ScalableClient(Client):

    def __init__(self, cluster, *args, **kwargs):
        super().__init__(address = cluster, *args, **kwargs)
        if isinstance(cluster, SlurmCluster):
            self.register_scheduler_plugin(SlurmSchedulerPlugin(None))

    
    
    
    
        
