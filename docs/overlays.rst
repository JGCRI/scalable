Manifest Overlays
=================

Overlays allow a single ``scalable.yaml`` to carry environment-specific
configuration deltas without duplicating the entire manifest.

Concept
-------

An overlay is a named block of configuration that is deep-merged onto the
base manifest when a target references it. This enables:

- Different resource allocations per environment (dev/staging/prod)
- Provider-specific tuning without separate manifest files
- Shared base configuration with targeted overrides

Syntax
------

.. code-block:: yaml

   version: 1
   project:
     name: my-project

   targets:
     local:
       provider: local
     prod:
       provider: kubernetes
       namespace: default
       overlay: prod-resources  # ← references an overlay

   components:
     model:
       cpus: 2
       memory: 4G

   tasks:
     run:
       component: model

   # Named overlays
   overlays:
     prod-resources:
       components:
         model:
           cpus: 16
           memory: 64G
     dev-resources:
       components:
         model:
           cpus: 1
           memory: 2G

Merge Semantics
---------------

- **Dicts** are deep-merged recursively (overlay keys win).
- **Lists** are replaced wholesale (no element-level merge).
- **Scalars** are overwritten by the overlay value.
- The ``overlays:`` top-level key is stripped from the resolved form.
- The ``overlay:`` reference in the target block is also stripped after resolution.

Resolution Order
----------------

1. The parser loads and env-expands the full YAML document.
2. If a ``target_name`` is provided and that target has an ``overlay:`` field,
   the named overlay is looked up in the ``overlays:`` block.
3. The overlay data is deep-merged onto the base document.
4. The resolved form is validated and used for planning/execution.
5. Both ``raw`` (resolved) and ``raw_unresolved`` (pre-overlay) forms are
   preserved in the ``ManifestModel`` for provenance tracking.

CLI Usage
---------

Overlays are automatically resolved when you specify a target:

.. code-block:: bash

   scalable validate scalable.yaml --target prod
   scalable plan --dry-run scalable.yaml --target prod
   scalable run scalable.yaml --target prod

Example
-------

See the full overlay example:

.. literalinclude:: examples/scalable.overlays.yaml
   :language: yaml
