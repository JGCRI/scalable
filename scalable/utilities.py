import subprocess
import yaml
import os
import asyncio
from dask.utils import parse_bytes
import re

from .common import logger

comm_port_regex = r'0\.0\.0\.0:(\d{1,5})'

async def get_cmd_comm(port, communicator_path=None):
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

def get_comm_port(logpath=None):
    if logpath is None:
        logpath = "./communicator.log"
    ret = -1
    with open(logpath, 'r') as file:
        for line in file:
            match = re.search(comm_port_regex, line)
            if match:
                port = int(match.group(1))
                if 0 <= port <= 65535:
                    ret = port
                    break
    return ret



class ModelConfig:

    def __init__(self, path=None, path_overwrite=True):
        # HARDCODING CURRENT DIRECTORY
        self.config_dict = {}
        cwd = os.getcwd()
        if path is None:
            self.path = os.path.abspath(os.path.join(cwd, "scalable", "config_dict.yaml"))
        dockerfile_path = os.path.abspath(os.path.join(cwd, "scalable", "Dockerfile"))
        list_avial_command =f"sed -n 's/^FROM[[:space:]]\+[^ ]\+[[:space:]]\+AS[[:space:]]\+\([^ ]\+\)$/\\1/p' {dockerfile_path}"
        result = subprocess.run(list_avial_command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, shell=True)
        if result.returncode == 0:
            avail_containers = result.stdout.decode('utf-8').split('\n')
            avail_containers = result.stdout.decode('utf-8').split('\n')
            try:
                avail_containers.remove("build_env")
            except ValueError:
                pass
            avail_containers = list(filter(bool, avail_containers))
        else:
            logger.error("Failed to run sed command...manual entry of container info may be required")
            return
        if not os.path.exists(self.path):
            logger.warn("No resource dict found...making one")
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
                self.config_dict[container]['Path'] = container_path
            with open(self.path, 'w') as config:
                yaml.dump(self.config_dict, config)
            

    def update_dict(self, tag, key, value):
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
        config = {}
        config['CPUs'] = 4
        config['Memory'] = "8G"
        return config


class HardwareResources:

    MIN_CPUS = 1
    MIN_MEMORY = 2

    def __init__(self):
        self.nodes = []
        self.assigned = {}
        self.available = {}
        self.active = {}

    def assign_resources(self, node, cpus, memory, jobid):
        allotted = {'cpus': cpus, 'memory': memory, 'jobid': jobid}
        if node not in self.assigned and node not in self.available:
            self.assigned[node] = allotted
            self.available[node] = allotted.copy()
            self.nodes.append(node)
            if jobid not in self.active:
                self.active[jobid] = set()
        else:
            raise ValueError(
                "The node already exists. New resources to an existing node \
                cannot be assigned. Please try again.\n"
            )
    
    def remove_jobid_nodes(self, jobid):
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
        if node not in self.available:
            raise ValueError(
                "The given node doesn't exist. Please try again.\n"
            )
        else:
            return self.available[node]['jobid']

    def check_availability(self, cpus, memory):
        ret = None
        for node, specs in self.available.items():
            if (specs['cpus'] - cpus) > self.MIN_CPUS and (specs['memory'] - memory) > self.MIN_MEMORY:
                ret = node
                break
        return ret

    def utilize_resources(self, node, cpus, memory, jobid):
        if node not in self.available or self.available[node]['jobid'] != jobid:
            raise ValueError (
                "There are not enough hardware resources available. Please \
                allocate more hardware resources and try again.\n"
            )
        self.available[node]['cpus'] -= cpus
        self.available[node]['memory'] -= memory
        self.active[self.available[node]['jobid']].add(node)

    def release_resources(self, node, cpus, memory, jobid):
        if node in self.available and node in self.assigned:
            if self.available[node]['jobid'] != jobid:
                return
            self.available[node]['cpus'] += cpus
            self.available[node]['memory'] += memory
        if self.available[node]['cpus'] ==  self.assigned[node]['cpus'] and \
        self.available[node]['memory'] == self.assigned[node]['memory']:
            self.active[self.available[node]['jobid']].remove(node)
    
    def has_active_nodes(self, jobid):
        ret = True
        if jobid not in self.active or len(self.active[jobid]) == 0:
            ret = False
        return ret
    
    @staticmethod
    def set_min_free_cpus(cpus):
        HardwareResources.MIN_CPUS = cpus

    @staticmethod
    def set_min_free_memory(memory):
        HardwareResources.MIN_MEMORY = memory



class Container:

    _runtime_directives = {"apptainer": "exec", "docker": "run"}

    _runtime = "apptainer"

    def __init__(self, name, cpus, memory, path, directories=None) -> None:
        self.name = name
        self.cpus = cpus
        memory_parsed = parse_bytes(memory)
        memory_parsed //= 10**9
        self.memory = memory_parsed
        self.path = path
        if  directories is None:
            directories = {}
        self.directories = directories
    
    def __init__(self, name, spec_dict):
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
        if dst is None:
            dst = src
        self.directories[src] = dst

    def get_info_dict(self):
        ret = {}
        ret['Name'] = self.name
        ret['CPUs'] = self.cpus
        ret['Memory'] = self.memory
        ret['Path'] = self.path
        ret['Directories'] = self.directories
        return ret

    def get_command(self):
        command = []
        command.append(Container.get_runtime())
        command.append(Container.get_runtime__directive())
        for src, dst in self.directories.items():
            if dst is None or dst == "":
                dst = src
            command.append("--bind")
            command.append(f"{src}:{dst}")
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
    def get_runtime__directive():
        if Container._runtime not in Container._runtime_directives:
            raise ValueError(
                "Runtime has not been set. Please set it using \
                set_runtime_directive()s."
            )
        return Container._runtime_directives[Container._runtime]
    
    @staticmethod
    def set_runtime(runtime):
        Container._runtime = runtime

    @staticmethod
    def set_runtime_directive(runtime, directive):
        Container._runtime_directives[runtime] = directive