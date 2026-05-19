import asyncio
import os
import subprocess
import sys
import threading
import warnings
from collections.abc import Mapping
from contextlib import contextmanager
from importlib.resources import files
from typing import Any

import yaml
from dask.utils import parse_bytes

from .common import logger

comm_port_regex = r'0\.0\.0\.0:(\d{1,5})'

# Set to True when legacy ModelConfig initialization is invoked via the
# manifest adapter/provider compatibility path. Direct user calls remain
# deprecated and emit DeprecationWarning.
_MODELCONFIG_ADAPTER_CONTEXT: bool = False


@contextmanager
def model_config_adapter_context() -> Any:
    """Temporarily suppress ModelConfig deprecation warnings.

    This context is used by the manifest-to-legacy adapter path introduced in
    Phase 1. Direct usage of :class:`ModelConfig` outside this context is
    deprecated in favor of ``scalable.yaml`` + manifest parsing.
    """

    global _MODELCONFIG_ADAPTER_CONTEXT
    previous = _MODELCONFIG_ADAPTER_CONTEXT
    _MODELCONFIG_ADAPTER_CONTEXT = True
    try:
        yield
    finally:
        _MODELCONFIG_ADAPTER_CONTEXT = previous

async def get_cmd_comm(
    port: int, communicator_path: str | None = None
) -> asyncio.subprocess.Process:
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

def run_bootstrap() -> None:
    """Run the packaged bootstrap shell script and propagate exit status.

    Raises
    ------
    SystemExit
        Raised with a non-zero code when the bootstrap command fails or is
        interrupted.
    """
    bootstrap_location = files('scalable').joinpath('scalable_bootstrap.sh')
    try:
        result = subprocess.run([os.environ.get("SHELL"), bootstrap_location.as_posix()], stdin=sys.stdin, 
                                stdout=sys.stdout, stderr=sys.stdout)
    except KeyboardInterrupt:
        logger.error("Bootstrap process interruped. Exiting...")
        sys.exit(1)
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

    def __init__(self, path: str | None = None, path_overwrite: bool = True) -> None:
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
        if not _MODELCONFIG_ADAPTER_CONTEXT:
            warnings.warn(
                "ModelConfig Dockerfile discovery is deprecated and will be "
                "replaced by scalable.yaml manifest parsing. Use "
                "scalable.manifest.parser.parse_manifest(...) and provider "
                "adapters instead.",
                DeprecationWarning,
                stacklevel=2,
            )
        # HARDCODING CURRENT DIRECTORY
        self.config_dict = {}
        cwd = os.getcwd()
        if path is None:
            self.path = os.path.abspath(os.path.join(cwd, "config_dict.yaml"))
        else:
            self.path = os.path.abspath(path)
        dockerfile_path = os.path.abspath(os.path.join(cwd, "Dockerfile"))
        list_avail_command = (
            r"sed -n 's/^FROM[[:space:]]\+[^ ]\+[[:space:]]\+AS[[:space:]]\+\([^ ]\+\)$/\\1/p' "
            + dockerfile_path
        )
        # NOTE: this shell-out is part of the legacy Dockerfile-as-config
        # behaviour scheduled for replacement under plan item M6 (manifest
        # parser); don't add features here, replace it.
        result = subprocess.run(  # noqa: S602 - legacy Dockerfile parser
            list_avail_command,
            capture_output=True,
            shell=True,
            check=False,
        )
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
            

    def update_dict(self, tag: str, key: str, value: Any) -> None:
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
    def default_spec() -> dict[str, int | str]:
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
    """Tracks CPU/memory bookkeeping for nodes allocated to a cluster.

    The previous implementation was a bag of dictionaries that callers had to
    coordinate around an external lock. This refactor:

    * Holds a single :class:`threading.RLock` covering every public method, so
      concurrent calls from a Dask scheduler or asyncio worker tasks are safe
      without callers needing to manage external synchronization.
    * Treats ``MIN_CPUS`` / ``MIN_MEMORY`` as instance defaults that can still
      be overridden globally via the legacy
      :meth:`set_min_free_cpus` / :meth:`set_min_free_memory` static methods,
      but each instance can also override them in its constructor.
    * Returns immutable views (copies) from accessors so callers cannot mutate
      internal state by accident.

    Notes
    -----
    Memory values throughout this class are nominally in **gigabytes** to
    match what the Slurm ``free -g`` command returns. Mixing units inside a
    single instance is unsupported.

    Methods
    -------
    assign_resources(node, cpus, memory, jobid)
        Store allocated node data.
    remove_jobid_nodes(jobid)
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
    """

    #: Default minimum CPU cores that must remain free on a node before
    #: :meth:`check_availability` will allow further reservations. Treated as
    #: a class-level default; per-instance overrides take precedence.
    MIN_CPUS = 10

    #: Default minimum memory (in GB) that must remain free on a node before
    #: :meth:`check_availability` will allow further reservations.
    MIN_MEMORY = 20

    def __init__(
        self, *, min_cpus: int | None = None, min_memory: int | None = None
    ) -> None:
        """Initialize an empty resource ledger.

        Parameters
        ----------
        min_cpus : int, optional
            Per-instance override for :attr:`MIN_CPUS`.
        min_memory : int, optional
            Per-instance override for :attr:`MIN_MEMORY`.
        """
        self.nodes = []
        self.assigned = {}
        self.available = {}
        self.active = {}
        self._lock = threading.RLock()
        # Per-instance copies; default to current class attribute values so
        # the legacy ``set_min_free_*`` static setters continue to influence
        # *future* instances but cannot retroactively change existing ones.
        self._min_cpus = HardwareResources.MIN_CPUS if min_cpus is None else min_cpus
        self._min_memory = (
            HardwareResources.MIN_MEMORY if min_memory is None else min_memory
        )

    # ------------------------------------------------------------------
    # Mutators
    # ------------------------------------------------------------------

    def assign_resources(self, node: str, cpus: int, memory: int, jobid: str) -> bool:
        """Store the information of an allocated node.

        Parameters
        ----------
        node : str
            The name of the node which was allocated.
        cpus : int
            The number of cpu cores in the node.
        memory : int
            The amount of memory (in GB) in the node.
        jobid : int
            The jobid to which the node's allocation request belongs to.

        Returns
        -------
        bool
            ``True`` if the node was newly recorded, ``False`` if it was
            already known (the call is a no-op in that case).
        """
        allotted = {"cpus": cpus, "memory": memory, "jobid": jobid}
        with self._lock:
            if node in self.assigned or node in self.available:
                return False
            self.assigned[node] = allotted
            self.available[node] = allotted.copy()
            self.nodes.append(node)
            self.active.setdefault(jobid, set())
            return True

    def remove_jobid_nodes(self, jobid: str) -> None:
        """Remove all the nodes belonging to the given jobid."""
        with self._lock:
            self.active.pop(jobid, None)
            delete = [
                node for node in self.nodes if self.assigned[node]["jobid"] == jobid
            ]
            for node in delete:
                self.assigned.pop(node, None)
                self.available.pop(node, None)
                self.nodes.remove(node)

    def utilize_resources(self, node: str, cpus: int, memory: int, jobid: str) -> None:
        """Mark the given cpus and memory in the given node as unavailable.

        Raises
        ------
        ValueError
            If not enough resources are available or the jobid doesn't match.
        """
        with self._lock:
            if (
                node not in self.available
                or self.available[node]["jobid"] != jobid
                or not self._check_availability_locked(node, cpus, memory)
            ):
                raise ValueError(
                    "There are not enough hardware resources available. Please "
                    "allocate more hardware resources and try again.\n"
                )
            self.available[node]["cpus"] -= cpus
            self.available[node]["memory"] -= memory
            self.active[self.available[node]["jobid"]].add(node)

    def release_resources(self, node: str, cpus: int, memory: int, jobid: str) -> None:
        """Mark the given cpus and memory in the given node as available.

        Raises
        ------
        ValueError
            If the given node doesn't exist for this jobid.
        """
        with self._lock:
            if (
                node in self.assigned
                and node in self.available
                and self.available[node]["jobid"] == jobid
            ):
                self.available[node]["cpus"] += cpus
                self.available[node]["memory"] += memory
                fully_idle = (
                    self.available[node]["cpus"] == self.assigned[node]["cpus"]
                    and self.available[node]["memory"] == self.assigned[node]["memory"]
                )
                if fully_idle:
                    active_set = self.active.get(self.available[node]["jobid"])
                    if active_set is not None:
                        active_set.discard(node)
            else:
                raise ValueError(
                    f"The given node {node!r} does not exist for jobid {jobid!r}.\n"
                )

    # ------------------------------------------------------------------
    # Accessors
    # ------------------------------------------------------------------

    def get_node_jobid(self, node: str) -> str:
        """Get the jobid of the allocation request for the given node.

        Raises
        ------
        ValueError
            If the node's information is not stored/invalid node.
        """
        with self._lock:
            if node not in self.assigned:
                raise ValueError("The given node doesn't exist. Please try again.\n")
            return self.assigned[node]["jobid"]

    def check_availability(self, node: str, cpus: int, memory: int) -> bool:
        """Check if a node has the given amount of cpus and memory available."""
        with self._lock:
            return self._check_availability_locked(node, cpus, memory)

    def _check_availability_locked(self, node: str, cpus: int, memory: int) -> bool:
        """Internal availability check that assumes the lock is held."""
        if node not in self.available:
            return False
        specs = self.available[node]
        return (
            (specs["cpus"] - cpus) >= self._min_cpus
            and (specs["memory"] - memory) >= self._min_memory
        )

    def get_available_node(self, cpus: int, memory: int) -> str | None:
        """Get a node which can accommodate the given cpus and memory.

        Returns
        -------
        str or None
            The name of a node which can accommodate the request, or ``None``
            if no single node can.
        """
        with self._lock:
            for node in self.available:
                if self._check_availability_locked(node, cpus, memory):
                    return node
            return None

    def has_active_nodes(self, jobid: str) -> bool:
        """Check if the given jobid has any nodes with reserved resources."""
        with self._lock:
            entry = self.active.get(jobid)
            return bool(entry)

    def is_assigned(self, jobid: str) -> bool:
        """Check if the given jobid corresponds to a tracked job.

        Notes
        -----
        Previously a linear scan over :attr:`nodes`. Now O(1) via :attr:`active`.
        """
        with self._lock:
            return jobid in self.active

    def get_active_jobids(self) -> list[str]:
        """Return a list of all jobids currently tracked."""
        with self._lock:
            return list(self.active.keys())

    # ------------------------------------------------------------------
    # Legacy global tunables (deprecated; prefer constructor arguments)
    # ------------------------------------------------------------------

    @staticmethod
    def set_min_free_cpus(cpus: int) -> None:
        """Set the class-default minimum free CPUs.

        .. deprecated::
            Pass ``min_cpus=`` to :class:`HardwareResources` instead. The
            class-level mutation only affects *future* instances and is
            inherently process-global.
        """
        warnings.warn(
            "HardwareResources.set_min_free_cpus is deprecated; pass "
            "min_cpus= to HardwareResources(...) instead.",
            DeprecationWarning,
            stacklevel=2,
        )
        HardwareResources.MIN_CPUS = cpus

    @staticmethod
    def set_min_free_memory(memory: int) -> None:
        """Set the class-default minimum free memory.

        .. deprecated::
            Pass ``min_memory=`` to :class:`HardwareResources` instead.
        """
        warnings.warn(
            "HardwareResources.set_min_free_memory is deprecated; pass "
            "min_memory= to HardwareResources(...) instead.",
            DeprecationWarning,
            stacklevel=2,
        )
        HardwareResources.MIN_MEMORY = memory



def _parse_memory_to_gb(value: str | int | float | None, *, default: int = 0) -> int:
    """Parse a memory string/int into integer gigabytes.

    Examples
    --------
    >>> _parse_memory_to_gb('8G')
    8
    >>> _parse_memory_to_gb('500MB')
    1
    >>> _parse_memory_to_gb('2GB')
    2
    >>> _parse_memory_to_gb(0)
    0

    Parameters
    ----------
    value : str | int | None
        Memory specification. Strings are parsed via :func:`dask.utils.parse_bytes`.
        Integers are interpreted as already being in **bytes**.
    default : int
        Returned when ``value`` is falsy/``None``.

    Returns
    -------
    int
        Memory rounded **up** to whole gigabytes (so ``500MB`` no longer
        truncates to ``0`` like the previous integer-floor implementation).
    """
    if value in (None, "", 0):
        return default
    if isinstance(value, (int, float)):
        bytes_ = int(value)
    else:
        bytes_ = parse_bytes(str(value))
    if bytes_ <= 0:
        return default
    # Ceiling-divide to whole GB; this avoids the historical truncation where
    # '500MB' silently became 0 GB and broke availability checks.
    one_gb = 10 ** 9
    return max(1, (bytes_ + one_gb - 1) // one_gb)


class Container:
    """Information about a per-tag container that workers will execute inside.

    Attributes
    ----------
    name : str
        The container's tag.
    cpus : int
        The number of CPU cores the container should reserve.
    memory : int
        The amount of memory **in gigabytes** needed by the container.
    path : str
        The path at which the container image is stored.
    directories : dict
        Bind-mount mapping (host path → container path).
    preload_script : str | None
        Optional Dask worker preload script.
    runtime : str
        Container runtime selected for *this* container instance
        (``"apptainer"`` or ``"docker"``). Each instance is independent —
        unlike the previous implementation, two ``Container`` objects in the
        same process can use different runtimes.

    Notes
    -----
    The class-level ``_runtime`` and ``_runtime_directives`` attributes are
    retained as **process-wide defaults** so the legacy
    :meth:`set_runtime` / :meth:`set_runtime_directive` static API continues
    to work, but they emit ``DeprecationWarning``.
    """

    # Process-wide defaults. Per-instance overrides live on ``self.runtime``
    # and ``self._runtime_directives``.
    _runtime_directives = {"apptainer": "exec", "docker": "run"}
    _runtime = "apptainer"

    def __init__(
        self,
        name: str,
        spec_dict: dict[str, Any],
        *,
        runtime: str | None = None,
    ) -> None:
        """Initialize a container description from a spec dict.

        Parameters
        ----------
        name : str
            The container's tag.
        spec_dict : dict
            Required keys: ``CPUs``, ``Memory``, ``Path``, ``Dirs``,
            ``PreloadScript``. ``Memory`` accepts strings (``'8G'``,
            ``'500MB'``) or integer bytes.
        runtime : str, optional
            Override the runtime for this instance only (``"apptainer"`` or
            ``"docker"``). Defaults to the class-wide :attr:`_runtime`.
        """
        self.name = name
        self.cpus = spec_dict["CPUs"]
        self.memory = _parse_memory_to_gb(spec_dict.get("Memory"))
        self.path = spec_dict.get("Path")
        dirs = spec_dict.get("Dirs") or {}
        # Mutate the caller's dict only if it was provided; otherwise build a
        # fresh one so two Container instances don't accidentally alias.
        dirs = dict(dirs)
        dirs.setdefault("/scratch", "/tmp")
        # Persist the normalized dict back into the spec_dict for callers that
        # depend on the previous side-effect of injecting ``/scratch``.
        spec_dict["Dirs"] = dirs
        self.directories = dirs
        self.preload_script = spec_dict.get("PreloadScript")

        # Per-instance runtime + directives
        self.runtime = runtime if runtime is not None else Container._runtime
        # Snapshot the directive table so later mutations to the class
        # default don't change this instance's behaviour.
        self._runtime_directives_local = dict(Container._runtime_directives)

    def add_directory(self, src: str, dst: str | None = None) -> None:
        """Bind-mount ``src`` (host) to ``dst`` (container, defaults to ``src``)."""
        if dst is None:
            dst = src
        self.directories[src] = dst

    def get_info_dict(self) -> dict[str, Any]:
        """Return a dictionary describing the container.

        Returns
        -------
        dict
            Keys: ``Name``, ``CPUs``, ``Memory``, ``Path``, ``Dirs``,
            ``PreloadScript``.
        """
        return {
            "Name": self.name,
            "CPUs": self.cpus,
            "Memory": self.memory,
            "Path": self.path,
            "Dirs": self.directories,
            "PreloadScript": self.preload_script,
        }

    def get_command(self, env_vars: Mapping[str, Any] | None = None) -> list[str]:
        """Return the argv used to launch this container."""
        command = [self.get_runtime(), self.get_runtime_directive()]
        # Apptainer-specific flags. Docker users will need a different builder.
        if self.runtime == "apptainer":
            command += ["--userns", "--compat"]
        if env_vars:
            for name, value in env_vars.items():
                command += ["--env", f"{name}={value}"]
        for src, dst in self.directories.items():
            if not dst:
                dst = src
            command += ["--bind", f"{src}:{dst}"]
        curr_dir = os.getcwd()
        command += ["--home", curr_dir, "--cwd", curr_dir, self.path]
        return command

    # ------------------------------------------------------------------
    # Runtime accessors (per-instance)
    # ------------------------------------------------------------------

    def get_runtime(self) -> str:
        """Return this container's runtime name."""
        if not self.runtime:
            raise ValueError(
                "Runtime has not been set on this Container instance."
            )
        return self.runtime

    def get_runtime_directive(self) -> str:
        """Return the runtime directive (``exec``/``run``/...) for this instance."""
        if self.runtime not in self._runtime_directives_local:
            raise ValueError(
                f"No directive registered for runtime {self.runtime!r}. "
                "Use Container.register_runtime_directive(runtime, directive)."
            )
        return self._runtime_directives_local[self.runtime]

    # ------------------------------------------------------------------
    # Legacy class-level static API (deprecated)
    # ------------------------------------------------------------------

    @staticmethod
    def set_runtime(runtime: str) -> None:
        """Set the *process-wide default* container runtime.

        .. deprecated::
            Pass ``runtime=`` to :class:`Container` instead. The static
            setter affects only future instances and prevents heterogeneous
            runtimes from coexisting in one process.
        """
        warnings.warn(
            "Container.set_runtime is deprecated; pass runtime= to "
            "Container(...) instead.",
            DeprecationWarning,
            stacklevel=2,
        )
        Container._runtime = runtime

    @staticmethod
    def set_runtime_directive(runtime: str, directive: str) -> None:
        """Register a runtime→directive mapping at the process level.

        .. deprecated::
            Per-instance runtimes snapshot the directive table on
            construction. Register directives *before* creating containers.
        """
        warnings.warn(
            "Container.set_runtime_directive is deprecated; register "
            "directives before constructing Container instances.",
            DeprecationWarning,
            stacklevel=2,
        )
        Container._runtime_directives[runtime] = directive

    @staticmethod
    def register_runtime_directive(runtime: str, directive: str) -> None:
        """Register a runtime→directive mapping at the class default level.

        New :class:`Container` instances will pick up the registration via
        their per-instance snapshot. Existing instances are unaffected.
        """
        Container._runtime_directives[runtime] = directive
