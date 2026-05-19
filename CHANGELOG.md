# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- New workflow architecture figure in [`docs/images/scalable_architecture.png`](docs/images/scalable_architecture.png).

### Changed

- Expanded demo documentation context and examples in [`docs/demo.rst`](docs/demo.rst).
- Replaced repo-specific paths with generic paths in documentation for portability.
- Updated block-style demo formatting in documentation.

### Documentation

- Added [`DISCLAIMER.md`](DISCLAIMER.md).
- Updated [`LICENSE.md`](LICENSE.md) to BSD-3-Clause wording.

## [1.1.0]

This release covers the **short-term** tier of the architectural improvement plan
(see [`plans/scalable_improvement_plan.md`](plans/scalable_improvement_plan.md)).
The package now ships with a real test suite, a CI workflow, a long list of
small correctness fixes, and a much-simplified packaging story.

### Packaging

- **Dropped versioneer.** Removed [`versioneer.py`](versioneer.py) (~2,300
  vendored lines), [`scalable/_version.py`](scalable/_version.py),
  [`setup.py`](setup.py), and [`.gitattributes`](.gitattributes). The
  package now uses the standard PEP 621 layout: a static `version` field
  in [`pyproject.toml`](pyproject.toml) and runtime version exposed via
  `importlib.metadata.version("scalable")` from
  [`scalable/__init__.py`](scalable/__init__.py).
- **`pyproject.toml` is now the single source of truth** for build,
  metadata, dependencies, scripts, pytest, ruff, and mypy. Future bumps
  are a one-line `version = "X.Y.Z"` change.
- [`docs/conf.py`](docs/conf.py) reads the release string from package
  metadata so docs stay in lockstep with `pyproject.toml`.

### Added

- **Test suite** under [`tests/unit/`](tests/) with 73 unit tests covering the
  `Settings`/logger plumbing, `HardwareResources` (including a concurrency
  stress test), `Container` runtimes, the `cacheable` decorator and its
  `*Type` wrappers, the Slurm command builders, `parse_nodelist`, and the
  `JobQueueCluster.scale` / `shutdown` contract.
- **Settings dataclass** in [`scalable/common.py`](scalable/common.py)
  exposing `settings.cache_dir` and `settings.seed`, both overridable via
  `SCALABLE_CACHE_DIR` and `SCALABLE_SEED` environment variables. The legacy
  module-level `cachedir` and `SEED` names continue to work via a
  `__getattr__` shim.
- **`SCALABLE_LOG_LEVEL` env var** — opt-in logging at any level without
  forcing applications to call `logging.basicConfig`.
- **`JobQueueCluster.shutdown()`** — explicit replacement for the previous
  side-effect of calling `scale(0)`, which is no longer overloaded as a
  shutdown signal.
- **Per-instance `Container` runtimes** — pass `runtime="docker"` (or any
  other registered runtime) to `Container(...)` so multiple cluster targets
  can use different runtimes in the same process.
- **`Container.register_runtime_directive(runtime, directive)`** — class-level
  registration of new runtime→directive mappings; existing instances keep
  the snapshot they were constructed with.
- **`HardwareResources(min_cpus=, min_memory=)`** — per-instance overrides for
  what were previously global tunables.
- **`SCALABLE_PATH_SNIFFING=0`** env var — disables the implicit
  string-as-path detection in `convert_to_type` for users who want
  deterministic cache keys without modifying decorator call sites.
- **CI workflow** at [`.github/workflows/tests.yml`](.github/workflows/tests.yml)
  matrix-testing against Python 3.9 – 3.12 on Ubuntu and macOS, plus a
  separate ruff/mypy job.
- **Tooling configuration** in [`pyproject.toml`](pyproject.toml) for
  `pytest`, `ruff`, and `mypy`.

### Changed

- **Memory parsing** is now ceiling-divided to whole gigabytes
  ([`_parse_memory_to_gb`](scalable/utilities.py)). Previously `'500MB'`
  silently truncated to `0` GB and broke `check_availability`. **Cache keys
  and resource ledger values for sub-1-GB memory specs will change.**
- **`HardwareResources` is now thread/async-safe internally.** All public
  methods take a single internal `RLock`; callers no longer need to wrap
  calls in an external lock. `is_assigned` is now `O(1)`.
- **`Container` no longer mutates a caller's `spec_dict["Dirs"]`** in place
  in a way that could alias between instances. The dict is copied before
  injecting the default `/scratch:/tmp` bind.
- **`SlurmCluster.close()`** now detects whether it's being called inside a
  running event loop and dispatches `scancel` accordingly. Previously,
  calling `close()` from an async context raised
  `RuntimeError: asyncio.run() cannot be called from a running event loop`.
- **`SlurmJob.start()`** schedules its `check_launched_worker` watchdog via
  `asyncio.get_running_loop()` (the deprecated-since-3.10
  `asyncio.get_event_loop()` is gone).
- **`Job.check_launched_worker()`** guards its access to the private Dask
  `scheduler._worker_collections` so that an upstream rename in `dask`
  degrades to a debug log rather than an exception.
- **`cacheable`** reuses a shared `diskcache.Cache` per directory (was
  opened/closed on every call) and falls back to a
  `qualname + bytecode` fingerprint when `dill.source.getsource` cannot
  read the function's source (lambdas, REPL definitions,
  `functools.partial`, …).
- **Communicator** ([`communicator/src/communicator.go`](communicator/src/communicator.go))
  now binds to `127.0.0.1` by default. Set `SCALABLE_COMM_BIND_ALL=1` to
  restore the legacy `0.0.0.0` behaviour for closed-network testing.
- **`ObjectType.__hash__`** narrows its `try/except` around dict-key
  sorting to `TypeError` only (was bare `except:`); unexpected errors now
  surface.
- **`UtilityType.__hash__`** mixes the `numpy.ndarray` `dtype` and `shape`
  into the digest so byte-identical buffers with different shapes hash
  differently.

### Deprecated

- **`HardwareResources.set_min_free_cpus(...)`** /
  **`set_min_free_memory(...)`** — emit `DeprecationWarning`. Pass
  `min_cpus=` / `min_memory=` to `HardwareResources(...)` instead.
- **`Container.set_runtime(...)`** /
  **`Container.set_runtime_directive(...)`** — emit `DeprecationWarning`.
  Pass `runtime=` to `Container(...)` (or call
  `Container.register_runtime_directive(...)` *before* construction).
- **`SlurmCluster.set_default_request_quantity(...)`** — emits
  `DeprecationWarning`. Per-cluster configuration arrives with the
  `SlurmScheduler` refactor (plan item M2).
- **Implicit path-sniffing in `convert_to_type`** — emits
  `DeprecationWarning` once per process when a string argument resolves to
  a file/dir on disk. Pass an explicit
  `arg_types={"x": FileType}` to `@cacheable` instead.

### Fixed

- Mutable default argument `worker_extra_args=[]` in
  [`Job.__init__`](scalable/core.py) shared mutation across instances.
- `--nthreads`, `--memory-limit`, `--nworkers`, and `--death-timeout` are
  now passed as strings, matching what `distributed.cli.dask_worker`
  expects.
- `worker_memory` was previously double-coerced (parsed bytes were
  integer-divided by 10⁹ and then formatted as `"...GB"`). Memory is now
  consistently in gigabytes throughout the `Job`/`Container` boundary.
- `JobQueueCluster.__init__` accepted `scheduler_options={}` as a mutable
  default; now defaults to `None` and normalizes to an empty dict.
- `JobQueueCluster.scale(0)` no longer flips `self.exited` as a side
  effect — restoring `distributed.deploy.SpecCluster` LSP compliance.
- `Job.check_launched_worker` guards `_worker_collections[-1]` against
  empty/missing collections.
- Equality-with-`None` warning in [`scalable/slurm.py`](scalable/slurm.py)
  (`self.job_node == None` → `is None`).
- `subprocess.run(..., shell=True, stdout=PIPE, stderr=PIPE)` in
  `ModelConfig` switched to `capture_output=True` and explicit
  `check=False`.
- `FileType` and `DirType` now stream files in 1 MiB chunks instead of
  reading the entire file into memory.
- `ObjectType` now raises `TypeError` (with a helpful message) instead of
  silently producing a bogus digest when `pickle` cannot serialize the
  argument.

### Security

- Communicator default bind moved to loopback (see Changed above).

### Migration notes

Most changes are source-compatible. Two situations to be aware of:

1. **Sub-1 GB containers.** Any `Container(memory="500MB")` previously had
   `memory == 0`, which made nodes silently unavailable. After this
   release the value is `1 GB`. Cache keys for the corresponding
   `cacheable` runs are unchanged (the cache key is based on function +
   args, not container metadata) but resource accounting shifts.
2. **`scale(0)` is no longer a shutdown.** Code that was relying on
   `cluster.scale(0)` to flip `exited=True` and tear down workers must
   call `cluster.shutdown()` (or `cluster.close()`) explicitly.
3. **Communicator binding.** If you were running the bootstrap on an
   isolated cluster network and depending on the `0.0.0.0` bind, set
   `SCALABLE_COMM_BIND_ALL=1` for the server invocation. The default is
   loopback.

[1.1.0]: https://github.com/JGCRI/scalable/compare/1.0.0...1.1.0
[Unreleased]: https://github.com/JGCRI/scalable/compare/1.1.0...HEAD
