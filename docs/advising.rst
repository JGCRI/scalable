Deterministic Resource Advising
==============================

Phase 2 adds a baseline deterministic :class:`ResourceAdvisor` that derives
conservative resource recommendations from historical run telemetry.

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
history and confidence-indexed quantiles. Learned ML models are deferred to
later phases.

