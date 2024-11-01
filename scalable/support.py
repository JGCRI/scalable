import os
import re
import shlex
from datetime import datetime


def salloc_command(account=None, chdir=None, clusters=None, exclusive=True, gpus=None, name=None, memory=None, 
                   nodes=None, partition=None, time=None, extras=None):
    """Make the salloc command for slurm.

    Parameters
    ----------
    account : str, optional
        The account to be used for the job.
    chdir : str, optional
        The directory to change to before running the job.
    clusters : str, optional
        The clusters to issue commands to for the job.
    exclusive : bool, optional
        Whether to allocate all nodes exclusively for the job.
    gpus : str, optional
        The number of GPUs to allocate for the job.
    name : str, optional
        The name of the job.
    memory : str, optional
        The amount of memory to allocate for the job.
    nodes : str, optional
        The number of nodes to allocate for the job.
    partition : str, optional
        The partition to run the job on.
    time : str, optional
        The amount of time to allocate for the job.
    extras : list, optional
        Any extra arguments to pass to the salloc command. All salloc arguments
        are technically allowed here.

    Returns
    -------
    list
        The salloc command as a list with a space as the separator.
    """
    command = ["salloc"]
    if account:
        command += ["-A", account]
    if chdir:
        command += ["-D", chdir]
    if clusters:
        command += ["-M", clusters]
    if exclusive:
        command.append("--exclusive")
    if gpus:
        command += ["-G", gpus]
    if name:
        command += ["-J", name]
    if memory:
        command += ["--mem", memory]
    if nodes:
        command += ["-N", nodes]
    if partition:
        command += ["-p", partition]
    if time:
        command += ["-t", time]
    if extras:
        command += extras
    command.append("--no-shell")
    return command

def memory_command():
    """Make the command to get the memory available on the node.
    
    Returns
    -------
    list
        The command to get the memory available on the node.
    """
    command = "free -g | grep 'Mem' | sed 's/[\t ][\t ]*/ /g' | cut -d ' ' -f 7"
    return shlex.split(command, posix=False)

def core_command():
    """Make the command to get the number of cores available on the node.
    
    Returns
    -------
    list
        The command to get the number of cores available on the node.
    """
    return ["nproc", "--all"]

def jobid_command(name):
    """Make the command to get the job id of a job with a given name.
    
    Parameters
    ----------
    name : str
        The name of the job.
    
    Returns
    -------
    list
        The command to get the job id of a job with a given name.
    """
    command = f"squeue --name={name} -o %i | tail -n 1"
    return shlex.split(command, posix=False)

def nodelist_command(name):
    """Make the command to get the nodelist of a job with a given name.
    
    Parameters
    ----------
    name : str
        The name of the job.

    Returns
    -------
    list
        The command to get the nodelist of a job with a given name.
    """
    command = f"squeue --name={name} -o %N | tail -n 1"
    return shlex.split(command, posix=False)

def jobcheck_command(jobid):
    """Make the command to check the status of a job with a given job id.
    
    Parameters
    ----------
    jobid : str
        The job id of the job.

    Returns
    -------
    list
        The command to check the status of a job with a given job id.
    """
    command = f"squeue -j {jobid} -o %i | tail -n 1"
    return shlex.split(command, posix=False)

def parse_nodelist(nodelist):
    """Parse the nodelist returned by slurm to get the nodes.
    
    Parameters
    ----------
    nodelist : str
        The nodelist returned by slurm.
        
    Returns
    -------
    list
        The list of nodes.
    """
    nodes = []
    matched = re.search(r'\[(.*)\]', nodelist)
    if matched:
        prefix = nodelist[:matched.start()]
        elements = matched.group(1).split(',')
        for element in elements:
            index = element.find('-')
            if index != -1:
                start_node = element[:index].strip() 
                end_node = element[(index + 1):].strip()
                padding_len = len(start_node)
                start = int(start_node)
                end = int(end_node)
                while start <= end:
                    node = prefix + str(start).zfill(padding_len)
                    nodes.append(node)
                    start += 1
            else:
                nodes.append(prefix + str(element.strip()))
    else:
        nodes.append(nodelist)
    return nodes

def create_logs_folder(folder, worker_name):
    """Create a folder for logs. Uses the current date and time along with 
    the given worker name to create a unique folder name.

    Parameters
    ----------
    folder : str
        The folder to create the logs folder in.
    cluster_name : str
        The name of the worker.
        
    Returns
    -------
    str
        The path to the newly created logs folder.
    """
    current_datetime = datetime.now()
    formatted_datetime = current_datetime.strftime("%Y%m%d_%H%M%S")
    folder_name = f"{worker_name}_{formatted_datetime}_logs"
    folder_path = os.path.join(os.getcwd(), folder, folder_name)
    os.makedirs(folder_path)
    return folder_path