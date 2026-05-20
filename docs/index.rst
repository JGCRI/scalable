.. Scalable documentation master file, created by
   sphinx-quickstart on Thu Aug 22 10:55:42 2024.
   You can adapt this file completely to your liking, but it should at least
   contain the root `toctree` directive.

Scalable Documentation
======================

Scalable is a Python framework for orchestrating multi-step workflows on HPC
systems, Kubernetes clusters, and cloud providers with minimal manual overhead.
It combines Dask-based task execution, scheduler-aware worker provisioning,
optional containerized runtimes, AI assistants, and ML-driven optimization so
workloads can run reproducibly across heterogeneous environments.

The diagram below shows the high-level architecture.

.. image:: images/scalable_architecture.png
   :align: center

Scalable is a strong fit when your project needs one or more of the following:

* Long-running or resource-intensive workflows on shared HPC infrastructure.
* Pipeline-style execution where outputs from one stage feed downstream stages.
* Automatic or programmatic scaling of workers and hardware allocations.
* Portable execution across local, HPC, Kubernetes, and cloud targets.
* AI-assisted model onboarding, failure diagnosis, and workflow composition.
* ML-optimized resource prediction and adaptive scaling from run history.

Scalable supports running functions in distinct software environments via
container images. A multi-stage Dockerfile can define multiple worker profiles,
each with different dependencies, models, or tools, and worker counts can be
managed per profile when scaling out a cluster.

Contents
--------

.. toctree::
   :caption: Getting Started
   :maxdepth: 1

   getting_started
   license
   how_to_contribute

.. _tutorials_section:

.. toctree::
   :caption: Tutorials
   :maxdepth: 2

   tutorials/index

.. _api_section:

.. toctree::
   :caption: API
   :maxdepth: 1

   workers
   manifest
   overlays
   providers
   cloud
   kubernetes
   artifacts
   cost
   telemetry
   advising
   ml
   emulation
   ai_assistants
   caching
   functions

