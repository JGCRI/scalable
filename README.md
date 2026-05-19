<p align="center">
    <img src="docs/images/scalable_logo_nobkg.png" alt="Scalable logo" width="320" />
</p>

# Scalable

[![PyPI](https://img.shields.io/pypi/v/scalable.svg)](https://pypi.org/project/scalable/)
[![Python](https://img.shields.io/badge/python-3.11%20%7C%203.12%20%7C%203.13-blue.svg)](https://pypi.org/project/scalable/)
[![Docs](https://readthedocs.org/projects/scalable/badge/?version=latest)](https://jgcri.github.io/scalable/)

Scalable is a Python framework for orchestrating containerized, distributed workflows on HPC systems. It integrates container lifecycle management, scheduler-aware resource provisioning, and a Dask-based execution model so multi-stage scientific workflows can run consistently at scale.

## Table of Contents

- [Documentation](#documentation)
- [Installation](#installation)
- [System Requirements](#system-requirements)
- [Quick Start](#quick-start)
- [Usage](#usage)
- [Function Caching](#function-caching)
- [How to Contribute](#how-to-contribute)
- [License](#license)

## Documentation

Full documentation is available at [jgcri.github.io/scalable](https://jgcri.github.io/scalable/).

## Installation

Install from PyPI:

```bash
pip install scalable
```

Install from source:

```bash
git clone https://github.com/JGCRI/scalable.git
pip install ./scalable
```

If your shell cannot find installed scripts (for example, `scalable_bootstrap`), add the relevant scripts directory to `PATH`.

## System Requirements

- **Scheduler:** Slurm
- **Local host tools:** Docker
- **HPC host tools:** Apptainer

Platform guidance:

- Linux is recommended for bootstrapping.
- On Windows, Git Bash is recommended.
- On macOS, Terminal works as expected.

## Quick Start

Scalable includes a bootstrap process that prepares a local/HPC work environment and required containers.

1. Choose a local working directory.
2. Run the bootstrap command.
3. Follow interactive prompts.

```bash
cd <local_work_dir>
scalable_bootstrap
```

After setup completes, the workflow environment is launched on the HPC side. From the work directory, start an interactive Python session or execute a script:

```bash
python3
python3 <filename>.py
```

### SSH Recommendation

Bootstrap performs multiple SSH operations. For best reliability and usability, configure key-based passwordless SSH authentication in advance.

## Usage

### Manifest-first workflow (v2.0.0 Phase 1)

Scalable now supports a declarative manifest path for provider-neutral planning
and validation.

Create ``scalable.yaml``:

```yaml
version: 1
project:
  name: demo
targets:
  local:
    provider: local
    max_workers: 2
    threads_per_worker: 1
    processes: false
    containers: none
components:
  gcam:
    cpus: 1
    memory: 1G
tasks:
  run_gcam:
    component: gcam
```

Validate and plan without launching workers:

```bash
scalable validate ./scalable.yaml
scalable plan ./scalable.yaml --target local --dry-run --output plan.json
```

Use the session API:

```python
from scalable import ScalableSession

session = ScalableSession.from_yaml("./scalable.yaml", target="local")
plan = session.plan(dry_run=True)
print(plan.manifest_lock)
```

At runtime, create a cluster, register container targets, scale workers, and submit functions.

### 1. Create a cluster

```python
from scalable import SlurmCluster, ScalableClient

cluster = SlurmCluster(
    queue="slurm",
    walltime="02:00:00",
    account="GCIMS",
    interface="ib0",
    silence_logs=False,
)
```

### 2. Register container targets

```python
cluster.add_container(
    tag="gcam",
    cpus=10,
    memory="20G",
    dirs={"/qfs/people/user/work/gcam-core": "/gcam-core", "/rcfs": "/rcfs"},
)
cluster.add_container(
    tag="stitches",
    cpus=6,
    memory="50G",
    dirs={"/qfs/people/user": "/user", "/rcfs": "/rcfs"},
)
cluster.add_container(
    tag="osiris",
    cpus=8,
    memory="20G",
    dirs={"/rcfs/projects/gcims/data": "/data", "/qfs/people/user/test": "/scratch"},
)
```

### 3. Scale workers

```python
cluster.add_workers(n=3, tag="gcam")
cluster.add_workers(n=2, tag="stitches")
cluster.add_workers(n=3, tag="osiris")
```

### 4. Submit functions

```python
def func1(param):
    import gcam
    return gcam.__version__


def func2(param):
    import stitches
    return stitches.__version__


def func3(param):
    import osiris
    return osiris.__version__


client = ScalableClient(cluster)

fut1 = client.submit(func1, "gcam", tag="gcam")
fut2 = client.submit(func2, "stitches", tag="stitches")
fut3 = client.submit(func3, "osiris", tag="osiris")
```

### 5. Scale down when complete

```python
cluster.remove_workers(n=2, tag="gcam")
cluster.remove_workers(n=1, tag="stitches")
cluster.remove_workers(n=3, tag="osiris")
```

## Function Caching

Scalable provides a `cacheable` decorator to avoid recomputing expensive function calls across retries or interrupted runs.

```python
from scalable import cacheable


@cacheable(return_type=str, param=str)
def func1(param):
    import gcam
    return gcam.__version__


@cacheable(return_type=str, recompute=True, param=str)
def func2(param):
    import stitches
    return stitches.__version__


@cacheable
def func3(param):
    import osiris
    return osiris.__version__
```

For reliable behavior, explicitly specify argument and return types whenever possible.

## How to Contribute

Contributions are welcome.

1. Fork the repository.
2. Create a feature branch.
3. Implement changes and add or update tests.
4. Open a pull request with a clear summary and rationale.

For bug reports, feature requests, and support questions, open an issue:

https://github.com/JGCRI/scalable/issues

## License

This project is licensed under the terms in [LICENSE.md](https://github.com/JGCRI/scalable/blob/master/LICENSE.md).
