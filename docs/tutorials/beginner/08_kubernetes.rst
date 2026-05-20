.. _beginner_kubernetes:

======================================================
Beginner Tutorial 8: Container Orchestration with Kubernetes
======================================================

The Big Picture
----------------

In Tutorial 5, you learned about containers — packaged software environments
that run anywhere. But what happens when you need to run 50 containers across
multiple machines? Who decides which machine runs which container? What happens
when a container crashes? What about scaling up and down?

**Kubernetes** (often abbreviated "K8s") is the answer. It's a platform for
managing containers at scale — automatically placing them on machines, restarting
them when they fail, and scaling them up or down based on demand.

This tutorial explains Kubernetes from first principles and shows how Scalable
uses it to run distributed workflows on container infrastructure.

What You Will Learn
--------------------

By the end of this tutorial you will:

* Understand what Kubernetes is and what problem it solves.
* Know the key K8s concepts: pods, nodes, namespaces, operators.
* Understand how the Dask Kubernetes Operator works.
* Configure Scalable's Kubernetes provider.
* Understand resource requests, limits, and quotas.
* Know when Kubernetes is appropriate vs. overkill.

Prerequisites
--------------

* Completed :ref:`beginner_getting_started`, :ref:`beginner_manifest_system`,
  and :ref:`beginner_scaling_strategies`.
* Conceptual understanding of containers from :ref:`beginner_cloud_integration`.
* No Kubernetes cluster required to understand the concepts — code examples
  show configuration patterns.


Key Concepts Explained
-----------------------

.. admonition:: 💡 Key Concept: What is Container Orchestration?
   :class: tip

   You know what a container is (packaged software). **Container
   orchestration** is the automation of deploying, managing, and scaling
   containers across multiple machines.

   **Without orchestration:**

   * Manually decide which server runs which container
   * Manually restart containers that crash
   * Manually add/remove containers when load changes
   * Manually route traffic to healthy containers

   **With orchestration (Kubernetes):**

   * You declare: "I want 10 copies of this container"
   * K8s decides where to put them (across available machines)
   * K8s automatically restarts crashed containers
   * K8s auto-scales based on demand
   * K8s routes traffic to healthy instances

   **Analogy:** Container orchestration is like an air traffic controller
   for containers. You don't tell each plane exactly which runway and gate
   to use — the controller optimally assigns resources based on the current
   situation.

.. admonition:: 💡 Key Concept: What is Kubernetes?
   :class: tip

   **Kubernetes** (from Greek: κυβερνήτης, "helmsman") is an open-source
   container orchestration platform originally developed by Google.

   It manages:

   * **Where** containers run (scheduling across machines)
   * **How many** containers run (scaling)
   * **Healthy** containers stay running (self-healing)
   * **Network** connectivity between containers (service discovery)
   * **Storage** for containers (persistent volumes)

   Kubernetes is the industry standard — it runs in AWS (EKS), Google Cloud
   (GKE), Azure (AKS), and on-premise. Scalable uses it as one of its
   deployment providers.

.. admonition:: 💡 Key Concept: Pods
   :class: tip

   A **pod** is the smallest deployable unit in Kubernetes — a group of one
   or more containers that share network and storage.

   Most commonly, a pod = one container. But sometimes related containers
   are grouped (e.g., your app container + a logging sidecar).

   .. code-block:: text

      ┌─── Pod ─────────────────────┐
      │                             │
      │  ┌───────────────────────┐  │
      │  │  Container            │  │
      │  │  (your Dask worker)   │  │
      │  └───────────────────────┘  │
      │                             │
      │  Shared: IP address,        │
      │  storage volumes            │
      └─────────────────────────────┘

   In Scalable's context: each Dask worker runs in its own pod.

.. admonition:: 💡 Key Concept: Nodes
   :class: tip

   A **node** is a physical or virtual machine in the Kubernetes cluster.
   Pods are scheduled onto nodes.

   .. code-block:: text

      Kubernetes Cluster
      ├── Node 1 (machine with 16 CPUs, 64GB RAM)
      │   ├── Pod A (your worker, 4 CPU, 16GB)
      │   ├── Pod B (your worker, 4 CPU, 16GB)
      │   └── Pod C (system pod)
      ├── Node 2 (machine with 16 CPUs, 64GB RAM)
      │   ├── Pod D (your worker, 4 CPU, 16GB)
      │   └── Pod E (your worker, 4 CPU, 16GB)
      └── Node 3 (machine with 8 CPUs, 32GB RAM)
          └── Pod F (scheduler pod)

   The Kubernetes scheduler decides which node each pod runs on, based on
   available resources and constraints.

.. admonition:: 💡 Key Concept: Namespaces
   :class: tip

   A **namespace** is an isolation boundary within a Kubernetes cluster.
   Different teams or projects use different namespaces to avoid conflicts.

   Think of namespaces like departments in a building:

   * ``team-energy`` namespace — your team's pods
   * ``team-hydrology`` namespace — another team's pods
   * ``system`` namespace — cluster infrastructure

   Resources in one namespace can't accidentally interfere with another.
   Resource quotas can limit how much CPU/memory each namespace uses.

.. admonition:: 💡 Key Concept: Operators (Kubernetes Extension)
   :class: tip

   A **Kubernetes Operator** is a program that extends Kubernetes to manage
   complex applications automatically. It encodes domain-specific knowledge
   about how to deploy, scale, and maintain an application.

   **The Dask Kubernetes Operator:**

   * Knows how to create Dask clusters (scheduler + workers)
   * Manages worker scaling automatically
   * Handles upgrades and restarts
   * Integrates with Kubernetes native features (quotas, monitoring)

   Without an operator, you'd need to manually create pods for the scheduler,
   pods for each worker, configure networking between them, and handle
   failures. The operator does all this for you.

.. admonition:: 💡 Key Concept: kubectl
   :class: tip

   **kubectl** (pronounced "cube-control" or "cube-C-T-L") is the
   command-line tool for interacting with Kubernetes clusters.

   .. code-block:: bash

      # List running pods in your namespace
      kubectl get pods -n team-energy

      # See details about a specific pod
      kubectl describe pod worker-abc123

      # View pod logs (stdout/stderr)
      kubectl logs worker-abc123

      # Delete a pod (Kubernetes will restart it if managed)
      kubectl delete pod worker-abc123

   Think of kubectl as the Kubernetes equivalent of ``docker`` commands,
   but for a whole cluster instead of a single machine.

.. admonition:: 💡 Key Concept: Resource Requests vs. Limits
   :class: tip

   In Kubernetes, each pod declares:

   **Requests** — minimum guaranteed resources:
     "I need at least 2 CPUs and 4GB RAM to function"

   **Limits** — maximum allowed resources:
     "Never let me use more than 4 CPUs or 8GB RAM"

   .. code-block:: yaml

      resources:
        requests:
          cpu: "2"
          memory: "4Gi"
        limits:
          cpu: "4"
          memory: "8Gi"

   **Why both?** Requests are used for scheduling (Kubernetes finds a node
   with enough free capacity). Limits prevent runaway containers from
   consuming all resources on a node and affecting other pods.

.. admonition:: 💡 Key Concept: Helm Charts
   :class: tip

   **Helm** is a package manager for Kubernetes (like ``pip`` for Python or
   ``apt`` for Linux). A **Helm chart** is a package of Kubernetes
   configuration files.

   Instead of writing dozens of YAML files to deploy an application, you
   install a chart:

   .. code-block:: bash

      helm install dask-operator dask/dask-kubernetes-operator

   Charts can be versioned, shared, and configured with values files.


Step 1: Kubernetes Architecture for Scalable
----------------------------------------------

When you use Scalable's Kubernetes provider, this is what gets created:

.. code-block:: text

   Kubernetes Cluster
   └── Your Namespace (team-energy)
       ├── Dask Scheduler Pod (1x)
       │   └── Container: dask-scheduler
       │       Port 8786 (client connections)
       │       Port 8787 (dashboard)
       ├── Dask Worker Pods (N×)
       │   └── Container: your-image
       │       Runs your Python code
       │       Connected to scheduler
       └── Client (your script, outside cluster)
           └── Connects to scheduler via port-forward or ingress

The Dask Kubernetes Operator manages all of this based on a ``DaskCluster``
custom resource that Scalable creates from your manifest.


Step 2: Configuring the Kubernetes Provider
---------------------------------------------

.. code-block:: yaml

   # scalable.yaml
   targets:
     k8s:
       provider: kubernetes
       namespace: team-energy
       image: ghcr.io/my-org/energy-model:latest
       adaptive:
         minimum: 2
         maximum: 20
       resources:
         requests:
           cpu: "4"
           memory: "16Gi"
         limits:
           cpu: "4"
           memory: "16Gi"

**What each setting does:**

``namespace: team-energy``
   Deploy into this Kubernetes namespace. Must exist and you must have
   permissions to create pods there.

``image: ghcr.io/my-org/energy-model:latest``
   Container image for worker pods. Must contain your code, Python, and all
   dependencies (including Scalable itself).

``adaptive: {minimum: 2, maximum: 20}``
   Start with 2 worker pods, scale up to 20 based on queue depth.

``resources``
   CPU and memory for each worker pod. Maps directly to Kubernetes resource
   specifications.


Step 3: The Deployment Lifecycle
----------------------------------

.. code-block:: text

   1. You run: scalable run ./scalable.yaml --target k8s
   2. Scalable creates a DaskCluster custom resource in your namespace
   3. The Dask Operator sees the resource and creates:
      - 1 scheduler pod
      - N worker pods (starting at adaptive.minimum)
   4. Your client connects to the scheduler
   5. Tasks are submitted and executed on worker pods
   6. Adaptive scaling adds/removes worker pods based on load
   7. When complete, the DaskCluster is deleted
   8. All pods are cleaned up

.. admonition:: Under the Hood: Custom Resources
   :class: hint

   Kubernetes has built-in resource types (Pod, Service, Deployment). But
   you can also define **Custom Resource Definitions (CRDs)** — new types
   that Kubernetes doesn't know about natively.

   The Dask Operator defines a ``DaskCluster`` CRD. When you create a
   ``DaskCluster`` resource, the operator watches for it and creates the
   necessary pods, services, and configurations automatically.

   This is the declarative pattern again: you declare "I want a DaskCluster
   with these specs" and the operator makes it happen.


Step 4: When to Use Kubernetes
--------------------------------

.. list-table::
   :header-rows: 1
   :widths: 50 50

   * - ✅ Good fit for Kubernetes
     - ❌ Overkill / Wrong tool
   * - Team sharing a cluster for multiple projects
     - Single user on a laptop
   * - Need for resource isolation between teams
     - Simple batch job on one machine
   * - Auto-scaling based on demand
     - Fixed workload with known size
   * - Long-running services + batch jobs
     - One-off analysis
   * - Already have K8s infrastructure
     - Don't have K8s (use cloud Fargate instead)
   * - Need reproducible deployment
     - Rapid development iteration

.. admonition:: 🤔 Think About It
   :class: note

   Kubernetes adds complexity. You need to:

   * Maintain a cluster (or pay for a managed one)
   * Build and push container images
   * Configure namespaces, quotas, and RBAC
   * Learn kubectl and K8s concepts

   For many scientific workflows, the local provider (development) + cloud
   Fargate (production) is simpler than Kubernetes. K8s shines when you
   have a shared cluster already or need fine-grained resource management.


Step 5: Working with Container Images
-----------------------------------------

Your code runs inside containers in K8s. The image must contain everything:

.. code-block:: dockerfile

   # Dockerfile
   FROM python:3.12-slim

   # Install system dependencies
   RUN apt-get update && apt-get install -y --no-install-recommends \
       gcc && rm -rf /var/lib/apt/lists/*

   # Install Python packages
   COPY requirements.txt .
   RUN pip install --no-cache-dir -r requirements.txt

   # Copy your workflow code
   COPY . /app
   WORKDIR /app

   # Default command (overridden by Dask worker command)
   CMD ["python", "-m", "distributed.cli.dask_worker"]

Build and push:

.. code-block:: bash

   # Build the image
   docker build -t ghcr.io/my-org/energy-model:latest .

   # Push to registry (GitHub Container Registry in this example)
   docker push ghcr.io/my-org/energy-model:latest

.. admonition:: 💡 Key Concept: Image Pull Policy
   :class: tip

   When Kubernetes creates a pod, it needs to download (pull) the container
   image from the registry. Pull policies control when:

   * ``Always`` — always pull the latest (good for development)
   * ``IfNotPresent`` — use cached version if available (faster)
   * ``Never`` — never pull (image must be pre-loaded)

   For production, use specific image tags (``v1.2.3``) rather than
   ``latest`` to ensure reproducibility.


Step 6: Monitoring Kubernetes Deployments
-------------------------------------------

.. code-block:: bash

   # Watch pods come up
   kubectl get pods -n team-energy -w

   # Output:
   # NAME                          READY   STATUS    RESTARTS   AGE
   # dask-scheduler-abc123         1/1     Running   0          30s
   # dask-worker-def456            1/1     Running   0          25s
   # dask-worker-ghi789            1/1     Running   0          25s

   # Check resource usage
   kubectl top pods -n team-energy

   # View worker logs
   kubectl logs dask-worker-def456 -n team-energy

   # Access Dask dashboard (port-forward to localhost)
   kubectl port-forward svc/dask-scheduler 8787:8787 -n team-energy
   # Then open http://localhost:8787 in your browser


Common Questions
-----------------

**Q: Do I need to be a Kubernetes expert to use Scalable with K8s?**

No. Scalable abstracts most K8s complexity. You need to know:

* Your namespace name
* Your container image URI
* Basic kubectl commands for debugging

The Dask Operator handles pod creation, scaling, and cleanup.

**Q: What's the difference between Kubernetes and Docker?**

* **Docker** = creates and runs individual containers on one machine
* **Kubernetes** = manages many containers across many machines

Docker builds the containers; Kubernetes orchestrates them.

**Q: How does auto-scaling work in Kubernetes?**

The Dask Operator watches queue depth (pending tasks). When tasks queue up,
it creates more worker pods. When workers are idle, it removes them. This
maps to the ``adaptive`` configuration in your manifest.

**Q: What happens if a node (machine) fails?**

Kubernetes detects the failure and reschedules pods from the failed node onto
healthy nodes. Combined with Scalable's retry logic, tasks on the failed node
are re-executed on new workers.

**Q: Is Kubernetes free?**

Kubernetes itself is open-source (free). But you pay for:

* The machines (nodes) that form the cluster
* Managed K8s services (EKS, GKE, AKS charge a management fee)
* Networking and storage

On-premise clusters have hardware and maintenance costs instead.


What You Learned
-----------------

.. list-table::
   :header-rows: 1
   :widths: 30 70

   * - Term
     - Definition
   * - Container Orchestration
     - Automating deployment, management, and scaling of containers
   * - Kubernetes (K8s)
     - Industry-standard container orchestration platform
   * - Pod
     - Smallest deployable unit in K8s (usually = one container)
   * - Node
     - Physical or virtual machine in the K8s cluster
   * - Namespace
     - Isolation boundary for resources within a cluster
   * - Operator
     - K8s extension that manages complex applications automatically
   * - kubectl
     - Command-line tool for interacting with Kubernetes
   * - Helm
     - Package manager for Kubernetes applications
   * - Resource Requests
     - Minimum guaranteed CPU/memory for a pod
   * - Resource Limits
     - Maximum allowed CPU/memory for a pod
   * - Custom Resource (CRD)
     - User-defined extension to Kubernetes resource types
   * - Image Pull
     - Downloading a container image from a registry


Next Steps
-----------

You now understand Kubernetes fundamentals and how Scalable uses it for
container-based distributed workflows.

* **Next beginner tutorial:** :ref:`beginner_ml_emulation` — using machine
  learning to optimize workflows
* **Standard tutorial:** :ref:`tutorial_kubernetes` — production K8s
  deployment, CI/CD integration, and advanced pod management
* **Explore:** If you have access to a K8s cluster, try running
  ``kubectl get nodes`` to see what machines are available, and
  ``kubectl get namespaces`` to see the isolation boundaries.
