import asyncio
import os
import re
import subprocess
import sys
import yaml

from importlib.resources import files
from dask.utils import parse_bytes

from .common import logger

comm_port_regex = r'0\.0\.0\.0:(\d{1,5})'

async def get_cmd_comm(port, communicator_path=None):
    """Returns a running process of the command communicator.

    The communicator is used by the containerized cluster to send commands to 
    be ran on the host. An active process of the communicator client, used to 
    connect with the communicator server on host is returned. 

    Parameters
    ----------
    communicator_path: str
        The path of the communicator. Defaults to None or the current directory.
    
    Returns
    -------
    asyncio.subprocess.Process
        The communicator client process.
    """
    if communicator_path is None:
        communicator_path = "./communicator"
    if not os.path.isfile(communicator_path):
        raise FileNotFoundError("The communicator file does not exist at the given path" +
                                "(default current directory). Please try again.")
    communicator_command = []
    communicator_command.append(communicator_path)
    communicator_command.append("-c")
    communicator_command.append(str(port))
    proc = await asyncio.create_subprocess_exec(
        *communicator_command,
        stdin=asyncio.subprocess.PIPE,
        stdout=asyncio.subprocess.PIPE,
    )
    return proc

def run_bootstrap():
    bootstrap_location = files('scalable').joinpath('scalable_bootstrap.sh')
    result = subprocess.run([os.environ.get("SHELL"), bootstrap_location.as_posix()], stdin=sys.stdin, 
                            stdout=sys.stdout, stderr=sys.stdout)
    if result.returncode != 0:
        sys.exit(result.returncode)

class ModelConfig:
    """ModelConfig class to represent the resource requirements for each model
    or container in the cluster. 

    Essentially a wrapper around config_dict.yaml which stores information 
    such as CPU cores and Memory needed, paths of mounted volumes, and paths 
    of the .sif container file for each of the containers/models. 

    Attributes
    ----------
    config_dict : dict
        A nested dictionary which stores config_dict.yaml. This dict is either 
        read from config_dict or a new one is made and written to config_dict. 
    path : str
        The path at which config_dict.yaml resides or is to be written to.

    Methods
    -------
    update_dict(tag, key, value)
        Update any of the stored information in the config_dict.
    """

    def __init__(self, path=None, path_overwrite=True):
        """
        
        Parameters
        ----------
        path : str
            The path at which the config_dict.yaml file resides or is to be 
            written to. Defaults to scalable/config_dict.yaml in the current 
            workingdirectory.
        path_overwrite : bool
            A flag to determine if the config_dict should be overwritten with
            fresh data or older data such as previously set binded directories.
            Defaults to True so a new config_dict is made.
        """
        # HARDCODING CURRENT DIRECTORY
        self.config_dict = {}
        cwd = os.getcwd()
        if path is None:
            self.path = os.path.abspath(os.path.join(cwd, "config_dict.yaml"))
        dockerfile_path = os.path.abspath(os.path.join(cwd, "Dockerfile"))
        list_avial_command = \
        f"sed -n 's/^FROM[[:space:]]\+[^ ]\+[[:space:]]\+AS[[:space:]]\+\([^ ]\+\)$/\\1/p' {dockerfile_path}"
        result = subprocess.run(list_avial_command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, shell=True)
        if result.returncode == 0:
            avail_containers = result.stdout.decode('utf-8').split('\n')
            try:
                avail_containers.remove("build_env")
            except ValueError:
                pass
            avail_containers = list(filter(bool, avail_containers))
            avail_containers = [container.replace('\r', '') for container in avail_containers]
        else:
            logger.error("Failed to run sed command...manual entry of container info may be required")
            return
        if not os.path.exists(self.path):
            logger.warning("No resource dict found...making one")
            path_overwrite = True
            for container in avail_containers:
                self.config_dict[container] = ModelConfig.default_spec()
        else:
            with open(self.path, 'r') as config_dict:
                self.config_dict = yaml.safe_load(config_dict)
        if path_overwrite:
            for container in avail_containers:
                container_path = os.path.abspath(os.path.join(cwd, "containers", f"{container}_container.sif"))
                if not os.path.exists(container_path):
                    container_path = ""
                if container not in self.config_dict:
                    self.config_dict[container] = ModelConfig.default_spec()
                self.config_dict[container]['Path'] = container_path
            with open(self.path, 'w') as config:
                yaml.dump(self.config_dict, config)
            

    def update_dict(self, tag, key, value):
        """Update information stored about a container in the config_dict. 

        Raises
        ------
        KeyError
            If the tag passed doesn't correspond to a container's/model's tag. 
        """
        try:
            self.config_dict[tag][key] = value
            with open(self.path, 'w') as config:
                yaml.dump(self.config_dict, config)
        except KeyError:
            msg = f"The given key {key} is not in the dictionary. The available keys are \
            {list(self.config_dict.keys())}"
            logger.error(msg)
            logger.error("Please try again")

    @staticmethod
    def default_spec():
        """Return a default specification for a container.
        
        Returns
        -------
        dict
            A dictionary containing the default specifications for a container."""
        config = {}
        config['CPUs'] = 4
        config['Memory'] = "8G"
        return config



class HardwareResources:
    """HardwareResources class is used for storing details about allocated 
    nodes.

    The class is essentially a set of dictionaries which track allocated and
    available nodes along with details like cpu cores and memory on each node.

    Attributes
    ----------
    nodes : list
        A list of names of the nodes allocated to the cluster. 
    assigned : dict
        A dictionary containing the cpu cores and memory for all the allocated 
        nodes. 
    available : dict
        A dictionary containing the available number of cpu cores and the 
        available amount of memory for each allocated node. 
    active : dict
        A dictionary containing the set of nodes allocated for each job 
        requested by the cluster. The jobid is used as a key to a set object
        containing the names of all the allocated nodes.

    Methods
    -------
    assign_resources(node, cpus, memory, jobid)
        Store allocated node data in the local dicts. 
    remove_job_nodes(jobid)
        Remove all stored nodes belonging to a certain job. 
    get_node_jobid(node)
        Get the jobid of the job through which the given node was allocated.
    check_availability(node, cpus, memory)
        Check if a node has the given amount of cpus and memory available. 
    get_available_node(cpus, memory)
        Get a node which has the given amount of cpus and memory available.
    utilize_resources(node, cpus, memory, jobid)
        Mark the given cpus/memory in the given node as unavailable. 
    release_resources(node, cpus, memory, jobid)
        Mark the given cpus/memory in the given node as available.
    has_active_nodes(jobid)
        Check if the given jobid has any nodes which are currently being used.  
    set_min_free_cpus(cpus)
        Set the minimum number of cpu cores which should always be available.
    set_min_free_memory(memory)
        Set the minimum amount of memory which should always be available.
    """

    MIN_CPUS = 10
    MIN_MEMORY = 20

    def __init__(self):
        self.nodes = []
        self.assigned = {}
        self.available = {}
        self.active = {}

    def assign_resources(self, node, cpus, memory, jobid):
        """Store the information of an allocated node. 

        This function is usually called the moment a new node is allocated 
        to store its information such as the jobid it belongs to along with
        the number of cpu cores it has and the amount of memory. 

        Parameters
        ----------
        node : str
            The name of the node which was allocated. 
        cpus : int
            The number of cpu cores in the node. 
        memory : int
            The amount of memory (in bytes) in the node. 
        jobid : int
            The jobid to which the node's allocation request belongs to.

        Raises
        ------
        ValueError
            If the node is already stored. 
        """
        allotted = {'cpus': cpus, 'memory': memory, 'jobid': jobid}
        ret = False
        if node not in self.assigned and node not in self.available:
            self.assigned[node] = allotted
            self.available[node] = allotted.copy()
            self.nodes.append(node)
            if jobid not in self.active:
                self.active[jobid] = set()
            ret = True
        return ret
    
    def remove_jobid_nodes(self, jobid):
        """Remove all the nodes belonging to the given jobid. 

        Parameters
        ----------
        jobid : int
            The jobid for which the nodes need to be removed.
        """
        nodes = self.nodes
        if jobid in self.active:
            del self.active[jobid]
        delete = []
        for node in nodes:
            if self.assigned[node]['jobid'] == jobid:
                del self.assigned[node]
                del self.available[node]
                delete.append(node)
        for node in delete:
            self.nodes.remove(node)
    
    def get_node_jobid(self, node):
        """Get the jobid of the allocation request for the given node.

        Parameters
        ----------
        node : str
            The name of the node whose jobid is requested. 

        Returns
        -------
        int
            The jobid to which the node's allocation request belongs to.

        Raises
        ------
        ValueError
            If the node's information is not stored/invalid node.
        """
        if node not in self.assigned:
            raise ValueError(
                "The given node doesn't exist. Please try again.\n"
            )
        else:
            return self.assigned[node]['jobid']

    def check_availability(self, node, cpus, memory):
        """Check if a node has the given amount of cpus and memory available. 

        Parameters
        ----------
        node : str
            The name of the node to check availability on. 
        cpus : int
            The number of cpu cores to check.  
        memory : int
            The amount of memory (in bytes) to check.
        
        Returns
        -------
        bool
            True if the node has the given amount of cpus and memory available. 
            False otherwise.
        """
        ret = False
        if node in self.available:
            specs = self.available[node]
            if ((specs['cpus'] - cpus) >= self.MIN_CPUS and 
            (specs['memory'] - memory) >= self.MIN_MEMORY):
                ret = True
        return ret


    def get_available_node(self, cpus, memory):
        """Get a node on the cluster which can accomodate the given cpus and 
        memory. 

        A node which has the requested number of cpus and memory available will 
        be returned. If no node has the requested specifications then None is 
        returned. None is also returned if multiple nodes can fulfill the 
        request together but no one node can do so by itself.

        Parameters
        ----------
        cpus : int
            The number of cpu cores needed.  
        memory : int
            The amount of memory (in bytes) needed. 

        Returns
        -------
        str
            The name of a node which can accomodate the given cpus and memory. 
            None if no node can accomodate the request.
        """
        ret = None
        for node in self.available.keys():
            if (self.check_availability(node, cpus, memory)):
                ret = node
                break
        return ret

    def utilize_resources(self, node, cpus, memory, jobid):
        """Mark the given cpus and memory in the given node as unavailable. 

        This function is called to reserve or mark unavailable the cpu and 
        memory resources when a program needing the same is ran on the node. 

        Parameters
        ----------
        node : str
            The name of the node which would mark its resources unavailable. 
        cpus : int
            The number of cpu cores to reserve. 
        memory : int
            The amount of memory (in bytes) to reserve. 
        jobid : int
            The jobid to which the node's allocation request belongs to.

        Raises
        ------
        ValueError
            If not enough resources available or the jobid doesn't match. 
        """
        if (node not in self.available or self.available[node]['jobid'] != jobid
        or not self.check_availability(node, cpus, memory)):
            raise ValueError (
                "There are not enough hardware resources available. Please "
                "allocate more hardware resources and try again.\n"
            )
        self.available[node]['cpus'] -= cpus
        self.available[node]['memory'] -= memory
        self.active[self.available[node]['jobid']].add(node)

    def release_resources(self, node, cpus, memory, jobid):
        """Mark the given cpus and memory in the given node as available. 

        This function is called to release previously busy/unavailable 
        resources on the given node. Usually used after a program has ended. 

        Parameters
        ----------
        node : str
            The name of the node which would mark its resources available. 
        cpus : int
            The number of cpu cores to release. 
        memory : int
            The amount of memory (in bytes) to release. 
        jobid : int
            The jobid to which the node's allocation request belongs to. 

        Raises
        ------
        ValueError
            If the given node doesn't exist. 
        """
        if node in self.assigned and self.available[node]['jobid'] == jobid:
            self.available[node]['cpus'] += cpus
            self.available[node]['memory'] += memory
            if self.available[node]['cpus'] ==  self.assigned[node]['cpus'] and \
            self.available[node]['memory'] == self.assigned[node]['memory']:
                self.active[self.available[node]['jobid']].remove(node)
        else:
            raise ValueError (
                f"The given node does not exist. Please try again.\n"
            )
    
    
    def has_active_nodes(self, jobid):
        """Check if the given jobid has any nodes which are running an active 
        job or have resources reserved/unavailable presumably for a running job.

        Parameters
        ----------
        jobid : int
            The jobid for which the active nodes need to be checked.

        Returns
        -------
        bool
            True if the jobid has any nodes with jobs running. False otherwise. 
        """
        ret = True
        if jobid not in self.active or len(self.active[jobid]) == 0:
            ret = False
        return ret
    
    def is_assigned(self, jobid):
        """Check if the given jobid corresponds to a real job. 

        Parameters
        ----------
        jobid : int
            The jobid to check for.

        Returns
        -------
        bool
            True if the jobid is in the list of removed jobids. False otherwise.
        """
        ret = False
        for node in self.nodes:
            if self.assigned[node]['jobid'] == jobid:
                ret = True
                break
        return ret
    
    def get_active_jobids(self):
        """Get all the active jobids in the cluster. 

        Returns
        -------
        list
            A set containing all the active jobids in the cluster. 
        """
        return list(set(self.active.keys()))

    @staticmethod
    def set_min_free_cpus(cpus):
        HardwareResources.MIN_CPUS = cpus

    @staticmethod
    def set_min_free_memory(memory):
        HardwareResources.MIN_MEMORY = memory



class Container:
    """Container class to store information about the program containers. 

    These containers store the program along with any dependencies the program
    may need to run. They also store the necessary libraries needed to connect 
    to the cluster and run a worker within the container. 

    Attributes
    ----------
    name : str
        The name of the container. 
    cpus : int
        The number of cpus the container needs.  
    memory : int
        The amount of memory in bytes needed by the container.  
    path : str
        The path at which the container is stored. 
    directories : dict
        A dictionary containing all the paths to be bind-mounted to the 
        container. Key represents a path in the container's host, value 
        represents a path in the container itself. 

    Methods
    -------
    add_directory(src, dst=None)
        Add a directory to bind-mount to the container.
    get_info_dict()
        Returns a dictionary with all the information about the container.
    get_command()
        Returns the command to run the container.
    get_runtime()
        Returns the runtime application (docker/apptainer) to run the container.
    get_runtime_directive()
        Returns the runtime application's directive which runs a container.
    set_runtime(runtime)
        Set the runtime application to run the container.
    set_runtime_directive(runtime, directive)
        Set the runtime application's directive which runs a container.
    """

    _runtime_directives = {"apptainer": "exec", "docker": "run"}

    _runtime = "apptainer"
    
    def __init__(self, name, spec_dict):
        """
        Parameters
        ----------
        name : str
            The name of the container.
        spec_dict : dict
            A dictionary containing the specifications of the container. The 
            specifications include CPUs, Memory, Path, and Dirs. The Memory can
            be in gigabytes, megabytes, or bytes. '500MB' or '2GB' are valid.
            A valid spec_dict can look like:
            {
            'CPUs': 4,
            'Memory': '8G',
            'Path': '/home/user/work/containers/container.sif',
            'Dirs': {
            '/home/work/inputs': '/inputs'
            '/home/work/shared': '/shared'}}
        """
        self.name = name
        self.cpus = spec_dict['CPUs']
        memory_parsed = parse_bytes(spec_dict['Memory'])
        memory_parsed //= 10**9
        self.memory = memory_parsed
        self.path = spec_dict['Path']
        if spec_dict['Dirs'] is None:
            spec_dict['Dirs'] = {}
        self.directories = spec_dict['Dirs']

    def add_directory(self, src, dst=None):
        """Mount a host's directory to a path in the container.
        
        This function takes a source directory on the host and a destination 
        path in the container. The source directory would be bind-mounted to 
        the destination path. If the destination path is not provided, then 
        the source directory is bind-mounted to the same path in the container.

        Parameters
        ----------
        src : str
            The path of the source directory on the host.
        dst : str
            The destination path in the container. Defaults to None.
        """
        if dst is None:
            dst = src
        self.directories[src] = dst

    def get_info_dict(self):
        """Return a dictionary containing all the information about the 
        container.

        Returns
        -------
        dict
            A dictionary containing the Name, CPUs, Memory, Path, and Dirs of 
            the container.
        """
        ret = {}
        ret['Name'] = self.name
        ret['CPUs'] = self.cpus
        ret['Memory'] = self.memory
        ret['Path'] = self.path
        ret['Dirs'] = self.directories
        return ret

    def get_command(self, env_vars=None):
        """Return the command to run the container.
        
        The function assumes '--bind' to be the binding flag for the runtime
        application. The command is returned as a list of strings.

        Parameters
        ----------
        env_vars : dict
            A dictionary containing the environment variables to be set in the 
            container. Defaults to None.

        Returns
        -------
        list
            A list of strings containing the command to run the container. 
            Joining the elements of the list with a space would give the
            complete command.
        """
        command = []
        command.append(Container.get_runtime())
        command.append(Container.get_runtime_directive())
        command.append("--userns")
        command.append("--compat")
        if env_vars is None:
            env_vars = {}
        for name, value in env_vars.items():
            command.append("--env")
            command.append(f"{name}={value}")
        for src, dst in self.directories.items():
            if dst is None or dst == "":
                dst = src
            command.append("--bind")
            command.append(f"{src}:{dst}")
        curr_dir = os.getcwd()
        command.append("--home")
        command.append(curr_dir)
        command.append("--cwd")
        command.append(curr_dir)
        command.append(self.path)
        return command

    @staticmethod
    def get_runtime():
        if Container._runtime is None or "":
            raise ValueError(
                "Runtime has not been set. Please set it using set_runtime()."
            )
        return Container._runtime

    @staticmethod
    def get_runtime_directive():
        if Container._runtime not in Container._runtime_directives:
            raise ValueError( 
                "Runtime has not been set. Please set it using "
                "set_runtime_directive()."
            )
        return Container._runtime_directives[Container._runtime]
    
    @staticmethod
    def set_runtime(runtime):
        Container._runtime = runtime

    @staticmethod
    def set_runtime_directive(runtime, directive):
        Container._runtime_directives[runtime] = directive