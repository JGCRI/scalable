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
