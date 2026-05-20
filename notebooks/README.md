# Scalable Tutorial Notebooks

Interactive Jupyter notebooks accompanying the [documentation tutorials](../docs/tutorials/).

## Notebooks

| # | Notebook | Topic | Install Extra |
|---|----------|-------|---------------|
| 1 | [Getting Started](01_getting_started.ipynb) | Install, manifest, validate, run | `pip install scalable` |
| 2 | [Manifest System](02_manifest_system.ipynb) | Schema, targets, overlays, validation | `pip install scalable` |
| 3 | [Scaling Strategies](03_scaling_strategies.ipynb) | Providers, pools, adaptive scaling | `pip install scalable` |
| 4 | [Caching & Performance](04_caching_performance.ipynb) | @cacheable, FileType, invalidation | `pip install scalable` |
| 5 | [Cloud Integration](05_cloud_integration.ipynb) | AWS, GCP, artifact store, cost estimation | `pip install scalable[cloud]` |
| 6 | [Telemetry](06_telemetry.ipynb) | JSONL events, reports, trend analysis | `pip install scalable` |
| 7 | [Error Handling](07_error_handling.ipynb) | Retry, partial success, fault tolerance | `pip install scalable` |
| 8 | [Kubernetes](08_kubernetes.ipynb) | Dask Operator, namespaces, CI/CD | `pip install scalable[kubernetes]` |
| 9 | [ML & Emulation](09_ml_emulation.ipynb) | LearnedAdvisor, @emulatable, dispatch | `pip install scalable[ml]` |
| 10 | [AI Composition](10_ai_composition.ipynb) | onboard, diagnose, compose, migrate | `pip install scalable[ai]` |

## Quick Start

```bash
# Install Scalable with all extras
pip install scalable[ai,cloud,kubernetes,ml]

# Install Jupyter
pip install jupyterlab

# Launch
jupyter lab notebooks/
```

## Running Order

Notebooks are designed to be run sequentially (1 → 10) but each is self-contained with its own setup and teardown. Notebooks 1–4 and 6–7 require only the base `scalable` package; others need optional extras as noted above.

## Conventions

- Each notebook creates a temporary working directory and cleans up after itself.
- Functions that simulate expensive computations use `time.sleep()` with short durations (0.1–1.0s) for notebook responsiveness.
- Cloud and Kubernetes notebooks (5, 8) demonstrate configuration and concepts but require real infrastructure for full execution.
- All notebooks use `no_ai=True` (heuristic mode) for the AI features to avoid external API dependencies.

## Relationship to RST Tutorials

These notebooks are interactive companions to the comprehensive RST tutorials in [`docs/tutorials/`](../docs/tutorials/). The RST versions contain deeper architectural context, trade-off discussions, and production deployment guidance. The notebooks focus on hands-on code execution.
