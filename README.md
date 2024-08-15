# Scalable

Scalable is a Python library which aids in running complex workflows on HPCs by orchestrating multiple containers, requesting appropriate HPC jobs to the scheduler, and providing a python environment for distributed computing. It's designed to be primarily used with JGCRI Climate Models but can be easily adapted for any arbritrary uses.

## Installation

Use the package manager [pip](https://pip.pypa.io/en/stable/) to install scalable.

```bash
pip install scalable
```

## Setup

### Compatibility Requirements

Docker is needed to run the bootstrap script. The script itself is preferred to be ran in a linux environment. 
For Windows users, Git Bash is recommended for bootstrapping. For MacOS users, ----- TODO -----

HPC Schedulers Supported: Slurm

Tools required on HPC Host: apptainer
Tools required on Local Host: docker

### Work Directory Setup

A work directory needs to be setup on the HPC host which would ensure the presence and a structured location for all required dependencies and any outputs. The provided bootstrap script helps in setting up the work directory and the containers which would be used as workers. **It is highly recommended to use the bootstrap script to use scalable.**

Once scalable is installed through pip, navigate to a directory on your local computer where the bootstrap script can place containers, logs, and any other required dependency. The bootstrap script downloads and builds files both on your local system and the HPC system. 

```bash
[user@localhost ~]$ cd <local_work_dir>
[user@localhost ~]$ scalable_bootstrap.sh
```

Follow and answer the prompts in the bootstrap script. All the dependencies will be automatically downloaded. Once everything has been downloaded and built, the script will initiate a SSH Session with the HPC Host logging in the user to the work directory on the HPC. 

The python3 command is aliased to start a server too. Simply calling python3 will launch an interactive session with all the dependencies. A file or other arguments can also be given to python3 and they will be ran as a python file within a container. **Only files present in the current work directory and subdirectories on the HPC Host can be ran this way.** Any files stored above the current work directory would need to be copied under it to be ran. 

```bash
[user@hpchost <work_dir>]$ python3
[user@hpchost <work_dir>]$ python3 <filename>.py
```

If the script fails in the middle, or if a new session needs to be started, simply run the same command again and the bootstrap script will pickup where it left off. If everything is already installed then the script will log in to the HPC SSH session directly. For everything to function properly, it is recommended to use the bootstrap script every time scalable needs to be used. The initial setup takes time but the script connects to the HPC Host directly only checking for required dependencies if everything is already installed. 

### Manual Changes

One of the most relevant files to change for most users would be the Dockerfile. Users can just use the one provided in this repo or to make a Dockerfile of their own. The Dockerfile consists of one or more container targets along with the commands for each one. The targets included in the Dockerfile provided make containers for [gcam](https://github.com/JGCRI/gcam-core), [stitches](https://github.com/JGCRI/stitches), [osiris](https://github.com/JGCRI/osiris), along with other targets which represent some other models. The targets of [scalable](https://github.com/JGCRI/scalable) and [apptainer](https://github.com/apptainer/apptainer) are required for the bootstrap script. 

## Usage

Scalable leverages Dask to manage resources and workers on the HPC system. After launching python3, a SlurmCluster object can be made to start the Dask Scheduler. 

```bash
[user@hpchost <work_dir>]$ python3
```
```python
from scalable import SlurmCluster, ScalableClient

cluster = SlurmCluster(queue='slurm', walltime='02:00:00', account='GCIMS', interface='ib0', silence_logs=False)
```

Similar to Dask, information about the queue and the account to use on the HPC scheduler is required. `ib0` would be likely be the interface on most HPC systems. The walltime is the expected time in which the jobs assigned to can be completed in. **If walltime is lesser than the time it takes to run any single function given to the cluster, then that function will never run to completion.** Instead, the job will get stuck in a cycle of getting killed when the time is up but getting re-scheduled as it was unable to finish. For this reason, it is recommended to set the walltime to be more than the estimated time taken to complete the longest running function. The walltime can also be changed anytime after the cluster is launched and any future resource requests will include the new walltime. 

```python
cluster.add_container(tag="gcam", cpus=10, memory="20G", dirs={"/qfs/people/user/work/gcam-core":"/gcam-core", "/rcfs":"/rcfs"})
cluster.add_container(tag="stitches", cpus=6, memory="50G", dirs={"/qfs/people/user":"/user", "/rcfs":"/rcfs"})
cluster.add_container(tag="osiris", cpus=8, memory="20G", dirs={"/rcfs/projects/gcims/data":"/data", "/qfs/people/user/test":"/scratch"})
```

Before launching the workers, the configuration of worker or container targets needs to be specified. The containers to be launched as workers need to be first added by specifying their tag, number of cpu cores they need, the memory they would need, and the directory on the HPC Host to bind to the containers so that these directories are accessible by the container.

```python
cluster.add_worker(n=3, tag="gcam")
cluster.add_worker(n=2, tag="stitches")
cluster.add_worker(n=3, tag="osiris")
```

Launching workers on the cluster can be done by just adding workers to the cluster. This call will only be successful if the tags used have also had containers with the same tag added beforehand. Removing workers is similarly as easy.

```python
cluster.remove_workers(n=2, tag="gcam")
cluster.remove_workers(n=1, tag="stitches")
cluster.remove_workers(n=3, tag="osiris")
```

To compute functions on these workers, a client object needs to be made to interact with the cluster. Then functions can be submitted to be computed on the workers.

```python

def func1(param):
    import gcam
    print(f"{param=} {gcam.__version__}")
    return gcam.__version__

def func2(param):
    import stitches
    print(f"{param=} {stitches.__version__}")
    return stitches.__version__

def func3(param):
    import osiris
    print(f"{param=} {osiris.__version__}")
    return osiris.__version__

client = ScalableClient(cluster)

fut1 = client.submit(func1, "gcam", tag="gcam")
fut2 = client.submit(func2, "stitches", tag="stitches")
fut3 = client.submit(func3, "osiris", tag="osiris")
```

Note how different functions are using different libraries. These functions can't be ran by containers which don't have the libraries used. **It is therefore recommended to always specify the tag of the desired worker while submitting a function.**

The functions will print to the logs of whichever worker they ran on. Futures are returned by the client. 

The cluster can optionally be closed on exit. Automatic exit is supported. **It is recommended to check with the job scheduler on the HPC Host for any pending/zombie jobs.** Although, the cluster should cancel any such jobs on exit. 

## Contributing

Pull requests are welcome. For major changes, please open an issue first
to discuss what you would like to change.

Please make sure to update tests as appropriate.

## License

[MIT](https://choosealicense.com/licenses/mit/)