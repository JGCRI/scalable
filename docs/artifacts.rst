Artifact Store
==============

The :mod:`scalable.artifacts` module (Phase 3) provides a protocol-based
abstraction for storing and retrieving workflow artifacts across local and
remote backends.

Overview
--------

- :class:`~scalable.artifacts.base.ArtifactStore` — protocol interface
- :class:`~scalable.artifacts.local.LocalArtifactStore` — filesystem backend
- :class:`~scalable.artifacts.fsspec_store.FsspecArtifactStore` — S3/GCS/memory
- :func:`~scalable.artifacts.factory.build_artifact_store` — URI-based factory

Usage
-----

.. code-block:: python

   from scalable.artifacts import build_artifact_store

   # Local storage
   store = build_artifact_store("./artifacts")
   ref = store.put("output.csv", "runs/run-001/output.csv")
   print(ref.uri, ref.digest, ref.size_bytes)

   # S3 storage (requires scalable[cloud])
   store = build_artifact_store("s3://my-bucket/artifacts/")
   ref = store.put("model_output/", "runs/run-001/model_output")

   # GCS storage
   store = build_artifact_store("gs://my-bucket/artifacts/")

Manifest Integration
--------------------

Set ``project.default_storage`` in your manifest to configure where artifacts
are stored:

.. code-block:: yaml

   project:
     name: my-project
     default_storage: s3://my-bucket/scalable-runs/

Or override via the ``SCALABLE_DEFAULT_STORAGE`` environment variable.

Remote Cache
------------

The artifact store layer also powers the remote cache backend. Enable it with:

.. code-block:: bash

   export SCALABLE_CACHE_REMOTE=s3://my-bucket/cache/

When enabled, cache results are stored remotely in addition to the local
diskcache, allowing cache sharing across machines.

Session Integration
-------------------

Record artifacts during a session for provenance tracking:

.. code-block:: python

   from scalable import ScalableSession

   session = ScalableSession.from_yaml("scalable.yaml", target="local")
   # ... run tasks ...
   session.record_artifact("output.csv", kind="result")

Artifact metadata is recorded in the ``artifacts.jsonl`` telemetry stream.

See Also
--------

- :doc:`cloud` — Cloud providers with remote storage support
- :doc:`telemetry` — Artifact events in run telemetry
- :doc:`manifest` — Configuring ``project.default_storage``
