Model Emulation
===============

The :mod:`scalable.emulation` package (Phase 5) provides scientific model
emulation capabilities with uncertainty-aware surrogate model dispatch. This
enables fast approximations of expensive model runs when confidence is high,
with automatic fallback to the full model otherwise.

Installation
------------

.. code-block:: bash

   pip install scalable[ml]

The emulation subsystem shares the ``ml`` optional dependency group
(``scikit-learn``, ``joblib``).

Overview
--------

The emulation workflow follows this pattern:

1. Mark expensive functions with the ``@emulatable`` decorator.
2. Train surrogate models on historical input/output data.
3. Register trained emulators in the ``EmulatorRegistry``.
4. Use ``EmulatorDispatch`` for confidence-gated routing between the
   emulator and the full model.

The ``@emulatable`` Decorator
-----------------------------

Mark functions as emulation-capable by declaring their inputs, outputs,
domain bounds, and confidence thresholds:

.. code-block:: python

   from scalable import emulatable

   @emulatable(
       inputs=["temperature", "precipitation", "co2"],
       outputs=["yield", "water_use"],
       domain_bounds={
           "temperature": (250, 350),
           "precipitation": (0, 5000),
           "co2": (280, 1200),
       },
       confidence_threshold=0.9,
   )
   def run_crop_model(temperature, precipitation, co2):
       # Expensive scientific model execution
       ...
       return {"yield": result_yield, "water_use": result_water}

The decorator attaches metadata to the function for registry lookup and
domain validation.

EmulatorRegistry
----------------

:class:`~scalable.emulation.EmulatorRegistry` manages trained surrogate
models with filesystem persistence, domain validation, and versioning:

.. code-block:: python

   from scalable import EmulatorRegistry

   registry = EmulatorRegistry(".scalable/emulators")

   # Register a trained emulator
   registry.register(
       name="run_crop_model",
       emulator=trained_model,
       metadata={"version": "1.0", "training_samples": 500},
   )

   # List registered emulators
   emulators = registry.list()

   # Load a specific emulator
   info = registry.get("run_crop_model")
   print(info.metadata)

EmulatorDispatch
----------------

:class:`~scalable.emulation.EmulatorDispatch` provides confidence-gated
routing between the emulator and the full model:

.. code-block:: python

   from scalable import EmulatorDispatch, EmulatorRegistry

   registry = EmulatorRegistry(".scalable/emulators")
   dispatch = EmulatorDispatch(registry, confidence_threshold=0.9)

   # Predict using the emulator when confident, fall back to full model
   result = dispatch.predict(
       "run_crop_model",
       inputs={"temperature": 300, "precipitation": 1200, "co2": 400},
   )
   print(result.source)       # "emulator" or "full_model"
   print(result.confidence)   # e.g. 0.95
   print(result.prediction)

Each dispatch decision is recorded as an ``EmulationEvent`` in telemetry,
including source, confidence, fallback reason, and domain validity.

Surrogate Models
----------------

Built-in surrogate model implementations:

- :class:`~scalable.emulation.GradientBoostingEmulator` — tree-based
  uncertainty estimation via gradient boosting
- :class:`~scalable.emulation.RandomForestEmulator` — ensemble-based
  uncertainty from tree variance

Both implement the :class:`~scalable.emulation.TrainedEmulator` protocol:

.. code-block:: python

   from scalable.emulation import GradientBoostingEmulator

   emulator = GradientBoostingEmulator()
   emulator.fit(X_train, y_train)

   prediction = emulator.predict(X_new)
   print(prediction.mean)
   print(prediction.uncertainty)

ActiveLearner
-------------

:class:`~scalable.emulation.ActiveLearner` provides intelligent scenario
selection for iteratively improving emulator accuracy:

.. code-block:: python

   from scalable import ActiveLearner

   learner = ActiveLearner(
       strategy="expected_improvement",  # or "maximum_uncertainty", "random"
       batch_size=10,
   )

   # Suggest next scenarios to run with the full model
   candidates = learner.suggest(
       emulator=trained_emulator,
       domain_bounds={"temperature": (250, 350), "precipitation": (0, 5000)},
       existing_data=X_train,
   )

Acquisition strategies:

- ``expected_improvement`` — prioritize regions where improvement is likely
- ``maximum_uncertainty`` — sample where the emulator is least certain
- ``random`` — uniform random sampling within domain bounds

Uncertainty Calibration
-----------------------

Assess emulator reliability with calibration metrics:

.. code-block:: python

   from scalable.emulation import calibrate_emulator

   result = calibrate_emulator(emulator, X_test, y_test)
   print(result.coverage)    # fraction of test points within intervals
   print(result.sharpness)   # average interval width

Configuration
-------------

Emulation features are controlled via environment variables:

- ``SCALABLE_EMULATION`` — Enable/disable emulation dispatch (default: ``0``)
- ``SCALABLE_EMULATOR_DIR`` — Emulator registry directory
  (default: ``.scalable/emulators``)
- ``SCALABLE_EMULATION_CONFIDENCE`` — Default confidence threshold
  (default: ``0.9``)

