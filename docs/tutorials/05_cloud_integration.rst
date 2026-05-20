.. _tutorial_cloud_integration:

======================================================
Tutorial 5: Cloud Integration with AWS and GCP
======================================================

What You Will Learn
-------------------

By the end of this tutorial you will:

* Configure AWS Fargate and EC2-backed Dask clusters via Scalable.
* Set up GCP Cloud Run / GKE-based execution.
* Use the artifact store for persistent cloud storage (S3, GCS).
* Estimate costs before running with dry-run planning.
* Deploy multi-target manifests that promote from local to cloud.
* Manage IAM roles, networking, and container registries.

Prerequisites
-------------

* Completed :ref:`tutorial_getting_started` and :ref:`tutorial_manifest_system`.
* ``pip install scalable[cloud]`` (installs ``s3fs``, ``gcsfs``,
  ``dask-cloudprovider``, ``fsspec``).
* AWS credentials configured (``~/.aws/credentials`` or environment variables).
* (For GCP) ``gcloud`` CLI authenticated or ``GOOGLE_APPLICATION_CREDENTIALS`` set.

Scenario
--------

Your energy forecasting pipeline works locally but needs to scale to 50+
concurrent scenarios for a production run. Your organization uses AWS for burst
compute and GCS for long-term data storage. You need to deploy the same
workflow to cloud infrastructure with cost visibility.

Step 1: AWS Target Configuration
----------------------------------

The AWS provider uses ``dask-cloudprovider`` to launch Dask workers on Fargate
(serverless containers) or EC2 instances:

.. code-block:: yaml

   # scalable.yaml
   version: 1
   project:
     name: energy-model-aws
     default_storage: s3://${S3_BUCKET}/scalable-runs/

   targets:
     aws:
       provider: aws
       region: ${AWS_REGION:-us-east-1}
       cluster_type: fargate
       instance_type: m5.xlarge       # For EC2-backed mode
       worker_cpu: 4096               # Fargate CPU units (1024 = 1 vCPU)
       worker_mem: 16384              # Fargate memory in MiB
       image: ${ECR_IMAGE}
       execution_role_arn: ${EXECUTION_ROLE_ARN}
       task_role_arn: ${TASK_ROLE_ARN}
       subnets:
         - ${SUBNET_A}
         - ${SUBNET_B}
       security_groups:
         - ${SG_ID}
       adaptive:
         minimum: 2
         maximum: 20

   components:
     gcam:
       image: ${ECR_IMAGE_GCAM}
       cpus: 4
       memory: 16G
       tags: [multi-sector-dynamics, energy]

     postprocess:
       cpus: 2
       memory: 8G
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

**Key configuration explained:**

``cluster_type``
  ``fargate`` for serverless (no EC2 management) or ``ec2`` for instance-backed
  clusters (lower cost at scale, more control over instance types).

``worker_cpu`` / ``worker_mem``
  Fargate task sizing. CPU is in units of 1024 (= 1 vCPU). Common
  configurations:

  .. list-table::
     :header-rows: 1
     :widths: 20 20 60

     * - CPU
       - Memory
       - Use Case
     * - 1024
       - 4096
       - Light tasks, I/O-bound
     * - 4096
       - 16384
       - Standard compute tasks
     * - 16384
       - 65536
       - Memory-intensive models

``execution_role_arn``
  IAM role assumed by the ECS agent to pull images and write logs. Needs
  ``ecr:GetAuthorizationToken``, ``ecr:BatchGetImage``, ``logs:CreateLogStream``
  permissions.

``task_role_arn``
  IAM role assumed by the running task. Needs S3 read/write for artifacts,
  network access for Dask scheduler communication.

Step 2: Set Up AWS Infrastructure
-----------------------------------

Before running, ensure these AWS resources exist:

**1. ECR Repository (Container Registry):**

.. code-block:: bash

   aws ecr create-repository --repository-name energy-model
   # Push your image
   docker build -t energy-model:latest .
   docker tag energy-model:latest 123456789.dkr.ecr.us-east-1.amazonaws.com/energy-model:latest
   aws ecr get-login-password | docker login --username AWS --password-stdin 123456789.dkr.ecr.us-east-1.amazonaws.com
   docker push 123456789.dkr.ecr.us-east-1.amazonaws.com/energy-model:latest

**2. VPC + Subnets:**

Workers need outbound internet access (for Dask scheduler communication) and
access to S3. Use a VPC with NAT Gateway or VPC endpoints.

**3. Security Group:**

.. code-block:: bash

   # Allow inbound from scheduler, outbound to internet
   aws ec2 create-security-group \
     --group-name scalable-workers \
     --description "Scalable Dask workers"
   aws ec2 authorize-security-group-ingress \
     --group-id sg-xyz789 \
     --protocol tcp --port 8786-8787 \
     --source-group sg-xyz789

**4. IAM Roles:**

.. code-block:: json

   {
     "Version": "2012-10-17",
     "Statement": [
       {
         "Effect": "Allow",
         "Action": [
           "s3:GetObject",
           "s3:PutObject",
           "s3:ListBucket"
         ],
         "Resource": [
           "arn:aws:s3:::my-bucket",
           "arn:aws:s3:::my-bucket/*"
         ]
       }
     ]
   }

Step 3: Dry-Run Cost Estimation
--------------------------------

Before launching real cloud resources, estimate costs:

.. code-block:: bash

   scalable run ./scalable.yaml --target aws --dry-run

.. code-block:: text

   Dry-run plan for target 'aws' (provider: aws):
     Workers: 10 × gcam (4 vCPU, 16 GiB)
              5 × postprocess (2 vCPU, 8 GiB)
     Estimated duration: 2.5 hours
     Estimated cost: $4.82
       Fargate compute: $3.90
       Data transfer: $0.12
       S3 storage: $0.80

Programmatic cost access:

.. code-block:: python

   from scalable import ScalableSession

   session = ScalableSession.from_yaml("./scalable.yaml", target="aws")
   plan = session.plan(dry_run=True)

   if plan.cost_estimate:
       print(f"Estimated cost: ${plan.cost_estimate.total:.2f}")
       print(f"  Compute: ${plan.cost_estimate.compute:.2f}")
       print(f"  Storage: ${plan.cost_estimate.storage:.2f}")
       print(f"  Transfer: ${plan.cost_estimate.transfer:.2f}")

**How cost estimation works:** Scalable uses the
:mod:`scalable.providers.cloud.cost_tables` module which contains region-specific
pricing for Fargate vCPU-hours, memory-hours, and S3 operations. Estimates are
based on the planned worker count, predicted task duration (from telemetry
history if available), and declared storage outputs.

Step 4: GCP Target Configuration
----------------------------------

For Google Cloud Platform, use GCS for storage and either Cloud Run or GKE for
compute:

.. code-block:: yaml

   targets:
     gcp:
       provider: gcp
       region: us-central1
       project_id: ${GCP_PROJECT_ID}
       cluster_type: cloud_run
       worker_cpu: 4
       worker_mem: 16Gi
       image: gcr.io/${GCP_PROJECT_ID}/energy-model:latest
       service_account: ${GCP_SERVICE_ACCOUNT}
       adaptive:
         minimum: 1
         maximum: 15

   project:
     default_storage: gs://${GCS_BUCKET}/scalable-runs/

GCP-specific setup:

.. code-block:: bash

   # Authenticate
   gcloud auth application-default login

   # Push image to GCR
   gcloud builds submit --tag gcr.io/my-project/energy-model:latest .

   # Create GCS bucket for artifacts
   gsutil mb -l us-central1 gs://my-bucket/

Step 5: Artifact Store — Cloud Storage
----------------------------------------

The artifact store provides a unified interface for persisting outputs across
storage backends:

.. code-block:: python

   from scalable.artifacts import build_artifact_store

   # Local storage (default)
   local_store = build_artifact_store("./artifacts")

   # S3 storage
   s3_store = build_artifact_store("s3://my-bucket/artifacts/")

   # GCS storage
   gcs_store = build_artifact_store("gs://my-bucket/artifacts/")

   # Store a file
   ref = s3_store.put("local/output.csv", "runs/run-001/output.csv")
   print(ref)
   # ArtifactRef(uri='s3://my-bucket/artifacts/runs/run-001/output.csv')

   # Retrieve a file
   local_path = s3_store.get("runs/run-001/output.csv", "./downloads/output.csv")

The store is protocol-aware via ``fsspec``: it detects the URI scheme and uses
the appropriate backend (``s3fs`` for S3, ``gcsfs`` for GCS, local filesystem
for paths).

**Integration with workflow output:**

.. code-block:: python

   from scalable import ScalableSession
   from scalable.artifacts import build_artifact_store

   session = ScalableSession.from_yaml("./scalable.yaml", target="aws")
   client = session.start()

   # Run simulation
   result = client.submit(run_gcam, scenario_params, tag="gcam").result()

   # Persist output artifact to configured storage
   store = build_artifact_store(session.manifest.project.default_storage)
   ref = store.put(
       result["output_path"],
       f"runs/{session._telemetry.run_id}/gcam-output.tar.gz",
   )
   print(f"Artifact persisted: {ref.uri}")

Step 6: Multi-Region Deployment
---------------------------------

For global workflows, define targets in multiple regions:

.. code-block:: yaml

   targets:
     aws-east:
       provider: aws
       region: us-east-1
       # ... config ...
       adaptive:
         minimum: 5
         maximum: 50

     aws-west:
       provider: aws
       region: us-west-2
       # ... config ...
       adaptive:
         minimum: 2
         maximum: 20

     gcp-europe:
       provider: gcp
       region: europe-west1
       # ... config ...

Select at runtime:

.. code-block:: bash

   # Heavy production run in us-east-1
   scalable run ./scalable.yaml --target aws-east --workflow pipeline.py

   # Quick validation in us-west-2
   scalable run ./scalable.yaml --target aws-west --workflow pipeline.py --dry-run

Step 7: Cloud + Cache Integration
-----------------------------------

Combine cloud execution with remote caching so repeated runs across different
machines share results:

.. code-block:: bash

   export SCALABLE_CACHE_REMOTE=s3://my-bucket/scalable-cache/

.. code-block:: yaml

   project:
     name: energy-forecast
     default_storage: s3://my-bucket/outputs/

Now:

1. First cloud run computes all scenarios and caches results to S3.
2. Subsequent runs (from any machine) hit the shared cache.
3. Only modified scenarios recompute.

This is particularly powerful for CI/CD: your PR validation pipeline benefits
from the cache populated by previous runs.

Step 8: Environment Variable Template
---------------------------------------

For production deployments, maintain a ``.env`` template:

.. code-block:: bash

   # .env.cloud (do not commit secrets — use secrets manager)
   AWS_REGION=us-east-1
   S3_BUCKET=energy-prod-artifacts
   ECR_IMAGE=123456789.dkr.ecr.us-east-1.amazonaws.com/energy-model:latest
   ECR_IMAGE_GCAM=123456789.dkr.ecr.us-east-1.amazonaws.com/gridlabd:5.0
   EXECUTION_ROLE_ARN=arn:aws:iam::123456789:role/ecsTaskExecutionRole
   TASK_ROLE_ARN=arn:aws:iam::123456789:role/scalableTaskRole
   SUBNET_A=subnet-abc123
   SUBNET_B=subnet-def456
   SG_ID=sg-xyz789
   SCALABLE_CACHE_REMOTE=s3://energy-prod-artifacts/cache/

Load before running:

.. code-block:: bash

   set -a && source .env.cloud && set +a
   scalable run ./scalable.yaml --target aws --workflow pipeline.py

Troubleshooting
---------------

**"botocore.exceptions.NoCredentialsError"**
  AWS credentials are not configured. Run ``aws configure`` or set
  ``AWS_ACCESS_KEY_ID`` and ``AWS_SECRET_ACCESS_KEY`` environment variables.
  For EC2/ECS, ensure the instance profile or task role has necessary
  permissions.

**Fargate task fails with "CannotPullContainerError"**
  The execution role lacks ECR permissions, the image URI is wrong, or the
  image doesn't exist in the specified region. Verify with:
  ``aws ecr describe-images --repository-name energy-model``.

**Workers can't connect to scheduler**
  Security group must allow inbound TCP on the Dask scheduler port (8786)
  from the worker security group. Subnets must have a route to the scheduler
  host (typically your local machine or a bastion).

**GCS "403 Forbidden"**
  The service account lacks ``storage.objects.create`` permission on the
  bucket. Grant the ``roles/storage.objectAdmin`` role.

**Cost estimate shows $0.00**
  Cost tables may not have pricing for your specific region or instance type.
  Check that ``scalable.providers.cloud.cost_tables`` includes your region.

Next Steps
----------

* :ref:`tutorial_telemetry` — Monitor cloud run costs and performance
  through telemetry.
* :ref:`tutorial_kubernetes` — Deploy to Kubernetes for container-native
  orchestration.
* :ref:`tutorial_error_handling` — Handle cloud-specific transient failures
  (timeouts, preemption).
