<p align="center">
    <img src="docs/images/scalable_logo_nobkg.png" alt="Scalable logo" width="320" />
</p>

# Scalable

[![PyPI](https://img.shields.io/pypi/v/scalable.svg)](https://pypi.org/project/scalable/)
[![Python](https://img.shields.io/badge/python-3.11%20%7C%203.12%20%7C%203.13-blue.svg)](https://pypi.org/project/scalable/)
[![Docs](https://readthedocs.org/projects/scalable/badge/?version=latest)](https://jgcri.github.io/scalable/)

Scalable is a Python framework for orchestrating containerized, distributed workflows on HPC systems, Kubernetes clusters, and cloud providers. It integrates container lifecycle management, scheduler-aware resource provisioning, a Dask-based execution model, optional AI assistants, and ML-driven optimization so multi-stage scientific workflows can run consistently at scale.

## Table of Contents

- [Documentation](#documentation)
- [Installation](#installation)
- [System Requirements](#system-requirements)
- [Quick Start](#quick-start)
- [Configuration (`.env` File)](#configuration-env-file)
- [Usage](#usage)
  - [Manifest-Driven Workflows](#manifest-driven-workflows)
  - [Session API](#session-api)
  - [Telemetry and Reports](#telemetry-and-reports)
  - [Resource Advising](#resource-advising)
  - [ML Optimization](#ml-optimization)
  - [Model Emulation](#model-emulation)
  - [AI Assistants](#ai-assistants)
  - [Cloud and Kubernetes](#cloud-and-kubernetes)
  - [Artifact Storage](#artifact-storage)
  - [Imperative API](#imperative-api)
- [Function Caching](#function-caching)
- [How to Contribute](#how-to-contribute)
- [License](#license)

## Documentation

Full documentation is available at [jgcri.github.io/scalable](https://jgcri.github.io/scalable/).

### Tutorials

Scalable includes two sets of tutorials:

- **[Beginner Tutorials](notebooks/beginner/)** — Start here if you are new to Scalable or unfamiliar with distributed computing, containers, cloud infrastructure, or declarative programming. These tutorials explain every concept from first principles with analogies and definitions.
- **[Advanced Tutorials](notebooks/advanced/)** — Production-focused tutorials for users already comfortable with distributed systems concepts.

Both are available as [interactive Jupyter notebooks](notebooks/) and as [comprehensive RST documentation](docs/tutorials/).

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

### Optional extras

Scalable provides optional dependency groups for extended features:

```bash
# AI assistant features (init-component, diagnose, explain, compose, migrate)
pip install scalable[ai]

# Cloud providers (AWS, GCP)
pip install scalable[cloud]

# Kubernetes provider (Dask Kubernetes Operator)
pip install scalable[kubernetes]

# ML optimization and emulation (LearnedAdvisor, AdaptiveScaler, emulators)
pip install scalable[ml]

# All optional dependencies
pip install scalable[ai,cloud,kubernetes,ml]
```

If your shell cannot find installed scripts (for example, `scalable_bootstrap`), add the relevant scripts directory to `PATH`.

## System Requirements

- **Scheduler:** Slurm (HPC), Kubernetes, AWS Fargate/EC2, or local execution
- **Local host tools:** Docker (optional for local provider)
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

## Configuration (`.env` File)

Scalable uses a **`.env` file** in your project's working directory to centralize
runtime configuration — particularly AI provider credentials, cache paths, and
telemetry settings.

### How It Works

When any part of the Scalable library is imported (or any CLI command is run),
the module [`scalable.common`](scalable/common.py:39) automatically loads a
`.env` file from **the current working directory** (`$CWD/.env`) using
[python-dotenv](https://pypi.org/project/python-dotenv/) with `override=True`.
This means values in `.env` take precedence over pre-existing system environment
variables.

### Setup Steps

1. **Copy the example file** from the repository root into your project directory:

   ```bash
   cp .env.example .env
   ```

2. **Edit `.env`** and fill in your values (at minimum, set `AI_PROVIDER` and
   `AI_API_KEY` if you want AI features):

   ```bash
   AI_PROVIDER=openai
   AI_API_KEY=sk-your-key-here
   LLM_MODEL_NAME=gpt-4o
   ```

3. **Run Scalable** from the directory containing `.env`:

   ```bash
   cd /path/to/your/project   # directory with .env
   scalable validate ./scalable.yaml
   scalable compose "Run GCAM then Stitches"
   ```

   Or in Python:

   ```python
   # The .env is loaded automatically on import
   from scalable import ScalableSession
   ```

### Where to Place the `.env` File

| Scenario | Location |
|----------|----------|
| CLI usage | The directory you `cd` into before running `scalable` commands |
| Python scripts | The directory from which you launch `python your_script.py` |
| Jupyter notebooks | The notebook's working directory (check with `os.getcwd()`) |

> **Tip:** If your working directory differs from where `.env` lives (e.g., in
> notebooks that `os.chdir()` into temp directories), use the programmatic
> helper:
>
> ```python
> from scalable.common import load_env
> load_env("/absolute/path/to/your/.env")
> ```

### Override Priority

Environment variable resolution follows this priority (highest → lowest):

1. `SCALABLE_AI_*` variables (e.g., `SCALABLE_AI_BACKEND`) — Scalable-specific overrides
2. Generic `AI_*` / `LLM_*` variables (e.g., `AI_PROVIDER`, `LLM_MODEL_NAME`) — from `.env`
3. Provider-specific keys (e.g., `OPENAI_API_KEY`) — used as fallback for `AI_API_KEY`
4. Built-in defaults (e.g., `AI_PROVIDER=none`, `SCALABLE_CACHE_DIR=./cache`)

### Security

> ⚠️ **Never commit `.env` to version control.** The repository `.gitignore`
> already excludes `.env`. The included `.env.example` is safe to commit and
> serves as a template.

See the full [Environment Variables](#environment-variables) reference below for
all supported settings.

## Usage

### Manifest-Driven Workflows

Scalable v2.0.0 introduces a declarative manifest (`scalable.yaml`) as the single source of truth for targets, components, and task bindings.

Create `scalable.yaml`:

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

Run a workflow (with optional dry-run for cost estimation):

```bash
scalable run ./scalable.yaml --target local --workflow workflow.py
scalable run ./scalable.yaml --target aws --dry-run
```

### Session API

Use the Python session API for programmatic control:

```python
from scalable import ScalableSession

session = ScalableSession.from_yaml("./scalable.yaml", target="local")
plan = session.plan(dry_run=True)
print(plan.manifest_lock)

# With planning objectives and policies
plan = session.plan(
    objective="minimize cost",   # "minimize cost", "minimize time", "balance"
    policy="safe",               # "safe", "aggressive", "manual"
)
```

### Telemetry and Reports

Every manifest-driven run records structured telemetry under `.scalable/runs/`:

```bash
scalable report --latest
scalable report --latest --format json --output report.json
```

### Resource Advising

Use deterministic history-based advising:

```python
from scalable import ResourceAdvisor

advisor = ResourceAdvisor.from_history("./.scalable/runs")
recommendation = advisor.recommend(
    task="run_gcam",
    target="local",
    confidence=0.95,
)
print(recommendation.workers)
print(recommendation.resources)
```

Or use the CLI:

```bash
scalable advise --task run_gcam --target local --confidence 0.95
```

### ML Optimization

When `scalable[ml]` is installed, ML-backed resource prediction and adaptive
scaling become available:

```python
from scalable import LearnedAdvisor, AdaptiveScaler

# ML-backed resource recommendations trained on telemetry history
advisor = LearnedAdvisor.from_history(
    "./.scalable/runs",
    model_type="gradient_boosting",
)
recommendation = advisor.recommend(task="run_gcam", target="local")
print(recommendation.resources)

# Adaptive real-time worker scaling
scaler = AdaptiveScaler(
    min_workers=1,
    max_workers=16,
    scale_up_threshold=0.8,
    scale_down_threshold=0.3,
    cooldown_seconds=60,
)
decision = scaler.evaluate(current_metrics)
```

CLI access:

```bash
scalable advise --task run_gcam --model-type gradient_boosting --format json
```

### Model Emulation

The emulation subsystem (`scalable[ml]`) provides uncertainty-aware surrogate
model dispatch for expensive scientific functions:

```python
from scalable import emulatable, EmulatorRegistry, EmulatorDispatch

@emulatable(
    inputs=["temperature", "precipitation"],
    outputs=["yield"],
    domain_bounds={"temperature": (250, 350), "precipitation": (0, 5000)},
    confidence_threshold=0.9,
)
def run_crop_model(temperature, precipitation):
    # Expensive model execution
    ...

# Register and manage trained emulators
registry = EmulatorRegistry(".scalable/emulators")
dispatch = EmulatorDispatch(registry, confidence_threshold=0.9)

# Confidence-gated routing: uses emulator when confident, falls back to full model
result = dispatch.predict("run_crop_model", inputs={"temperature": 300, "precipitation": 1200})
print(result.source)       # "emulator" or "full_model"
print(result.confidence)
```

### AI Assistants

AI assistants help with onboarding, diagnostics, workflow generation, and
migration. All features work without an LLM backend via deterministic heuristics;
LLM enhancement is opt-in via `AI_PROVIDER` (or `SCALABLE_AI_BACKEND`).

Supported AI providers:

| Provider | `AI_PROVIDER` | Example Models |
|----------|---------------|----------------|
| OpenAI | `openai` | gpt-4o, gpt-4o-mini, o1 |
| Anthropic | `anthropic` | claude-opus-4-20250514, claude-sonnet-4-20250514 |
| Google Gemini | `google` | gemini-2.0-flash, gemini-1.5-pro |
| xAI (Grok) | `xai` | grok-3, grok-2 |
| Groq | `groq` | llama-3.1-70b-versatile |
| Ollama (local) | `ollama` | llama3, mistral |

Configure via `.env` file (loaded automatically with override priority):

```bash
AI_PROVIDER=openai
AI_API_KEY=your_api_key_here
LLM_MODEL_NAME=gpt-4o
# AI_BASE_URL=https://custom-endpoint.example.com/v1  # optional
```

```bash
# Onboard a new model component
scalable init-component ./path/to/model --name gcam --no-ai

# Diagnose failures from recent runs
scalable diagnose --latest --no-ai

# Explain an execution plan in human-readable form
scalable explain plan.json

# Generate a workflow from natural language
scalable compose "Run GCAM reference scenario then Stitches for daily climate"

# Propose manifest migration to a new provider
scalable migrate scalable.yaml --to-provider kubernetes
```

Python API:

```python
from scalable.ai import onboard_component, diagnose_run, explain_plan

result = onboard_component("./gcam-core", name="gcam", no_ai=True)
print(result.component_yaml)
```

### Cloud and Kubernetes

Scalable supports multi-provider execution through optional extras:

```bash
# AWS (Fargate/EC2)
pip install scalable[cloud]
scalable run scalable.yaml --target aws --dry-run

# Kubernetes (Dask Kubernetes Operator)
pip install scalable[kubernetes]
scalable run scalable.yaml --target gke --dry-run
```

Cost estimation is included for cloud providers:

```python
from scalable import CostEstimate
# Cost estimates are included in dry-run plan output and telemetry
```

### Artifact Storage

The artifact store provides protocol-based storage across local and remote
backends:

```python
from scalable.artifacts import build_artifact_store

# Local storage
store = build_artifact_store("./artifacts")
ref = store.put("output.csv", "runs/run-001/output.csv")

# S3 storage (requires scalable[cloud])
store = build_artifact_store("s3://my-bucket/artifacts/")
```

### Imperative API

The legacy imperative API remains fully supported for existing workflows:

#### 1. Create a cluster

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

#### 2. Register container targets

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
```

#### 3. Scale workers

```python
cluster.add_workers(n=3, tag="gcam")
cluster.add_workers(n=2, tag="stitches")
```

#### 4. Submit functions

```python
def func1(param):
    import gcam
    return gcam.__version__


def func2(param):
    import stitches
    return stitches.__version__


client = ScalableClient(cluster)

fut1 = client.submit(func1, "gcam", tag="gcam")
fut2 = client.submit(func2, "stitches", tag="stitches")
```

#### 5. Scale down when complete

```python
cluster.remove_workers(n=2, tag="gcam")
cluster.remove_workers(n=1, tag="stitches")
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

For reliable behavior, explicitly specify argument and return types whenever possible. Cache hit/miss events are emitted to telemetry when telemetry is active.

## Environment Variables

Scalable is configured via environment variables for deployment flexibility.
A `.env` file in the project root is loaded automatically with override priority
(values in `.env` take precedence over system environment variables).

### AI Provider Configuration (Generic)

These provider-agnostic variables are the recommended way to configure AI features:

| Variable | Default | Description |
|----------|---------|-------------|
| `AI_PROVIDER` | `none` | AI provider (`openai`, `anthropic`, `google`, `xai`, `groq`, `ollama`) |
| `AI_API_KEY` | *(unset)* | Universal API key (works for any provider) |
| `LLM_MODEL_NAME` | *(unset)* | Model name (e.g. `gpt-4o`, `claude-sonnet-4-20250514`, `grok-3`) |
| `AI_BASE_URL` | *(unset)* | Custom API endpoint (for proxies, xAI auto-configures) |

### Provider-Specific API Keys (Optional)

Override `AI_API_KEY` for individual providers when using multiple services:

| Variable | Provider |
|----------|----------|
| `OPENAI_API_KEY` | OpenAI |
| `ANTHROPIC_API_KEY` | Anthropic |
| `GOOGLE_API_KEY` | Google Gemini |
| `XAI_API_KEY` | xAI (Grok) |
| `GROQ_API_KEY` | Groq |

### Core Configuration

| Variable | Default | Description |
|----------|---------|-------------|
| `SCALABLE_CACHE_DIR` | `./cache` | Disk cache directory |
| `SCALABLE_SEED` | `987654321` | xxhash seed for cache keys |
| `SCALABLE_LOG_LEVEL` | *(unset)* | Library log level (e.g. `DEBUG`) |
| `SCALABLE_MANIFEST` | `./scalable.yaml` | Default manifest path |
| `SCALABLE_TARGET` | *(unset)* | Default target override |
| `SCALABLE_RUNS_DIR` | `./.scalable/runs` | Telemetry run directory |
| `SCALABLE_TELEMETRY` | `1` | Enable/disable telemetry |
| `SCALABLE_TELEMETRY_PARQUET` | `0` | Emit parquet snapshots |
| `SCALABLE_CACHE_REMOTE` | *(unset)* | Remote cache URI (S3/GCS) |
| `SCALABLE_DEFAULT_STORAGE` | *(unset)* | Default artifact storage URI |
| `SCALABLE_ML` | `1` | Enable ML features |
| `SCALABLE_ML_CACHE_DIR` | `.scalable/models` | ML model cache directory |
| `SCALABLE_EMULATION` | `0` | Enable model emulation |
| `SCALABLE_EMULATOR_DIR` | `.scalable/emulators` | Emulator registry directory |
| `SCALABLE_EMULATION_CONFIDENCE` | `0.9` | Emulation confidence threshold |

### Advanced AI Overrides

These `SCALABLE_AI_*` variables take priority over the generic `AI_*` equivalents.
Use only when you need Scalable-specific config separate from other tools:

| Variable | Default | Description |
|----------|---------|-------------|
| `SCALABLE_AI_BACKEND` | *(from AI_PROVIDER)* | AI backend override |
| `SCALABLE_AI_MODEL` | *(from LLM_MODEL_NAME)* | Model name override |
| `SCALABLE_AI_ENDPOINT` | *(from AI_BASE_URL)* | API endpoint override |
| `SCALABLE_AI_API_KEY` | *(from AI_API_KEY)* | API key override |

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
