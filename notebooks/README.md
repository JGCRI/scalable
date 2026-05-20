# Scalable Tutorial Notebooks

Interactive Jupyter notebooks for learning Scalable.

## 📚 Start Here: Beginner Tutorials

If you are **new to Scalable or distributed computing**, start with the beginner tutorials:

→ **[`beginner/`](beginner/)** — 10 notebooks that explain every concept from first principles. No prior distributed computing, cloud, or container experience required.

## 🚀 Advanced Tutorials

Once you're comfortable with the concepts, the advanced tutorials cover production patterns and deeper technical details:

→ **[`advanced/`](advanced/)** — 10 notebooks covering the same topics with less explanation and more advanced patterns for production use.

## Recommended Path

1. Work through `beginner/01` → `beginner/10` sequentially
2. Graduate to `advanced/01` → `advanced/10` for production patterns
3. Use the [RST documentation](../docs/tutorials/) for full architectural context

## Quick Start

```bash
# Install Scalable with all extras
pip install scalable[ai,cloud,kubernetes,ml]

# Install Jupyter
pip install jupyterlab

# Launch beginner tutorials
jupyter lab notebooks/beginner/

# Or advanced tutorials
jupyter lab notebooks/advanced/
```
