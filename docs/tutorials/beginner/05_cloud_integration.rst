.. _beginner_cloud_integration:

======================================================
Beginner Tutorial 5: Cloud Computing Fundamentals
======================================================

.. contents:: In This Tutorial
   :local:
   :depth: 2

The Big Picture
----------------

So far, everything has run on your laptop. But what happens when you need more
power than any single machine can provide? Or when you need to run 500
scenarios overnight without keeping your laptop open?

**Cloud computing** lets you rent powerful computers over the internet, use
them for your computation, and stop paying when you're done. Scalable can
deploy your workflows to cloud providers (AWS, GCP) with the same manifest
you use locally — only the target changes.

This tutorial explains cloud computing from first principles: what it is,
how billing works, what all the acronyms mean, and how Scalable integrates
with cloud infrastructure.

What You Will Learn
--------------------

By the end of this tutorial you will:

* Understand what cloud computing is and how it differs from local/HPC.
* Know what AWS and GCP are and their core services.
* Understand object storage (S3, GCS) and why it matters.
* Know what containers are and why they're essential for cloud.
* Configure cloud targets in your Scalable manifest.
* Understand IAM (permissions) and network basics (VPCs, subnets).
* Use Scalable's cost estimation to predict spending.
* Understand artifacts and remote storage.

Prerequisites
--------------

* Completed :ref:`beginner_getting_started` and :ref:`beginner_manifest_system`.
* ``pip install scalable[cloud]`` (for code examples).
* No cloud account is required to understand the concepts — the code examples
  show configuration patterns you can use when you do have access.


Key Concepts Explained
-----------------------

.. admonition:: 💡 Key Concept: What is Cloud Computing?
   :class: tip

   **Cloud computing** means renting computers, storage, and networking from
   a provider (like AWS or Google) over the internet, paying only for what
   you use.

   **Before cloud:** Organizations bought physical servers, installed them in
   data centers, maintained them, and paid for them whether used or idle.

   **With cloud:** You request "give me 10 machines with 32GB RAM for 2 hours"
   and they appear in seconds. When you're done, you stop them and stop
   paying.

   **Three service models:**

   * **IaaS (Infrastructure as a Service)** — rent raw machines (EC2, GCE)
   * **PaaS (Platform as a Service)** — rent a managed platform (App Engine)
   * **Serverless/FaaS** — just run code, no server management (Lambda,
     Fargate)

   Scalable primarily uses **serverless containers** (Fargate) and
   **managed Kubernetes** (GKE/EKS) — you don't manage individual servers.

.. admonition:: 💡 Key Concept: AWS and GCP
   :class: tip

   **AWS (Amazon Web Services)** and **GCP (Google Cloud Platform)** are the
   two largest public cloud providers. They offer hundreds of services, but
   for Scalable you mainly need:

   **AWS services used by Scalable:**

   * **Fargate** — runs containers without managing servers
   * **EC2** — virtual machines (when you need more control)
   * **S3** — object storage (for data and artifacts)
   * **ECR** — container registry (stores your Docker images)

   **GCP services used by Scalable:**

   * **Cloud Run** — serverless containers
   * **GKE** — managed Kubernetes
   * **GCS** — object storage (equivalent to S3)
   * **GCR/Artifact Registry** — container registry

.. admonition:: 💡 Key Concept: Object Storage (S3/GCS)
   :class: tip

   **Object storage** is a cloud service for storing files (called "objects")
   in containers called "buckets." Unlike a filesystem with directories and
   paths, object storage is flat — each object has a unique key (like a URL).

   .. code-block:: text

      s3://my-bucket/scalable-runs/run-001/results.json
      │    │         │                      │
      │    │         │                      └── Object key (name)
      │    │         └── Prefix (like a folder, but it's just part of the key)
      │    └── Bucket name
      └── Protocol (s3:// for AWS, gs:// for GCP)

   **Why object storage instead of a regular filesystem?**

   * **Scalability** — stores petabytes without performance degradation
   * **Durability** — data is replicated across multiple data centers
     (99.999999999% durability on S3)
   * **Accessibility** — accessible from anywhere with credentials
   * **Cost** — very cheap for storage ($0.023/GB/month on S3)
   * **No server** — fully managed, no filesystem to maintain

.. admonition:: 💡 Key Concept: Containers (Introduction)
   :class: tip

   A **container** packages your code plus all its dependencies into a single
   portable unit that runs identically everywhere.

   **The problem containers solve:** "It works on my machine!" — your code
   depends on specific library versions, system tools, and configurations.
   Moving it to another machine (especially in the cloud) often breaks things.

   **A container includes:**

   * Your code
   * All Python packages (with exact versions)
   * System libraries and tools
   * Configuration files
   * Everything needed to run — nothing more

   **Analogy:** A container is like a shipping container for goods. The crane
   doesn't need to know what's inside — it just knows how to move the
   standard-sized container. Similarly, cloud platforms know how to run any
   container without knowing what's inside.

   **Docker** is the most popular container technology. A ``Dockerfile``
   describes how to build a container image:

   .. code-block:: dockerfile

      FROM python:3.12
      COPY requirements.txt .
      RUN pip install -r requirements.txt
      COPY . /app
      WORKDIR /app
      CMD ["python", "workflow.py"]

.. admonition:: 💡 Key Concept: Container Registry
   :class: tip

   A **container registry** is a storage service for container images (like
   a library for containers). You build an image locally, push it to a
   registry, and cloud services pull it when launching workers.

   Common registries:

   * **Docker Hub** — public (free for open source)
   * **ECR** (AWS) — private, integrated with AWS services
   * **GCR / Artifact Registry** (GCP) — private, integrated with GCP
   * **GHCR** (GitHub) — integrated with GitHub Actions

.. admonition:: 💡 Key Concept: IAM (Identity and Access Management)
   :class: tip

   **IAM** is the security system that controls who can do what in the cloud.

   **Analogy:** Think of a building with key cards. IAM defines:

   * **Who** (identity) — users, service accounts, roles
   * **Can do what** (permissions) — read files, launch instances, delete
     buckets
   * **On what** (resources) — specific buckets, instances, registries

   In Scalable's context, your cloud credentials need permissions to:

   * Launch compute resources (Fargate tasks, EC2 instances)
   * Read/write to storage buckets (S3, GCS)
   * Pull container images from registries
   * Create networking resources

.. admonition:: 💡 Key Concept: VPC, Subnets, and Networking
   :class: tip

   **VPC (Virtual Private Cloud)** is an isolated network in the cloud —
   like having your own private data center.

   **Subnets** divide a VPC into segments (like rooms in a building):

   * **Public subnet** — accessible from the internet
   * **Private subnet** — only accessible from within the VPC

   **Security Groups** are firewalls — rules about what traffic is allowed
   in and out.

   For Scalable, workers need to communicate with the scheduler (Dask
   protocol), so they must be in subnets where they can reach each other.
   The details are provider-specific — Scalable's cloud provider handles
   most of this automatically.


Step 1: Cloud Target Configuration
-------------------------------------

Here's how you configure a cloud target in your manifest:

.. code-block:: yaml

   # scalable.yaml
   version: 1
   project:
     name: energy-model
     default_storage: s3://${S3_BUCKET}/scalable-runs/

   targets:
     local:
       provider: local
       max_workers: 4
       processes: false
       containers: none

     aws:
       provider: aws
       region: us-east-1
       cluster_type: fargate
       instance_type: m5.xlarge
       worker_cpu: 4096      # 4 vCPUs (in Fargate units: 1024 = 1 vCPU)
       worker_mem: 16384     # 16 GB (in MB)
       image: 123456789.dkr.ecr.us-east-1.amazonaws.com/energy-model:latest
       adaptive:
         minimum: 1
         maximum: 10

   components:
     analysis:
       cpus: 4
       memory: 16G

   tasks:
     run_analysis:
       component: analysis

.. admonition:: What each cloud setting means
   :class: note

   ``region: us-east-1``
     Which data center to use. Choose the closest to your data or team.
     Different regions have different pricing and available services.

   ``cluster_type: fargate``
     Use AWS Fargate (serverless containers). You don't manage servers —
     AWS allocates compute for each task on demand.

   ``instance_type: m5.xlarge``
     The type of virtual machine. ``m5`` = general purpose, ``xlarge`` =
     4 vCPUs + 16GB RAM. (Used for EC2-backed mode, not Fargate.)

   ``worker_cpu: 4096`` / ``worker_mem: 16384``
     Fargate resource allocation in Fargate units (1024 CPU units = 1 vCPU,
     memory in MB).

   ``image: ...``
     The container image containing your code and dependencies. Workers in
     the cloud run inside this container.

   ``adaptive: {minimum: 1, maximum: 10}``
     Auto-scale between 1 and 10 workers based on queue depth.


Step 2: Understanding Cloud Costs
------------------------------------

.. admonition:: 💡 Key Concept: Pay-Per-Use Pricing
   :class: tip

   Cloud computing charges you for what you use:

   * **Compute:** Per-second or per-hour while instances are running
   * **Storage:** Per-GB-month for data stored
   * **Network:** Per-GB for data transferred out of the cloud
   * **Requests:** Per-request for API calls (small, usually negligible)

   **Example cost breakdown for a Scalable run:**

   .. code-block:: text

      10 Fargate workers × 4 vCPU × 2 hours × $0.04/vCPU-hour = $3.20
      10 workers × 16GB × 2 hours × $0.004/GB-hour               = $1.28
      Output data in S3: 50GB × $0.023/GB-month                   = $1.15/month
      Data transfer: 10GB × $0.09/GB                              = $0.90
      ────────────────────────────────────────────────────────────────
      Total run cost: ~$5.38 + $1.15/month storage

Scalable's cost estimator gives you this breakdown BEFORE you run:

.. code-block:: bash

   scalable plan ./scalable.yaml --target aws --dry-run

.. code-block:: text

   Cost Estimate for target 'aws':
     Compute: $3.20 (10 workers × 2h × $0.04/vCPU-h)
     Memory:  $1.28 (10 workers × 16GB × 2h × $0.004/GB-h)
     Storage: ~$1.15/month (estimated 50GB output)
     ────────
     Total:   ~$5.63 (one-time) + $1.15/month (storage)

.. admonition:: 💡 Key Concept: Spot/Preemptible Instances
   :class: tip

   Cloud providers offer **heavily discounted** compute (60–90% off) with a
   catch: they can terminate your instance with 2 minutes notice if demand
   rises.

   * **AWS Spot Instances** — up to 90% cheaper
   * **GCP Preemptible/Spot VMs** — up to 80% cheaper

   This is useful for fault-tolerant workflows (Tutorial 7) where tasks can
   be retried. Scalable's caching makes this viable — if a spot instance is
   terminated, already-cached results don't need recomputation.


Step 3: The Artifact Store
----------------------------

.. admonition:: 💡 Key Concept: Artifacts
   :class: tip

   **Artifacts** are the outputs of your workflow that you want to persist
   (keep) after the run completes. Examples:

   * Simulation results (JSON, CSV, Parquet files)
   * Model weights (pickle, HDF5 files)
   * Reports and visualizations (HTML, PNG)
   * Logs and diagnostics

   Artifacts are stored in the location specified by
   ``project.default_storage`` — either local filesystem or cloud object
   storage.

.. code-block:: python

   from scalable import ScalableSession

   session = ScalableSession.from_manifest("./scalable.yaml", target="aws")

   # After computation, store artifacts
   session.store_artifact("results/scenario_42.json", result_data)
   # → Uploaded to s3://my-bucket/scalable-runs/run-.../results/scenario_42.json


Step 4: Deploying to the Cloud
--------------------------------

The actual deployment workflow:

.. code-block:: text

   ┌─────────────┐      ┌─────────────┐      ┌─────────────┐
   │ 1. Develop  │─────▶│ 2. Build    │─────▶│ 3. Deploy   │
   │   locally   │      │   container │      │   to cloud  │
   └─────────────┘      └─────────────┘      └─────────────┘
    scalable.yaml         Dockerfile           scalable run
    workflow.py           docker build           --target aws
    --target local        docker push

**Step-by-step:**

1. **Develop locally** — write and test your workflow with ``--target local``
2. **Build a container** — package your code into a Docker image
3. **Push to registry** — upload the image to ECR/GCR
4. **Deploy** — run with ``--target aws`` (or ``gcp``)

.. code-block:: bash

   # Build your container image
   docker build -t energy-model:latest .

   # Tag and push to AWS ECR
   docker tag energy-model:latest 123456789.dkr.ecr.us-east-1.amazonaws.com/energy-model:latest
   docker push 123456789.dkr.ecr.us-east-1.amazonaws.com/energy-model:latest

   # Run in the cloud
   scalable run ./scalable.yaml --target aws

.. admonition:: 🤔 Think About It
   :class: note

   Notice how the Python code (``workflow.py``) doesn't change between local
   and cloud deployment. Only the target selection changes. This is the power
   of declarative manifests + the provider abstraction.


Step 5: GCP Configuration
----------------------------

Google Cloud works similarly:

.. code-block:: yaml

   targets:
     gcp:
       provider: gcp
       region: us-central1
       cluster_type: cloud_run
       worker_cpu: 4
       worker_mem: 16384
       image: gcr.io/my-project/energy-model:latest
       adaptive:
         minimum: 2
         maximum: 20

The concepts are the same — only the service names and configuration keys
differ.


Common Questions
-----------------

**Q: How do I get started with cloud without spending money?**

Both AWS and GCP offer free tiers:

* AWS Free Tier: 12 months of limited free usage
* GCP Free Tier: $300 credit for 90 days

For learning, the ``--dry-run`` flag lets you see what WOULD happen without
actually deploying.

**Q: Is the cloud always more expensive than on-premise?**

Not necessarily. Cloud is more expensive for steady, predictable workloads
(you're paying for convenience and flexibility). It's often cheaper for:

* Burst workloads (need 100 machines for 2 hours, then nothing)
* Variable workloads (demand changes day-to-day)
* Avoiding capital expenditure (no upfront server purchase)

**Q: What if my data is too large to upload to the cloud?**

Options:

* Store data in cloud object storage permanently (especially if generated there)
* Use AWS DataSync or GCS Transfer Service for large migrations
* Use hybrid architectures where data stays on-premise and only compute is in cloud

**Q: Do I need to learn Docker/containers to use cloud features?**

For basic usage, your team lead or DevOps person typically builds the container
image once. You then reference it in your manifest. But understanding
containers conceptually (as taught in this tutorial) helps you debug issues.

**Q: What happens if my cloud run fails halfway through?**

Scalable's caching system means completed tasks are saved. When you re-run,
only the failed/incomplete tasks execute. Combined with spot instances, this
makes cost-effective fault-tolerant workflows possible.


What You Learned
-----------------

.. list-table::
   :header-rows: 1
   :widths: 30 70

   * - Term
     - Definition
   * - Cloud Computing
     - Renting computing resources over the internet, pay-per-use
   * - Object Storage
     - Flat file storage (S3/GCS) addressed by bucket + key
   * - Container
     - Packaged code + dependencies that runs identically anywhere
   * - Container Registry
     - Storage service for container images (ECR, GCR)
   * - IAM
     - Identity and Access Management — who can do what
   * - VPC
     - Virtual Private Cloud — isolated network in the cloud
   * - Subnet
     - Segment within a VPC (public or private)
   * - Fargate
     - AWS serverless container service (no server management)
   * - Region
     - Geographic location of a cloud data center
   * - Spot Instance
     - Discounted compute that can be interrupted (60-90% off)
   * - Artifact
     - Workflow output stored for persistence (results, models)
   * - Pay-Per-Use
     - Billing model charging only for resources consumed
   * - Dry Run
     - Simulating deployment to see costs without spending


Next Steps
-----------

You now understand cloud computing fundamentals and how Scalable deploys
workflows to AWS and GCP.

* **Next beginner tutorial:** :ref:`beginner_telemetry` — understanding what
  happened during your runs
* **Standard tutorial:** :ref:`tutorial_cloud_integration` — production cloud
  patterns, IAM configuration, and cost optimization
* **Explore:** Run ``scalable plan --target aws --dry-run`` on your manifest
  to see the cost estimate. Try different ``worker_cpu`` and ``adaptive.maximum``
  values to see how costs change.
