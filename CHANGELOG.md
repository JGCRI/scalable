# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [2.0.0a4] — Phase 4: AI Assistant Features

### Added

- **AI assistant subsystem** (`scalable.ai`) with pluggable LLM backend
  protocol and heuristic-only fallback mode:
  - `AIBackend` protocol with `NoOpBackend`, `OpenAIBackend`, `OllamaBackend`
  - Backend selection via `SCALABLE_AI_BACKEND` environment variable
  - All assistants functional without LLM via deterministic heuristics
- **Component onboarding assistant** (`scalable init-component`):
  - Directory scanning for language, build system, and runtime detection
  - Resource estimation heuristics based on detected language/build system
  - Container file detection (Dockerfile, Apptainer)
  - Mount point suggestions from data directory conventions
  - Proposed `ComponentConfig`-compatible YAML output
- **Failure diagnosis assistant** (`scalable diagnose`):
  - Rule-based failure taxonomy: `oom`, `walltime`, `mount_missing`,
    `import_error`, `connection`, `credential`, `model_runtime`
  - Evidence extraction from telemetry events
  - Suggested fixes with confidence ratings
  - Text and JSON output formats
- **Plan explanation assistant** (`scalable explain`):
  - Human-readable narrative from `plan.json` files
  - Sections: overview, resource allocation, execution strategy, recommendations
  - Historical context from telemetry when available
- **Workflow composition assistant** (`scalable compose`):
  - Natural-language to workflow generation
  - Known model pattern detection (GCAM, Stitches, Demeter, Tethys, Xanthos, Hector)
  - Generates `workflow.py`, `components.yaml`, `README.generated.md`
  - Python syntax validation via `ast.parse`
- **Manifest migration assistant** (`scalable migrate`):
  - Provider migration proposals (slurm→kubernetes, slurm→aws, etc.)
  - Schema version upgrade guidance
  - Overlay-based output for non-destructive changes
  - General manifest optimization suggestions
- **Prompt template system** (`scalable.ai.prompts`) for all assistants.
- **Heuristic analysis engine** (`scalable.ai.heuristics`):
  - File/directory scanner for model detection
  - Language/runtime classifier
  - Resource estimation from build system analysis
  - Failure pattern matching with regex taxonomy
- **`ScalableSession.plan(objective=, policy=)`** now functional:
  - Supported objectives: `"minimize cost"`, `"minimize time"`, `"balance"`
  - Supported policies: `"safe"`, `"aggressive"`, `"manual"`
  - Heuristic-based resource/worker adjustments
- **Settings extensions** (`scalable.common.Settings`):
  - `ai_backend` (`SCALABLE_AI_BACKEND`)
  - `ai_model` (`SCALABLE_AI_MODEL`)
  - `ai_endpoint` (`SCALABLE_AI_ENDPOINT`)
- **Public API**: `onboard_component`, `diagnose_run`, `explain_plan`,
  `compose_workflow`, `migrate_manifest` and associated result types
  exported from `scalable.__init__` with optional-dep guards.
- New docs page: `ai_assistants.rst`.
- Populated `[project.optional-dependencies] ai` with `jinja2 >= 3.1`
  and `rich >= 13.0`.

### Changed

- Bumped version to `2.0.0a4`.
- CLI `_STUB_COMMANDS` is now empty — all Phase 4 commands (`diagnose`,
  `explain`, `init-component`, `compose`) are fully implemented.
- Added `migrate` as a new CLI command (not previously stubbed).
- `ScalableSession.plan(objective=, policy=)` no longer raises
  `NotImplementedError` for supported objective/policy combinations.

### Tests

- 118 new unit tests for AI modules, CLI commands, and session planning.
- Updated 2 existing tests to reflect Phase 4 behavioral changes.
- 356 total unit tests passing.

---

## [2.0.0a3] — Phase 3: Cloud and Kubernetes Execution

### Added

- **Kubernetes provider** (`scalable.providers.kubernetes.KubernetesProvider`)
  implementing the `DeploymentProvider` protocol over the Dask Kubernetes
  Operator. Maps manifest components to worker groups with per-component
  resource requests and adaptive scaling support.
- **AWS cloud provider** (`scalable.providers.cloud.aws.AWSBatchProvider`)
  wrapping `dask-cloudprovider` `FargateCluster` / `EC2Cluster`.
- **GCP provider scaffold** (`scalable.providers.cloud.gcp.GCPProvider`)
  for manifest validation only; `build_cluster()` raises `NotImplementedError`.
- **Cloud cost tables** (`scalable.providers.cloud.cost_tables`) with static
  on-demand pricing for common AWS and GCP instance types.
- **Cost estimation primitives** (`scalable.costing`):
  - `CostEstimate` dataclass with provider/region/line-item breakdown
  - `CostLineItem` with auto-computed totals
- **Artifact store layer** (`scalable.artifacts`):
  - `ArtifactStore` protocol, `ArtifactRef`, `ArtifactKind`
  - `LocalArtifactStore` (filesystem backend)
  - `FsspecArtifactStore` (S3, GCS, memory via fsspec)
  - `build_artifact_store(uri)` factory function
  - `RemoteCacheBackend` for opt-in remote cache storage
- **Manifest overlays** (`scalable.manifest.overlays`):
  - `overlays:` top-level key added to schema (additive, no version bump)
  - `targets[*].overlay:` reference field for per-target overlay selection
  - Deep-merge semantics: dicts merged recursively, lists/scalars replaced
  - `ManifestModel.raw_unresolved` for pre-overlay provenance tracking
- **`scalable run` CLI verb** (`scalable.cli.cmd_run`):
  - Loads manifest with overlay resolution
  - Validates, plans, estimates cost, and optionally executes a workflow file
  - `--dry-run` mode prints plan + cost estimate as JSON
- **Provider protocol extension**: optional `estimate_cost(spec, plan)` method
  on `DeploymentProvider` with `_BaseProviderMixin` providing `None` default.
- **Telemetry extensions**:
  - `CostEvent` and `RemoteCacheEvent` in `scalable.telemetry.events`
  - `cost.jsonl` stream in `TelemetryStore`
  - Cost summary in `scalable report` output
- **Settings extensions** (`scalable.common.Settings`):
  - `cache_remote_uri` (`SCALABLE_CACHE_REMOTE`)
  - `default_storage` (`SCALABLE_DEFAULT_STORAGE`)
  - `runs_dir_remote` (`SCALABLE_RUNS_DIR_REMOTE`)
- **Provider registry**: `kubernetes`, `aws`, `gcp` added as builtin providers.
- **Public API**: `CostEstimate`, `KubernetesProvider`, `CloudProvider`,
  `AWSBatchProvider`, `GCPProvider`, `ArtifactStore`, `LocalArtifactStore`,
  `build_artifact_store` exported from `scalable.__init__` with optional-dep
  guards.
- New docs pages: `cloud.rst`, `kubernetes.rst`, `artifacts.rst`,
  `overlays.rst`, `cost.rst`.
- Example manifests: `scalable.gke.yaml`, `scalable.aws.yaml`,
  `scalable.overlays.yaml`.
- Populated `[project.optional-dependencies]` `cloud` and `kubernetes` extras.

### Changed

- Bumped version to `2.0.0a3`.
- `_TOP_LEVEL_KEYS` in `scalable.manifest.parser` now includes `"overlays"`.
- `load_manifest()` / `parse_manifest()` accept `target_name` and
  `overlay_name` keyword arguments for overlay resolution.
- `scalable run` removed from `_STUB_COMMANDS` in CLI main.

### Tests

- Unit tests for costing, artifacts, overlays, cloud/k8s providers, cost
  tables, CLI run verb, telemetry cost events, and Phase 3 Settings.
- 238 total unit tests passing.

---

## [Unreleased]

### Added

- **Phase 2 telemetry package** implementing run history, event schemas, and
  report aggregation:
  - `scalable.telemetry.events`
  - `scalable.telemetry.store`
  - `scalable.telemetry.collectors`
  - `scalable.telemetry.runtime`
- **Run history store** for manifest-driven sessions under `.scalable/runs/`
  with persisted `manifest.yaml`, `plan.json`, `manifest.lock`, `run.json`,
  task/resource/worker/failure/cache/artifact JSONL streams, and `summary.json`.
- **`scalable report` CLI command** (text + JSON output) replacing the Phase 1
  report stub.
- **Deterministic advising API**:
  - `ResourceAdvisor.from_history(...)`
  - `ResourceAdvisor.recommend(...)`
  - `ResourceRecommendation` result payload
- **Artifact metadata recording API** via `ScalableSession.record_artifact(...)`.
- New docs pages:
  - `docs/telemetry.rst`
  - `docs/advising.rst`

### Changed

- `ScalableSession` now initializes and finalizes telemetry by default for
  manifest-driven runs (configurable).
- `ScalableClient.submit` and `ScalableClient.map` now emit task lifecycle
  telemetry through future callbacks.
- `cacheable` now emits cache hit/miss telemetry events when telemetry is
  active.
- `LocalProvider` and `SlurmProvider` now emit worker/cluster telemetry events.
- `scalable.__all__` now exports `ResourceAdvisor` and
  `ResourceRecommendation`.
- `Settings` now includes telemetry controls:
  - `runs_dir` (`SCALABLE_RUNS_DIR`)
  - `telemetry_enabled` (`SCALABLE_TELEMETRY`)
  - `telemetry_parquet` (`SCALABLE_TELEMETRY_PARQUET`)

### Tests

- Added unit and integration coverage for:
  - telemetry store lifecycle and summary generation
  - telemetry collectors and report rendering
  - `scalable report` CLI behavior
  - `ResourceAdvisor` heuristics and fallbacks
  - session telemetry end-to-end behavior on local execution

## [2.0.0a1] - 2026-05-19

### Added

- New workflow architecture figure in [`docs/images/scalable_architecture.png`](docs/images/scalable_architecture.png).
- Manifest-driven v2 entry points:
  - ``ScalableSession.from_yaml(...)`` lifecycle API
  - ``scalable validate`` CLI command
  - ``scalable plan --dry-run`` CLI command
  - deterministic ``manifest.lock`` fingerprint generation
  - provider abstraction with ``LocalProvider`` and ``SlurmProvider``
  - docs pages: [`docs/manifest.rst`](docs/manifest.rst) and [`docs/providers.rst`](docs/providers.rst)
- Provider abstractions and neutral planning data structures:
  - ``DeploymentProvider`` protocol
  - ``DeploymentSpec``, ``ScalePlan``, ``ResourceRequest``, and ``ClusterHandle``
- New CLI subcommands and namespace stubs:
  - ``scalable validate``
  - ``scalable plan --dry-run``
  - reserved stubs: ``run``, ``diagnose``, ``explain``, ``init-component``, ``compose``, ``report``
- Example manifests for docs and CI validation:
  - [`docs/examples/scalable.minimal.yaml`](docs/examples/scalable.minimal.yaml)
  - [`docs/examples/scalable.gcam_stitches.yaml`](docs/examples/scalable.gcam_stitches.yaml)

### Changed

- Expanded demo documentation context and examples in [`docs/demo.rst`](docs/demo.rst).
- Replaced repo-specific paths with generic paths in documentation for portability.
- Updated block-style demo formatting in documentation.
- Raised minimum supported Python version to 3.11 in [`pyproject.toml`](pyproject.toml).
- Updated CI test matrix in [`.github/workflows/tests.yml`](.github/workflows/tests.yml) to run Python 3.11–3.12 only.
- Updated container conda Python baseline to 3.11 in [`scalable/Dockerfile`](scalable/Dockerfile).
- Expanded top-level exports in [`scalable/__init__.py`](scalable/__init__.py) to include
  ``ScalableSession``, ``DeploymentProvider``, ``LocalProvider``, and ``SlurmProvider``.
- Package version now targets v2 alpha in [`pyproject.toml`](pyproject.toml) with
  ``version = "2.0.0a1"``.
- Global settings in [`scalable/common.py`](scalable/common.py) now include
  ``manifest_path`` and ``target`` with env overrides ``SCALABLE_MANIFEST`` and
  ``SCALABLE_TARGET``.
- CI now includes:
  - version branch triggers (``version/**``)
  - macOS matrix coverage for LocalProvider paths
  - a dedicated docs-manifest validation and dry-run planning job

### Deprecated

- Legacy ``ModelConfig`` Dockerfile/config auto-discovery path now emits a
  ``DeprecationWarning`` when used outside the manifest adapter context;
  manifest-driven configuration via ``scalable.yaml`` is the preferred path.

### Documentation

- Added [`DISCLAIMER.md`](DISCLAIMER.md).
- Updated [`LICENSE.md`](LICENSE.md) to BSD-3-Clause wording.
- Added and cross-linked:
  - [`docs/manifest.rst`](docs/manifest.rst)
  - [`docs/providers.rst`](docs/providers.rst)
  - v2 manifest-first usage examples in [`README.md`](README.md)
  - onboarding links in [`docs/getting_started.rst`](docs/getting_started.rst)

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
[2.0.0a1]: https://github.com/JGCRI/scalable/compare/1.1.0...version/2.0.0-phase1-provider-manifest
[Unreleased]: https://github.com/JGCRI/scalable/compare/version/2.0.0-phase1-provider-manifest...HEAD
