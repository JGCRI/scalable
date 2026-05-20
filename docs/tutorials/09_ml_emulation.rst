.. _tutorial_ml_advanced:

======================================================
Tutorial 9: ML-Driven Scaling and Model Emulation
======================================================

What You Will Learn
-------------------

By the end of this tutorial you will:

* Train and use the LearnedAdvisor for ML-backed resource predictions.
* Configure the AdaptiveScaler with ML-informed decisions.
* Mark functions as emulatable with the ``@emulatable`` decorator.
* Build, register, and dispatch surrogate models.
* Implement confidence-gated routing between emulators and full models.
* Use active learning to improve emulator accuracy over time.

Prerequisites
-------------

* Completed :ref:`tutorial_getting_started`, :ref:`tutorial_telemetry`, and
  :ref:`tutorial_scaling_strategies`.
* ``pip install scalable[ml]`` (installs ``scikit-learn``, ``dask-ml``,
  ``joblib``).
* At least 5 completed telemetry runs (more history → better predictions).

Scenario
--------

Your pipeline has been running for weeks, accumulating telemetry data. You want
to leverage this history to (1) automatically predict optimal resource
allocations for new runs, and (2) replace expensive model invocations with
fast surrogate models when confidence is high. Both features reduce cost and
time without sacrificing accuracy.

Part A: ML-Driven Resource Advising
=====================================

Step 1: The ResourceAdvisor (Baseline)
---------------------------------------

Before ML, Scalable provides a deterministic, quantile-based advisor:

.. code-block:: python

   from scalable import ResourceAdvisor

   advisor = ResourceAdvisor.from_history("./.scalable/runs")
   recommendation = advisor.recommend(
       task="run_gcam",
       target="local",
       confidence=0.95,
   )

   print(f"Recommended workers: {recommendation.workers}")
   print(f"Resources: {recommendation.resources}")
   print(f"Confidence: {recommendation.confidence}")
   print(f"Evidence: {recommendation.evidence}")

Expected output:

.. code-block:: text

   Recommended workers: {'gcam': 4}
   Resources: {'gcam': {'cpus': 8, 'memory': '32G', 'walltime': '02:30:00'}}
   Confidence: 0.95
   Evidence: {'runs_analyzed': 12, 'method': 'quantile', 'percentile': 95}

The deterministic advisor uses simple quantile statistics (P95 of historical
duration and resource usage). It's reliable but doesn't adapt to input
characteristics — it treats all invocations of ``run_gcam`` identically.

Step 2: The LearnedAdvisor (ML-Enhanced)
-----------------------------------------

The :class:`~scalable.ml.learned_advisor.LearnedAdvisor` trains a machine
learning model on your telemetry to predict resource requirements based on
task features:

.. code-block:: python

   from scalable import LearnedAdvisor

   # Train from telemetry history
   advisor = LearnedAdvisor.from_history(
       "./.scalable/runs",
       model_type="gradient_boosting",  # or "random_forest", "linear"
   )

   # Predict resources for a specific task with input features
   recommendation = advisor.recommend(
       task="run_gcam",
       target="hpc",
       features={
           "num_scenarios": 50,
           "input_size_mb": 2048,
           "time_horizon": 2100,
       },
   )

   print(f"Predicted workers: {recommendation.workers}")
   print(f"Predicted resources: {recommendation.resources}")
   print(f"Model confidence: {recommendation.confidence:.2f}")

Expected output:

.. code-block:: text

   Predicted workers: {'gcam': 8}
   Predicted resources: {'gcam': {'cpus': 16, 'memory': '48G', 'walltime': '03:15:00'}}
   Model confidence: 0.87

**How it works:**

1. The advisor scans telemetry run directories for completed tasks.
2. It extracts features: task name, input sizes, component resources, target
   type, historical duration, peak memory.
3. A gradient boosting model (or random forest) is trained to predict optimal
   resource allocation given input features.
4. Predictions include confidence intervals — low confidence triggers
   fallback to the deterministic advisor.

Step 3: Model Types and Trade-Offs
------------------------------------

.. list-table::
   :header-rows: 1
   :widths: 20 30 25 25

   * - Model Type
     - Accuracy
     - Training Speed
     - When to Use
   * - ``linear``
     - Low
     - Fast (<1s)
     - Few runs, simple patterns
   * - ``random_forest``
     - Medium
     - Moderate (5–30s)
     - Moderate history, non-linear patterns
   * - ``gradient_boosting``
     - High
     - Slow (30–120s)
     - Rich history (50+ runs), complex patterns

Choose via CLI:

.. code-block:: bash

   # Use the ML advisor from CLI
   scalable advise --task run_gcam --model-type gradient_boosting --format json

.. code-block:: json

   {
     "task": "run_gcam",
     "workers": {"gcam": 8},
     "resources": {"gcam": {"cpus": 16, "memory": "48G", "walltime": "03:15:00"}},
     "confidence": 0.87,
     "model_type": "gradient_boosting"
   }

Step 4: AdaptiveScaler with ML Predictions
--------------------------------------------

Combine the LearnedAdvisor with real-time scaling:

.. code-block:: python

   from scalable import AdaptiveScaler, LearnedAdvisor, ScalableSession

   # Train advisor
   advisor = LearnedAdvisor.from_history("./.scalable/runs", model_type="gradient_boosting")

   # Create adaptive scaler backed by ML predictions
   scaler = AdaptiveScaler(
       advisor=advisor,
       min_workers={"gcam": 2, "postprocess": 1},
       max_workers={"gcam": 30, "postprocess": 10},
       scale_up_threshold=0.7,
       scale_down_threshold=0.3,
       cooldown_seconds=90,
   )

   session = ScalableSession.from_yaml("./scalable.yaml", target="aws")
   client = session.start()

   # Submit work in batches and let the scaler decide
   for batch in scenario_batches:
       futures = [client.submit(run_gcam, s, tag="gcam") for s in batch]

       decision = scaler.evaluate(
           pending_tasks=[{"tag": "gcam", "features": {"input_size_mb": s.size}} for s in batch],
           active_workers={"gcam": 10},
           recent_completions=[{"tag": "gcam", "duration_s": 180}],
       )

       if decision.has_changes:
           print(f"ML-informed scaling: {decision.reasoning}")
           print(f"  Confidence: {decision.confidence:.2f}")
           print(f"  Predicted completion: {decision.predicted_completion_time:.0f}s")

   session.close()

The ML-backed scaler considers:

* Current queue depth and worker utilization.
* Predicted task duration from the learned model.
* Historical scaling patterns (what worked before).
* Cost constraints (from the ``max_workers`` ceiling).

Step 5: Hyperparameter Tuning
------------------------------

For optimal predictions, tune the ML model:

.. code-block:: python

   from scalable.ml import HyperparameterSearch

   search = HyperparameterSearch(
       runs_dir="./.scalable/runs",
       model_type="gradient_boosting",
       cv_folds=5,
   )

   best_params = search.run()
   print(f"Best parameters: {best_params}")
   print(f"Cross-validation score: {search.best_score:.3f}")

   # Use best parameters
   advisor = LearnedAdvisor.from_history(
       "./.scalable/runs",
       model_type="gradient_boosting",
       model_params=best_params,
   )

Part B: Model Emulation
=========================

Step 6: The @emulatable Decorator
-----------------------------------

The :func:`~scalable.emulation.decorator.emulatable` decorator marks expensive
functions as candidates for surrogate model replacement:

.. code-block:: python

   from scalable import emulatable


   @emulatable(
       tag="gridlabd",
       inputs=["fuel_cost", "population", "gdp"],
       outputs=["demand_mw", "energy_price"],
       uncertainty="required",
       fallback="full_model",
       domain={
           "fuel_cost": (0, 500),
           "population": (7e9, 12e9),
           "gdp": (50e12, 200e12),
       },
       confidence_threshold=0.9,
   )
   def run_energy_scenario(fuel_cost, population, gdp):
       """Run a full energy demand scenario — takes 30+ minutes."""
       # ... expensive energy model execution ...
       return {"demand_mw": 35.2, "energy_price": 0.12}

Decorator parameters:

``tag``
  Component tag for worker routing when falling back to the full model.

``inputs``
  Named input parameters the emulator expects. Order matters for training data.

``outputs``
  Named output values the emulator produces.

``uncertainty``
  * ``"required"`` — Emulator must provide calibrated uncertainty bounds.
    Predictions without bounds are rejected.
  * ``"optional"`` — Point estimates are accepted.
  * ``"none"`` — No uncertainty checking.

``fallback``
  Strategy when the emulator is unavailable or confidence is low:
  * ``"full_model"`` — Execute the original function.
  * ``"error"`` — Raise an exception.
  * ``"cached"`` — Try the disk cache.

``domain``
  Input validation bounds. Predictions outside the domain always fall back to
  the full model (extrapolation is unreliable).

``confidence_threshold``
  Minimum emulator confidence for accepting a prediction.

Step 7: Training an Emulator
------------------------------

Collect training data by running the full model on a design-of-experiments
grid, then train a surrogate:

.. code-block:: python

   from scalable.emulation import EmulatorRegistry
   import numpy as np

   # Generate training data (Latin Hypercube or similar)
   np.random.seed(42)
   training_inputs = {
       "fuel_cost": np.random.uniform(0, 500, size=100),
       "population": np.random.uniform(7e9, 12e9, size=100),
       "gdp": np.random.uniform(50e12, 200e12, size=100),
   }

   # Run the full model for each sample (expensive!)
   training_outputs = []
   for i in range(100):
       result = run_energy_scenario(
           fuel_cost=training_inputs["fuel_cost"][i],
           population=training_inputs["population"][i],
           gdp=training_inputs["gdp"][i],
       )
       training_outputs.append(result)

   # Register the trained emulator
   registry = EmulatorRegistry(".scalable/emulators")
   registry.register(
       function_name="run_energy_scenario",
       training_inputs=training_inputs,
       training_outputs=training_outputs,
       model_type="gaussian_process",  # Provides uncertainty estimates
   )

   print(f"Emulator registered: {registry.list()}")

Step 8: Confidence-Gated Dispatch
----------------------------------

The :class:`~scalable.emulation.dispatch.EmulatorDispatch` routes calls between
the emulator and full model based on confidence:

.. code-block:: python

   from scalable.emulation import EmulatorDispatch, EmulatorRegistry

   registry = EmulatorRegistry(".scalable/emulators")
   dispatch = EmulatorDispatch(registry, confidence_threshold=0.9)

   # High-confidence prediction (within training domain)
   result = dispatch.predict(
       "run_energy_scenario",
       inputs={"fuel_cost": 100, "population": 8e9, "gdp": 80e12},
   )
   print(f"Source: {result.source}")        # "emulator"
   print(f"Confidence: {result.confidence:.3f}")  # 0.95
   print(f"Prediction: {result.values}")    # {'demand_mw': 34.8, 'energy_price': 0.11}
   print(f"Uncertainty: {result.uncertainty}")  # {'demand_mw': ±1.2, 'energy_price': ±0.02}

   # Low-confidence prediction (edge of domain)
   result = dispatch.predict(
       "run_energy_scenario",
       inputs={"fuel_cost": 490, "population": 11.5e9, "gdp": 190e12},
   )
   print(f"Source: {result.source}")        # "full_model" (fell back)
   print(f"Confidence: {result.confidence:.3f}")  # 0.72 (below threshold)

**Dispatch logic:**

.. code-block:: text

   ┌─────────────────┐     ┌──────────────┐
   │  Input arrives  │────▶│ Domain check │
   └─────────────────┘     └──────┬───────┘
                                   │
                          In domain?│
                      ┌────Yes─────┼────No─────┐
                      │            │            │
               ┌──────▼──────┐    │    ┌───────▼───────┐
               │  Emulator   │    │    │  Full model   │
               │  predict    │    │    │  (fallback)   │
               └──────┬──────┘    │    └───────────────┘
                      │            │
            Confidence > threshold?│
                 ┌──Yes──┼───No────┐
                 │       │         │
          ┌──────▼──┐    │  ┌──────▼───────┐
          │ Accept  │    │  │  Full model  │
          │ result  │    │  │  (fallback)  │
          └─────────┘    │  └──────────────┘
                         │

Step 9: Active Learning
------------------------

Improve emulator accuracy by strategically selecting which points to run with
the full model:

.. code-block:: python

   from scalable.emulation import ActiveLearner

   learner = ActiveLearner(
       registry=registry,
       function_name="run_energy_scenario",
       acquisition="uncertainty",  # Sample where emulator is least confident
       batch_size=10,
   )

   # Get the next batch of points to evaluate with the full model
   next_points = learner.suggest()
   print(f"Suggested {len(next_points)} points for full model evaluation:")
   for point in next_points[:3]:
       print(f"  fuel_cost={point['fuel_cost']:.0f}, "
             f"population={point['population']:.2e}, "
             f"gdp={point['gdp']:.2e}")

   # Run full model on suggested points
   new_results = []
   for point in next_points:
       result = run_energy_scenario(**point)
       new_results.append(result)

   # Update the emulator with new data
   learner.update(next_points, new_results)
   print(f"Emulator updated. New training size: {learner.training_size}")
   print(f"Estimated accuracy improvement: {learner.accuracy_gain:.1%}")

Active learning acquisition strategies:

* ``"uncertainty"`` — Sample where prediction uncertainty is highest.
* ``"expected_improvement"`` — Sample where model is likely wrong.
* ``"random"`` — Uniform random (baseline comparison).

Step 10: Emulation in Production Workflows
--------------------------------------------

Integrate emulation into your pipeline for massive speedups:

.. code-block:: python

   from scalable import ScalableSession, emulatable, cacheable
   from scalable.emulation import EmulatorDispatch, EmulatorRegistry


   @emulatable(
       tag="gridlabd",
       inputs=["fuel_cost", "population"],
       outputs=["demand_mw"],
       uncertainty="required",
       fallback="full_model",
       confidence_threshold=0.9,
   )
   @cacheable(return_type=dict, fuel_cost=float, population=float)
   def run_scenario(fuel_cost: float, population: float) -> dict:
       """Full model — 30 min per call."""
       # ... expensive computation ...
       return {"demand_mw": fuel_cost * 0.1 + population * 1e-10}


   def run_pipeline():
       session = ScalableSession.from_yaml("./scalable.yaml", target="local")
       client = session.start()

       registry = EmulatorRegistry(".scalable/emulators")
       dispatch = EmulatorDispatch(registry, confidence_threshold=0.9)

       results = []
       emulated_count = 0
       full_model_count = 0

       for fc in range(0, 500, 10):
           for pop in [8e9, 9e9, 10e9]:
               # Try emulator first
               result = dispatch.predict(
                   "run_scenario",
                   inputs={"fuel_cost": fc, "population": pop},
               )

               if result.source == "emulator":
                   results.append(result.values)
                   emulated_count += 1
               else:
                   # Fall back to full model via distributed workers
                   fut = client.submit(run_scenario, fc, pop, tag="gridlabd")
                   results.append(fut.result())
                   full_model_count += 1

       print(f"Total scenarios: {emulated_count + full_model_count}")
       print(f"  Emulated: {emulated_count} ({emulated_count/(emulated_count+full_model_count)*100:.0f}%)")
       print(f"  Full model: {full_model_count}")
       print(f"  Time saved: ~{emulated_count * 30} minutes")

       session.close()

Expected output:

.. code-block:: text

   Total scenarios: 150
     Emulated: 128 (85%)
     Full model: 22
     Time saved: ~3840 minutes

Troubleshooting
---------------

**LearnedAdvisor predictions are poor**
  Ensure you have sufficient telemetry history (at least 10–20 completed runs
  with varied inputs). With fewer runs, the deterministic ``ResourceAdvisor``
  is more reliable.

**"ImportError: scikit-learn not installed"**
  Install the ML extra: ``pip install scalable[ml]``.

**Emulator confidence is always low**
  The training domain may not cover your query inputs. Run active learning to
  expand coverage, or check that your domain bounds in ``@emulatable`` match
  the actual input range.

**"EmulatorRegistry: no emulator registered for function"**
  You must train and register an emulator before dispatch can use it. See
  Step 7 for the registration process.

**Active learning suggests the same points repeatedly**
  The learner converges when uncertainty is uniformly low across the domain.
  If it's suggesting the same points, your emulator may already be well-trained.
  Check ``learner.mean_uncertainty`` — if it's below your threshold, no
  further training is needed.

Next Steps
----------

* :ref:`tutorial_ai_composition` — Use AI assistants to generate workflow
  configurations that incorporate emulation.
* :ref:`tutorial_telemetry` — Track emulator vs. full model usage in telemetry
  for cost analysis.
* :ref:`tutorial_cloud_integration` — Deploy emulator-backed workflows to cloud
  for maximum cost savings.
