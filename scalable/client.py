import subprocess

from collections.abc import Awaitable
from distributed import Scheduler, Client
from distributed.diagnostics.plugin import SchedulerPlugin


from .common import logger

class ScalableSchedulerPlugin(SchedulerPlugin):

    def __init__(self, cluster):
        self.cluster = cluster
        super().__init__()

    async def close(self) -> None:
        active_jobs_command = f"squeue | grep $(whoami)"
        result = subprocess.run(active_jobs_command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, shell=True)
        if result.returncode == 0:
            active_jobs = result.stdout.decode('utf-8').split('\n')
            logger.info(f"These jobs launched by the cluster are still active: \n{active_jobs}\n"
                        "No jobs should be listed above under normal operation.")
        else:
            logger.error("Failed to run squeue command. Please check for active jobs manually by running: \n"
                         "squeue | grep $(whoami)")
            return
        
    

class ScalableClient(Client):

    def __init__(self, cluster, *args, **kwargs):
        super().__init__(address = cluster, *args, **kwargs)
        self.register_scheduler_plugin(ScalableSchedulerPlugin(None))

    
    
    
    
        
