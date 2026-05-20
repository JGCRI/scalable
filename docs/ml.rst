ML Optimization
===============

The :mod:`scalable.ml` package (Phase 5) provides machine-learning-backed
resource prediction, adaptive worker scaling, and distributed hyperparameter
tuning. All features degrade gracefully to Phase 2 heuristic advising when
``scalable[ml]`` is not installed.

Installation
------------

.. code-block:: bash

   pip install scalable[ml]

This installs ``scikit-learn >= 1.3``, ``dask-ml >= 2023.3.24``, and
``joblib >= 1.3``.

LearnedAdvisor
--------------

:class:`~scalable.ml.LearnedAdvisor` provides ML-backed resource
recommendations using gradient boosting, random forest, or quantile regression
trained on run telemetry history.

.. code-block:: python

   from scalable import LearnedAdvisor

   advisor = LearnedAdvisor.from_history(
       "./.scalable/runs",
       model_type="gradient_boosting",
   )
   recommendation = advisor.recommend(task="run_gcam", target="local")
   print(recommendation.resources)
   print(recommendation.confidence)

Supported model types:

- ``gradient_boosting`` (default) — gradient boosting regressor
- ``random_forest`` — random forest regressor
- ``quantile_regression`` — quantile regression for interval estimates

When insufficient training data is available, ``LearnedAdvisor`` transparently
falls back to the Phase 2 :class:`~scalable.advising.ResourceAdvisor` heuristic.

AdaptiveScaler
--------------

:class:`~scalable.ml.AdaptiveScaler` provides real-time adaptive worker
scaling with configurable thresholds, min/max bounds, and cooldown periods.

.. code-block:: python

   from scalable import AdaptiveScaler

   scaler = AdaptiveScaler(
       min_workers=1,
       max_workers=16,
       scale_up_threshold=0.8,
       scale_down_threshold=0.3,
       cooldown_seconds=60,
   )
   decision = scaler.evaluate(current_metrics)
   print(decision.action)       # "scale_up", "scale_down", or "hold"
   print(decision.target_workers)

FeatureExtractor
----------------

:class:`~scalable.ml.FeatureExtractor` provides telemetry feature engineering
with rolling aggregates, task identity hashing, and user-provided input
features for ML model training.

.. code-block:: python

   from scalable.ml import FeatureExtractor

   extractor = FeatureExtractor()
   features = extractor.extract(telemetry_records)

HyperparameterSearch
--------------------

:class:`~scalable.ml.HyperparameterSearch` integrates Dask-ML distributed
hyperparameter tuning with support for hyperband, successive halving, and
random search strategies. Falls back to sklearn ``GridSearchCV`` when
``dask-ml`` is unavailable.

.. code-block:: python

   from scalable import HyperparameterSearch

   search = HyperparameterSearch(
       strategy="hyperband",
       param_distributions={
           "n_estimators": [50, 100, 200],
           "max_depth": [3, 5, 10],
       },
   )
   result = search.fit(X_train, y_train)
   print(result.best_params)
   print(result.best_score)

Model Validation
----------------

Use ``cross_validate_advisor`` to assess model quality before deployment:

.. code-block:: python

   from scalable.ml import cross_validate_advisor

   quality = cross_validate_advisor(advisor, X_test, y_test)
   print(quality.mae)
   print(quality.coverage)

CLI Command
-----------

The ``scalable advise`` command provides ML-backed recommendations from the
command line:

.. code-block:: bash

   scalable advise --task run_gcam --target local --confidence 0.95
   scalable advise --task run_gcam --model-type random_forest --format json

Options:

- ``--task`` — Task name to get recommendations for (required)
- ``--target`` — Deployment target to scope recommendations
- ``--runs-dir`` — Path to runs directory (default: ``.scalable/runs``)
- ``--model-type`` — ML model type (``gradient_boosting``, ``random_forest``,
  ``quantile_regression``)
- ``--confidence`` — Confidence level (default: 0.95)
- ``--format`` — Output format (``text`` or ``json``)
- ``--output`` — Output file path (default: stdout)

Configuration
-------------

ML features are controlled via environment variables:

- ``SCALABLE_ML`` — Enable/disable ML features (default: ``1``)
- ``SCALABLE_ML_CACHE_DIR`` — Model cache directory
  (default: ``.scalable/models``)

