Getting Started with Scalable
=============================

This guide covers installation, baseline host requirements, and the bootstrap
flow used to prepare local and HPC environments.


Installation
------------

Install from PyPI using `pip <https://pip.pypa.io/en/stable/>`_.

.. code-block:: bash

    pip install scalable


For development or local source installs, clone the repository and install it
from the checkout.

.. code-block:: bash

    git clone https://github.com/JGCRI/scalable.git
    pip install ./scalable


Development Install (Editable Mode)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

For local development — where you want code changes to take effect immediately
without reinstalling — clone the repository and install in **editable mode**
(``-e``) inside a virtual environment.

.. code-block:: bash

    # Clone the repository
    git clone https://github.com/JGCRI/scalable.git
    cd scalable

    # Create and activate a virtual environment
    python -m venv .venv
    source .venv/bin/activate   # Linux / macOS
    # .venv\Scripts\activate    # Windows (cmd / PowerShell)

    # Install in editable mode with dev/test dependencies
    pip install -e ".[dev]"

The ``-e`` flag (short for ``--editable``) creates a link from the virtual
environment's ``site-packages`` back to your working tree so that any edits to
source files under ``scalable/`` are reflected immediately — no reinstall
required.

**Why use a virtual environment?**

A virtual environment isolates project dependencies from your system Python and
other projects.  This prevents version conflicts and makes dependency management
reproducible.  Always activate the environment before working on the project:

.. code-block:: bash

    source .venv/bin/activate   # each new terminal session

After installation, verify the setup:

.. code-block:: bash

    # Confirm the package is installed in editable mode
    pip show scalable          # Location should point to your clone
    python -c "import scalable; print(scalable.__version__)"

    # Run the test suite
    pytest

.. tip::

   If you only need to *run* Scalable (not develop it), a plain
   ``pip install ./scalable`` inside a virtual environment is sufficient and
   avoids installing test/lint tooling.

**Available extras for development:**

.. list-table::
   :header-rows: 1

   * - Extra
     - Contents
   * - ``dev``
     - Everything in ``test`` plus ``ruff``, ``mypy``, ``pytest-cov``
   * - ``test``
     - ``pytest``, ``pytest-asyncio``, ``hypothesis``, ``pydantic``
   * - ``ai``
     - AI assistant dependencies (``pydantic-ai``, ``jinja2``, ``rich``)
   * - ``ml``
     - ML optimization (``scikit-learn``, ``dask-ml``)
   * - ``cloud``
     - Cloud providers (``s3fs``, ``gcsfs``, ``dask-cloudprovider``)
   * - ``kubernetes``
     - Kubernetes provider (``dask-kubernetes``)

You can combine extras:

.. code-block:: bash

    pip install -e ".[dev,ai,ml]"


Optional Extras
~~~~~~~~~~~~~~~

Scalable provides optional dependency groups for extended features:

.. code-block:: bash

    # AI assistant features (init-component, diagnose, explain, compose, migrate)
    pip install scalable[ai]

    # Cloud providers (AWS, GCP) and remote artifact storage
    pip install scalable[cloud]

    # Kubernetes provider (Dask Kubernetes Operator)
    pip install scalable[kubernetes]

    # ML optimization and emulation (LearnedAdvisor, AdaptiveScaler, emulators)
    pip install scalable[ml]

    # All optional dependencies
    pip install scalable[ai,cloud,kubernetes,ml]


If installation reports that the scripts directory is not in ``PATH``, add the
reported directory to your shell profile.

.. code-block:: bash

    WARNING: The script scalable_bootstrap.exe is installed in '/path/to/python/scripts' which is not on PATH.
    Consider adding this directory to PATH or, if you prefer to suppress this warning, use --no-warn-script-location.

For example:

.. code-block:: bash

    echo "export PATH=\$PATH:/path/to/python/scripts" >> <shell_profile>
    source <shell_profile>

This only needs to be done once per environment.

Compatibility Requirements
--------------------------

Required and supported tooling:

* Local host: `Docker <https://www.docker.com/>`_ (optional for local provider)
* HPC scheduler: Slurm
* HPC container runtime: Apptainer
* Cloud: AWS (Fargate/EC2), GCP (scaffold)
* Orchestration: Kubernetes with Dask Operator

Bootstrapping is designed for POSIX-like shells. On Windows,
`Git Bash <https://git-scm.com/>`_ is recommended.

Work Directory Setup
--------------------

A dedicated work directory on the HPC host keeps dependencies, runtime assets,
and outputs in a consistent layout. The ``scalable_bootstrap`` script prepares
that directory and builds required worker containers.

Using key-based SSH authentication is strongly recommended because bootstrap may
open multiple remote sessions. A setup guide is available
`on this website
<https://www.digitalocean.com/community/tutorials/how-to-configure-ssh-key-based-authentication-on-a-linux-server>`_.

From a local working directory, run:

.. code-block:: bash

    cd <local_work_dir>
    scalable_bootstrap

Follow the interactive prompts. Bootstrap downloads and builds dependencies on
both local and HPC systems, then opens an SSH session into the configured HPC
work directory.

Inside the prepared environment, ``python3`` starts an interactive session with
Scalable dependencies available. You can also execute scripts directly.

Only files under the configured HPC work directory (and its subdirectories) are
available in this execution model.

.. code-block:: bash

    python3
    python3 <filename>.py

If bootstrap is interrupted, rerun ``scalable_bootstrap``. It resumes from the
last valid step and skips completed setup where possible.

Environment Configuration
-------------------------

Scalable uses a ``.env`` file in your working directory to centralize runtime
configuration — especially AI provider credentials, cache paths, and telemetry
settings.

How ``.env`` Loading Works
~~~~~~~~~~~~~~~~~~~~~~~~~~

Whenever the ``scalable`` package is imported (or any CLI command is run), the
:mod:`scalable.common` module automatically loads ``.env`` from the **current
working directory** using `python-dotenv <https://pypi.org/project/python-dotenv/>`_
with ``override=True``.  Values in ``.env`` therefore take precedence over
pre-existing system environment variables.

Setup Steps
~~~~~~~~~~~

1. **Copy the example file** from the repository root into your project
   directory:

   .. code-block:: bash

       cp .env.example .env

2. **Edit** ``.env`` and set the values you need.  At minimum, configure
   ``AI_PROVIDER`` and ``AI_API_KEY`` to enable AI features:

   .. code-block:: bash

       AI_PROVIDER=openai
       AI_API_KEY=sk-your-key-here
       LLM_MODEL_NAME=gpt-4o

3. **Run Scalable** from the directory containing ``.env``:

   .. code-block:: bash

       cd /path/to/your/project   # directory containing .env
       scalable validate ./scalable.yaml
       scalable compose "Run GCAM then Stitches"

   Or in Python:

   .. code-block:: python

       # .env is loaded automatically on import
       from scalable import ScalableSession

Where to Place the ``.env`` File
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

The file must be in the **current working directory** at the time Scalable is
first imported.  Common scenarios:

* **CLI usage** — the directory you ``cd`` into before running ``scalable``
  commands.
* **Python scripts** — the directory from which you run
  ``python your_script.py``.
* **Jupyter notebooks** — the notebook's working directory (check with
  ``os.getcwd()``).

If your working directory differs from where ``.env`` lives (for example, in
notebooks that ``os.chdir()`` into temporary directories), use the programmatic
helper *before* changing directories:

.. code-block:: python

    from scalable.common import load_env
    load_env("/absolute/path/to/your/.env")

Override Priority
~~~~~~~~~~~~~~~~~

Environment variable resolution follows this order (highest → lowest):

1. ``SCALABLE_AI_*`` variables (e.g., ``SCALABLE_AI_BACKEND``) —
   Scalable-specific overrides.
2. Generic ``AI_*`` / ``LLM_*`` variables (e.g., ``AI_PROVIDER``,
   ``LLM_MODEL_NAME``) — typically set in ``.env``.
3. Provider-specific keys (e.g., ``OPENAI_API_KEY``) — used as fallback for
   ``AI_API_KEY``.
4. Built-in defaults (e.g., ``AI_PROVIDER=none``,
   ``SCALABLE_CACHE_DIR=./cache``).

Security
~~~~~~~~

.. warning::

   Never commit ``.env`` to version control.  The repository ``.gitignore``
   already excludes it.  The bundled ``.env.example`` is safe to commit and
   serves as a configuration template.

Key Environment Variables
~~~~~~~~~~~~~~~~~~~~~~~~~

AI provider configuration (generic — recommended):

.. list-table::
   :header-rows: 1

   * - Variable
     - Default
     - Description
   * - ``AI_PROVIDER``
     - ``none``
     - Provider name (``openai``, ``anthropic``, ``google``, ``xai``, ``groq``, ``ollama``)
   * - ``AI_API_KEY``
     - *(unset)*
     - Universal API key (works for any provider)
   * - ``LLM_MODEL_NAME``
     - *(unset)*
     - Model name (e.g. ``gpt-4o``, ``claude-sonnet-4-20250514``, ``grok-3``)
   * - ``AI_BASE_URL``
     - *(unset)*
     - Custom API endpoint (for proxies; xAI auto-configures)

Core settings:

.. list-table::
   :header-rows: 1

   * - Variable
     - Default
     - Description
   * - ``SCALABLE_CACHE_DIR``
     - ``./cache``
     - Disk cache directory
   * - ``SCALABLE_SEED``
     - ``987654321``
     - xxhash seed for cache keys
   * - ``SCALABLE_LOG_LEVEL``
     - *(unset)*
     - Library log level (e.g. ``DEBUG``)
   * - ``SCALABLE_MANIFEST``
     - ``./scalable.yaml``
     - Default manifest path
   * - ``SCALABLE_TARGET``
     - *(unset)*
     - Default target override
   * - ``SCALABLE_RUNS_DIR``
     - ``./.scalable/runs``
     - Telemetry run directory
   * - ``SCALABLE_TELEMETRY``
     - ``1``
     - Enable/disable telemetry (``0`` or ``1``)

See ``.env.example`` in the repository root for the complete template with
inline documentation.

CLI Commands
------------

Scalable v2.0.0 provides a full CLI for manifest-driven workflows:

.. code-block:: bash

    scalable validate ./scalable.yaml
    scalable plan ./scalable.yaml --target local --dry-run
    scalable run ./scalable.yaml --target local --workflow workflow.py
    scalable report --latest
    scalable advise --task run_gcam --target local
    scalable init-component ./path/to/model --name gcam
    scalable diagnose --latest
    scalable explain plan.json
    scalable compose "Run GCAM then Stitches"
    scalable migrate scalable.yaml --to-provider kubernetes

Next Steps
----------

After setup:

* **New to distributed computing?** Start with the :ref:`beginner_tutorials`
  for a guided introduction that explains all concepts from first principles.
* For declarative workflows, start with :doc:`manifest` and :doc:`providers`.
* Use manifest overlays for environment-specific overrides: :doc:`overlays`.
* Review run telemetry in :doc:`telemetry`.
* Use deterministic history-based recommendations from :doc:`advising`.
* For ML-driven optimization, see :doc:`ml`.
* For model emulation, see :doc:`emulation`.
* For AI-assisted onboarding and diagnosis, see :doc:`ai_assistants`.
* For cloud and Kubernetes targets, see :doc:`cloud` and :doc:`kubernetes`.
* For artifact storage, see :doc:`artifacts`.
* Review the :ref:`api_section` for worker, caching, and function interfaces.
* Run examples from :ref:`demos_section`.
* Use :ref:`how_tos_section` for targeted implementation guidance.

Report issues at
`https://github.com/JGCRI/scalable/issues <https://github.com/JGCRI/scalable/issues>`_.
