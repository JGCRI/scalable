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

    
    
    
    
        
