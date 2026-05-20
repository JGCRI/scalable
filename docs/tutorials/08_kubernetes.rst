.. _tutorial_kubernetes:

======================================================
Tutorial 8: Deployment Workflows with Kubernetes
======================================================

What You Will Learn
-------------------

By the end of this tutorial you will:

* Deploy Scalable workflows on Kubernetes using the Dask Kubernetes Operator.
* Configure namespace isolation, resource quotas, and pod specifications.
* Use the Kubernetes provider with adaptive scaling.
* Manage container images and pull secrets.
* Combine Kubernetes with overlays for multi-environment deployments.
* Handle pod evictions and node failures.

Prerequisites
-------------

* Completed :ref:`tutorial_getting_started`, :ref:`tutorial_manifest_system`,
  and :ref:`tutorial_scaling_strategies`.
* ``pip install scalable[kubernetes]`` (installs ``dask-kubernetes``,
  ``kubernetes``).
* Access to a Kubernetes cluster (local ``minikube``/``kind`` for development,
  or a managed cluster like GKE/EKS/AKS for production).
* ``kubectl`` configured with cluster access.

Scenario
--------

Your organization runs a shared Kubernetes cluster for all scientific
workloads. You need to deploy the energy forecasting pipeline as a Dask
cluster within your team's namespace, with resource quotas enforced by
platform engineering.
The deployment must support both development (small, fast iterations) and
production (large-scale, fault-tolerant) modes.

Step 1: Install the Dask Kubernetes Operator
---------------------------------------------

The Dask Kubernetes Operator manages DaskCluster custom resources in your
cluster:

.. code-block:: bash

   # Install the operator (cluster-admin required, one-time setup)
   helm repo add dask https://helm.dask.org
   helm repo update
   helm install dask-operator dask/dask-kubernetes-operator \
     --namespace dask-operator --create-namespace

Verify the operator is running:

.. code-block:: bash

   kubectl get pods -n dask-operator

.. code-block:: text

   NAME                             READY   STATUS    RESTARTS   AGE
   dask-operator-7f8b6d5c4-x2j9k   1/1     Running   0          2m

Step 2: Configure the Kubernetes Target
-----------------------------------------

.. code-block:: yaml

   # scalable.yaml
   version: 1
   project:
     name: energy-forecast-k8s
     default_storage: gs://${GCS_BUCKET}/scalable-runs/

   targets:
     k8s-dev:
       provider: kubernetes
       namespace: energy-dev
       image: gcr.io/${GCP_PROJECT}/energy-model:${IMAGE_TAG:-latest}
       adaptive:
         minimum: 1
         maximum: 5
       overlay: k8s-dev-resources

     k8s-prod:
       provider: kubernetes
       namespace: energy-prod
       image: gcr.io/${GCP_PROJECT}/energy-model:${IMAGE_TAG}
       adaptive:
         minimum: 4
         maximum: 40
       overlay: k8s-prod-resources

   components:
     gridlabd:
       image: gcr.io/${GCP_PROJECT}/gridlabd:5.0
       cpus: 8
       memory: 32G
       tags: [multi-sector-dynamics, energy]
       env:
         GRIDLABD_DATA: /data/gridlabd

     postprocess:
       image: gcr.io/${GCP_PROJECT}/postprocess:latest
       cpus: 4
       memory: 16G
       tags: [analysis]

   tasks:
     run_gcam:
       component: gcam
       cache: true
       outputs:
         database: dir

     aggregate:
       component: postprocess
       cache: true

   overlays:
     k8s-dev-resources:
       components:
         gcam:
           cpus: 2
           memory: 8G
         postprocess:
           cpus: 1
           memory: 4G

     k8s-prod-resources:
       components:
         gcam:
           cpus: 16
           memory: 64G
         postprocess:
           cpus: 8
           memory: 32G

Step 3: Namespace Setup
------------------------

Create isolated namespaces for development and production:

.. code-block:: bash

   # Development namespace
   kubectl create namespace energy-dev
   kubectl label namespace energy-dev team=energy env=dev

   # Production namespace
   kubectl create namespace energy-prod
   kubectl label namespace energy-prod team=energy env=prod

Apply resource quotas to prevent runaway usage:

.. code-block:: yaml

   # resource-quota.yaml
   apiVersion: v1
   kind: ResourceQuota
   metadata:
     name: energy-forecast-quota
     namespace: energy-prod
   spec:
     hard:
       requests.cpu: "160"
       requests.memory: "640Gi"
       limits.cpu: "200"
       limits.memory: "800Gi"
       pods: "50"

.. code-block:: bash

   kubectl apply -f resource-quota.yaml

Step 4: Image Pull Secrets
---------------------------

If your container registry requires authentication:

.. code-block:: bash

   # For GCR (Google Container Registry)
   kubectl create secret docker-registry gcr-secret \
     --docker-server=gcr.io \
     --docker-username=_json_key \
     --docker-password="$(cat service-account-key.json)" \
     --namespace energy-prod

   # For ECR (AWS Elastic Container Registry)
   kubectl create secret docker-registry ecr-secret \
     --docker-server=123456789.dkr.ecr.us-east-1.amazonaws.com \
     --docker-username=AWS \
     --docker-password="$(aws ecr get-login-password)" \
     --namespace energy-prod

The Kubernetes provider automatically attaches these secrets to worker pods
when the image URI matches the registry.

Step 5: Run a Development Workflow
-----------------------------------

.. code-block:: bash

   export GCP_PROJECT=my-gcp-project
   export GCS_BUCKET=energy-artifacts
   export IMAGE_TAG=dev-$(git rev-parse --short HEAD)

   # Validate
   scalable validate ./scalable.yaml

   # Plan (shows pod resource requests)
   scalable plan ./scalable.yaml --target k8s-dev --dry-run

.. code-block:: text

   Plan created for target 'k8s-dev' (provider: kubernetes)
   Namespace: energy-dev
   Workers:
     gcam: 2 pods (2 cpu, 8G memory)
     postprocess: 1 pod (1 cpu, 4G memory)
   Adaptive: min=1, max=5

Run the workflow:

.. code-block:: python

   from scalable import ScalableSession

   session = ScalableSession.from_yaml("./scalable.yaml", target="k8s-dev")
   plan = session.plan(dry_run=True)
   client = session.start(plan)

   # Submit tasks — they run in Kubernetes pods
   futures = [client.submit(run_gcam, s, tag="gcam") for s in range(5)]
   results = client.gather(futures)

   session.close()

**What happens under the hood:**

1. The :class:`~scalable.providers.kubernetes.KubernetesProvider` creates a
   ``DaskCluster`` custom resource in the ``energy-dev`` namespace.
2. The Dask Kubernetes Operator provisions scheduler and worker pods.
3. Worker pods are labeled with component tags for affinity scheduling.
4. The adaptive scaler monitors task backlog and scales pods up/down within
   the configured bounds.
5. On ``session.close()``, the ``DaskCluster`` resource is deleted, cleaning
   up all pods.

Step 6: Monitor Pods and Scaling
---------------------------------

Watch Kubernetes events in real-time:

.. code-block:: bash

   # Watch pods in the namespace
   kubectl get pods -n energy-dev -w

.. code-block:: text

   NAME                                READY   STATUS    RESTARTS   AGE
   dask-scheduler-energy-dev-0         1/1     Running   0          30s
   dask-worker-gridlabd-0              1/1     Running   0          25s
   dask-worker-gridlabd-1              1/1     Running   0          25s
   dask-worker-postprocess-0           1/1     Running   0          25s

   # Scale-up event
   dask-worker-gridlabd-2              0/1     Pending   0          0s
   dask-worker-gridlabd-2              1/1     Running   0          15s

Check the Dask dashboard (port-forward the scheduler):

.. code-block:: bash

   kubectl port-forward -n energy-dev svc/dask-scheduler-energy-dev 8787:8787
   # Open http://localhost:8787 in your browser

Step 7: Production Deployment
------------------------------

For production, ensure high availability and fault tolerance:

.. code-block:: bash

   export IMAGE_TAG=v2.1.0  # Pinned release tag
   scalable run ./scalable.yaml --target k8s-prod --workflow pipeline.py

Production considerations:

**Pod disruption budgets** — Prevent too many workers from being evicted
simultaneously:

.. code-block:: yaml

   # pdb.yaml
   apiVersion: policy/v1
   kind: PodDisruptionBudget
   metadata:
     name: dask-workers-pdb
     namespace: energy-prod
   spec:
     minAvailable: "50%"
     selector:
       matchLabels:
         app: dask-worker

.. code-block:: bash

   kubectl apply -f pdb.yaml

**Priority classes** — Ensure your workload gets scheduled before lower-priority
jobs:

.. code-block:: yaml

   apiVersion: scheduling.k8s.io/v1
   kind: PriorityClass
   metadata:
     name: energy-production
   value: 1000
   globalDefault: false
   description: "Priority for production energy forecasting runs"

Step 8: Handling Pod Evictions
-------------------------------

Kubernetes may evict pods due to resource pressure or node maintenance.
Scalable's error handling (see :ref:`tutorial_error_handling`) catches these
as ``KilledWorker`` exceptions:

.. code-block:: python

   from distributed import as_completed

   session = ScalableSession.from_yaml("./scalable.yaml", target="k8s-prod")
   client = session.start()

   futures = [client.submit(run_gcam, s, tag="gcam") for s in range(200)]

   results = []
   retry_queue = []

   for future in as_completed(futures):
       try:
           results.append(future.result())
       except Exception as e:
           if "KilledWorker" in str(type(e).__name__):
               # Pod was evicted — retry
               scenario_id = future.key.split("-")[-1]
               retry_queue.append(scenario_id)
           else:
               print(f"Permanent failure: {e}")

   # Retry evicted tasks
   if retry_queue:
       print(f"Retrying {len(retry_queue)} evicted tasks...")
       retry_futures = [
           client.submit(run_gcam, s, tag="gcam") for s in retry_queue
       ]
       retry_results = client.gather(retry_futures)
       results.extend(retry_results)

   session.close()

Step 9: CI/CD Integration
---------------------------

Automate Kubernetes deployments from your CI pipeline:

.. code-block:: yaml

   # .github/workflows/scalable-prod.yaml
   name: Production Pipeline Run
   on:
     workflow_dispatch:
       inputs:
         scenarios:
           description: "Number of scenarios"
           default: "200"

   jobs:
     run:
       runs-on: ubuntu-latest
       steps:
         - uses: actions/checkout@v4

         - uses: google-github-actions/auth@v2
           with:
             credentials_json: ${{ secrets.GCP_SA_KEY }}

         - uses: google-github-actions/get-gke-credentials@v2
           with:
             cluster_name: energy-cluster
             location: us-central1

         - name: Install Scalable
           run: pip install scalable[kubernetes,cloud]

         - name: Run Pipeline
           env:
             GCP_PROJECT: ${{ vars.GCP_PROJECT }}
             GCS_BUCKET: ${{ vars.GCS_BUCKET }}
             IMAGE_TAG: ${{ github.sha }}
             SCALABLE_TARGET: k8s-prod
           run: |
             scalable validate ./scalable.yaml
             scalable run ./scalable.yaml --target k8s-prod --workflow pipeline.py

Step 10: Local Development with minikube
------------------------------------------

For local Kubernetes development without a cloud cluster:

.. code-block:: bash

   # Start minikube
   minikube start --cpus=4 --memory=8192

   # Install Dask operator
   helm install dask-operator dask/dask-kubernetes-operator

   # Build and load image locally
   docker build -t energy-model:local .
   minikube image load energy-model:local

   # Use local image in manifest
   export IMAGE_TAG=local
   scalable run ./scalable.yaml --target k8s-dev --workflow workflow.py

This gives you a realistic Kubernetes environment for testing pod scheduling,
resource limits, and failure modes before deploying to production.

Troubleshooting
---------------

**Pods stuck in "Pending" state**
  Check resource availability: ``kubectl describe pod <pod-name> -n <ns>``.
  Common causes: insufficient cluster capacity, resource quota exceeded, or
  node selector constraints not met.

**"ImagePullBackOff" error**
  The image URI is wrong or the pull secret is missing/expired. Verify:
  ``kubectl get secret -n <ns>`` and check image URI spelling.

**Workers fail to connect to scheduler**
  Ensure network policies allow pod-to-pod communication within the namespace.
  The scheduler service must be reachable on port 8786.

**Adaptive scaling not working**
  Verify the Dask Kubernetes Operator is running and the ``DaskCluster``
  resource has ``adaptive`` section configured. Check operator logs:
  ``kubectl logs -n dask-operator deployment/dask-operator``.

**Resource quota prevents scaling**
  If ``adaptive.maximum`` exceeds what the quota allows, pods will stay
  pending. Set maximum to a value within your quota limits.

Next Steps
----------

* :ref:`tutorial_ml_advanced` — Use ML predictions to pre-size Kubernetes pods
  based on historical resource usage.
* :ref:`tutorial_error_handling` — Build resilient pipelines that handle pod
  evictions gracefully.
* :ref:`tutorial_ai_composition` — Auto-generate Kubernetes manifests from
  natural language workflow descriptions.
