Deterministic Resource Advising
================================

Scalable provides a deterministic :class:`~scalable.advising.ResourceAdvisor`
that derives conservative resource recommendations from historical run
telemetry.

Quick start
-----------

.. code-block:: python

    from scalable import ResourceAdvisor

    advisor = ResourceAdvisor.from_history("./.scalable/runs")
    recommendation = advisor.recommend(
        task="run_gcam",
        target="local",
        confidence=0.95,
    )

    print(recommendation.workers)
    print(recommendation.resources)
    print(recommendation.evidence)

Design intent
-------------

This advisor is heuristic and explainable. It uses observed request/runtime
history and confidence-indexed quantiles. No external dependencies beyond the
base Scalable install are required.

The advisor returns a :class:`~scalable.advising.ResourceRecommendation` with:

- ``workers`` — recommended worker count
- ``resources`` — recommended per-worker resource allocation
- ``evidence`` — source data summary backing the recommendation
- ``confidence`` — achieved confidence level

CLI access
----------

.. code-block:: bash

    scalable advise --task run_gcam --target local --confidence 0.95

The CLI ``advise`` command first attempts ML-backed recommendations (if
``scalable[ml]`` is installed) and falls back to the heuristic advisor when
insufficient training data is available or the ML extra is missing.

ML-backed advising
------------------

When ``scalable[ml]`` is installed, :class:`~scalable.ml.LearnedAdvisor`
provides ML-backed predictions using gradient boosting, random forest, or
quantile regression trained on telemetry history. See :doc:`ml` for details.

The heuristic advisor documented on this page remains the deterministic
baseline and fallback for all ML-backed recommendations.

