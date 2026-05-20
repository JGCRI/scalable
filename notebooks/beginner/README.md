# Scalable Beginner Tutorial Notebooks

Interactive Jupyter notebooks designed for **non-experts** who are new to both Scalable and distributed computing. These notebooks accompany the [beginner documentation tutorials](../docs/tutorials/beginner/).

## How These Differ from Standard Notebooks

The advanced notebooks (in `../advanced/`) assume familiarity with distributed computing, YAML, containers, and cloud infrastructure. These beginner notebooks:

- 📖 **Define every term** before using it
- 🤔 **Explain why** approaches were chosen (not just how to use them)
- 💡 **Key Concept** cells introduce foundational ideas
- 📝 **Vocabulary summaries** at the end of each notebook
- 🔍 **Under the Hood** cells explain what Scalable does internally
- ✅ **Checkpoint** cells verify understanding before moving on

## Notebooks

| # | Notebook | Topic | Concepts Taught |
|---|----------|-------|-----------------|
| 1 | [Getting Started](01_getting_started.ipynb) | First workflow | Workflows, Dask, CLI, virtual environments |
| 2 | [Manifest System](02_manifest_system.ipynb) | Configuration | Declarative programming, YAML, schemas |
| 3 | [Scaling Strategies](03_scaling_strategies.ipynb) | Distribution | Clusters, schedulers, providers, parallelism |
| 4 | [Caching & Performance](04_caching_performance.ipynb) | Optimization | Hashing, memoization, decorators |
| 5 | [Cloud Integration](05_cloud_integration.ipynb) | Cloud | Object storage, containers, IAM, cost |
| 6 | [Telemetry](06_telemetry.ipynb) | Observability | Structured logging, JSONL, metrics |
| 7 | [Error Handling](07_error_handling.ipynb) | Resilience | Fault tolerance, retries, idempotency |
| 8 | [Kubernetes](08_kubernetes.ipynb) | Orchestration | Pods, operators, namespaces |
| 9 | [ML & Emulation](09_ml_emulation.ipynb) | Intelligence | Surrogate models, uncertainty, active learning |
| 10 | [AI Composition](10_ai_composition.ipynb) | AI Assistants | LLMs, heuristics, code generation |

## Quick Start

```bash
# Install Scalable with all extras
pip install scalable[ai,cloud,kubernetes,ml]

# Install Jupyter
pip install jupyterlab

# Launch
jupyter lab notebooks/beginner/
```

## Running Order

Notebooks are designed to be run sequentially (1 → 10). Each is self-contained with its own setup and teardown, but concepts build progressively. If you skip ahead, you may encounter terms that were defined in earlier notebooks.

## Prerequisites

- Python 3.11+
- Basic Python knowledge (functions, imports, loops)
- NO distributed computing experience required
- NO cloud/container/Kubernetes experience required

## Conventions

- Each notebook creates a temporary working directory and cleans up after itself
- Extensive markdown cells explain concepts BEFORE code cells
- `# Explanation:` comments in code cells describe what each line does
- "🤔 Think About It" cells prompt reflection on key concepts
- "📖 Vocabulary" cells summarize new terms learned
- Functions that simulate expensive computations use `time.sleep()` with short durations

## Graduating to Standard Notebooks

After completing these beginner notebooks, move to the [advanced notebooks](../advanced/) for deeper technical content and production patterns. Each beginner notebook maps 1:1 to a standard notebook covering the same topic at a more advanced level.
