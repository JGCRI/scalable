# flake8: noqa
from .core import JobQueueCluster
from .slurm import SlurmCluster
from .caching import *
from .common import SEED

from ._version import get_versions

__version__ = get_versions()["version"]
del get_versions

from . import _version
__version__ = _version.get_versions()['version']
