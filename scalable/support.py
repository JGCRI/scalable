from datetime import datetime
import os
import re
import shlex
import inspect
import hashlib

from itertools import islice
from tokenize import open as open_py_source

def salloc_command(account=None, chdir=None, clusters=None, exclusive=True, gpus=None, name=None, memory=None, 
                   nodes=None, partition=None, time=None, extras=None):
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
    command = "free -g | grep 'Mem' | sed 's/[\t ][\t ]*/ /g' | cut -d ' ' -f 7"
    return shlex.split(command, posix=False)

def core_command():
    return ["nproc", "--all"]

# Handle what to do if name is null or invalid
def jobid_command(name):
    command = f"squeue --name={name} -o %i | tail -n 1"
    return shlex.split(command, posix=False)

def nodelist_command(name):
    command = f"squeue --name={name} -o %N | tail -n 1"
    return shlex.split(command, posix=False)

def jobcheck_command(jobid):
    command = f"squeue -j {jobid} -o %i | tail -n 1"
    return shlex.split(command, posix=False)

def parse_nodelist(nodelist):
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

def create_logs_folder(folder, cluster_name):
    current_datetime = datetime.now()
    formatted_datetime = current_datetime.strftime("%Y%m%d_%H%M%S")
    folder_name = f"{cluster_name}_{formatted_datetime}_logs"
    folder_path = os.path.join(os.getcwd(), folder, folder_name)
    os.makedirs(folder_path)
    return folder_path

def hash_function(func):
    source_file = None
    try:
        code = func.__code__
        source_file = code.co_filename
        if not os.path.exists(source_file):
            source_code = ''.join(inspect.getsourcelines(func)[0])
            line_no = 1
            if source_file.startswith('<doctest '):
                source_file, line_no = re.match(
                    r'\<doctest (.*\.rst)\[(.*)\]\>', source_file).groups()
                line_no = int(line_no)
                source_file = '<doctest %s>' % source_file
            return source_code, source_file, line_no
        with open_py_source(source_file) as source_file_obj:
            first_line = code.co_firstlineno
            source_lines = list(islice(source_file_obj, first_line - 1, None))
        return ''.join(inspect.getblock(source_lines)), source_file, first_line
    except:
        if hasattr(func, '__code__'):
            obj = hashlib.sha256()
            obj.update(func.__code__.co_code)
            hash = int(obj.hexdigest()[:16], 16) - (1 << 63)
            return str(hash), source_file, -1
        else:
            return repr(func), source_file, -1
