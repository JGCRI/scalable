.. _beginner_ml_emulation:

======================================================
Beginner Tutorial 9: Machine Learning for Smarter Workflows
======================================================

The Big Picture
----------------

After running your workflow many times, you've accumulated telemetry data
showing how tasks perform: which scenarios are fast, which are slow, how much
memory different inputs require. What if a computer could learn these patterns
and predict optimal resource allocations? Or even replace expensive computations
with fast approximations?

This tutorial introduces **machine learning** concepts in the context of
workflow optimization: using past experience to make smarter decisions about
resource allocation and replacing expensive simulations with fast surrogate
models.

What You Will Learn
--------------------

By the end of this tutorial you will:

* Understand what machine learning is at a high level.
* Know the difference between training and inference.
* Understand how Scalable's LearnedAdvisor predicts resource needs.
* Know what a surrogate model (emulator) is and why it's useful.
* Understand uncertainty and confidence thresholds.
* Know what active learning is and how it improves emulators.
* Use the ``@emulatable`` decorator to mark functions for emulation.

Prerequisites
--------------

* Completed :ref:`beginner_getting_started`, :ref:`beginner_telemetry`, and
  :ref:`beginner_scaling_strategies`.
* ``pip install scalable[ml]`` (installs scikit-learn, dask-ml).
* At least 5 completed telemetry runs (more history → better predictions).


Key Concepts Explained
-----------------------

.. admonition:: 💡 Key Concept: What is Machine Learning?
   :class: tip

   **Machine learning (ML)** is teaching computers to find patterns in data
   and make predictions without being explicitly programmed with rules.

   **Traditional programming:**
     Human writes rules → computer follows rules

     .. code-block:: text

        IF memory_usage > 8GB THEN allocate 16GB
        IF memory_usage > 16GB THEN allocate 32GB

   **Machine learning:**
     Computer finds rules from data → uses them to predict

     .. code-block:: text

        Training data: [past runs with memory usage patterns]
        ML model learns: "scenarios with >1000 nodes need ~12GB"
        Prediction: "scenario 47 (1200 nodes) → recommend 16GB"

   **Analogy:** A traditional program is like a recipe (follow these steps).
   ML is like learning to cook from experience (after cooking 100 dishes,
   you develop intuition about seasoning, timing, etc.).

.. admonition:: 💡 Key Concept: Training vs. Inference
   :class: tip

   ML has two phases:

   **Training** (learning):
     Feed historical data to an algorithm. The algorithm adjusts its internal
     parameters to fit the patterns in the data.

     * Slow (minutes to hours)
     * Done once (or periodically when new data is available)
     * Requires labeled data (inputs + known correct outputs)

   **Inference** (predicting):
     Use the trained model to make predictions on new inputs.

     * Fast (milliseconds)
     * Done many times
     * Uses the patterns learned during training

   **In Scalable:**

   * **Training** = learning from telemetry history (past run metrics)
   * **Inference** = predicting resource needs for new runs

.. admonition:: 💡 Key Concept: Features
   :class: tip

   **Features** are the input variables that a model uses to make
   predictions. They're the characteristics of your data that the model
   "looks at."

   For Scalable's resource prediction:

   * Task name
   * Number of input data points
   * Historical average duration for this task type
   * Time of day
   * Target provider type

   **Feature engineering** is the process of choosing and transforming raw
   data into useful features. Good features → good predictions.

.. admonition:: 💡 Key Concept: What is a Model?
   :class: tip

   In ML, a **model** is a mathematical function learned from data. It maps
   inputs (features) to outputs (predictions):

   .. code-block:: text

      Model: features → prediction
      Example: [task="gridlabd", nodes=1200, history_avg=45s] → memory=12GB

   Think of a model as a function that was "written" by the training process
   rather than by a human programmer. The model doesn't understand what it's
   doing — it just captures statistical patterns in the training data.

   Common model types:

   * **Linear regression** — simple, interpretable, assumes linear relationships
   * **Decision tree** — series of if/then rules learned from data
   * **Random forest** — many decision trees that vote on the answer
   * **Gradient boosting** — trees that correct each other's mistakes

   Scalable uses gradient boosting and random forests — they work well for
   tabular data (like telemetry metrics) without much tuning.

.. admonition:: 💡 Key Concept: Surrogate Model / Emulator
   :class: tip

   A **surrogate model** (also called an **emulator**) is a fast
   approximation of an expensive computation.

   **Real-world analogy:**

   * Full model = weather simulation (supercomputer, hours of computation)
   * Surrogate = weather forecast model (quick approximation based on patterns)

   **In scientific computing:**

   * Full model: Run GridLAB-D simulation (5 minutes per scenario)
   * Surrogate: ML model trained on past GridLAB-D outputs (0.01 seconds)

   **When to use surrogates:**

   * Exploring parameter space (try 10,000 configurations quickly)
   * Preliminary analysis (get approximate results fast)
   * Optimization (surrogate guides search, full model validates)

   **When NOT to use surrogates:**

   * Final publication-quality results (use the full model)
   * Inputs far outside training range (surrogate may be unreliable)
   * When exact answers are required (surrogates are approximations)

.. admonition:: 💡 Key Concept: Uncertainty
   :class: tip

   **Uncertainty** quantifies how confident a model is in its prediction.

   .. code-block:: text

      Model prediction: memory = 12GB ± 3GB (68% confidence)

   This means:

   * Best estimate: 12GB
   * Likely range: 9–15GB
   * The model isn't perfectly certain

   **Why uncertainty matters:**

   * High confidence (tight range) → trust the prediction, use the surrogate
   * Low confidence (wide range) → don't trust it, use the full model instead

   Scalable uses uncertainty to make **routing decisions**: if the emulator
   is confident, use the fast approximation. If not, fall back to the
   expensive full computation.

.. admonition:: 💡 Key Concept: Active Learning
   :class: tip

   **Active learning** is a strategy where the model intelligently chooses
   which new data points to learn from (rather than passively waiting for
   random data).

   **Analogy:** Imagine studying for an exam. Active learning means focusing
   on topics you're weakest in (maximum learning benefit) rather than
   re-studying topics you already know well.

   **In Scalable:** The active learner identifies input scenarios where the
   emulator is most uncertain and requests full-model runs for those specific
   scenarios. This improves the emulator's accuracy with minimal expensive
   computation.

.. admonition:: 💡 Key Concept: Cross-Validation
   :class: tip

   **Cross-validation** tests model quality by repeatedly splitting data into
   training and testing sets:

   1. Split data into 5 parts (folds)
   2. Train on 4 parts, test on 1
   3. Repeat 5 times (each part is the test set once)
   4. Average the test scores

   This prevents **overfitting** — a model that memorizes the training data
   but fails on new data. Cross-validation estimates how well the model will
   perform on data it hasn't seen.


Step 1: The ResourceAdvisor (Baseline — No ML)
-------------------------------------------------

Before ML, Scalable provides a deterministic, rule-based advisor:

.. code-block:: python

   from scalable import ResourceAdvisor

   advisor = ResourceAdvisor.from_history("./.scalable/runs")
   recommendation = advisor.recommend(task="run_simulation")
   print(recommendation)
   # {'cpus': 4, 'memory': '16G', 'basis': 'p95 of 50 historical runs'}

This uses simple statistics (percentiles) — it works but doesn't learn
complex patterns.


Step 2: The LearnedAdvisor (ML-Powered)
------------------------------------------

The LearnedAdvisor uses machine learning on your telemetry history:

.. code-block:: python

   from scalable import LearnedAdvisor

   # Train on historical telemetry
   advisor = LearnedAdvisor.from_history(
       "./.scalable/runs",
       model_type="gradient_boosting",   # Algorithm choice
   )

   # Predict resources for a new run
   recommendation = advisor.recommend(
       task="run_simulation",
       input_features={"num_nodes": 1200, "scenario_type": "peak_demand"},
   )
   print(recommendation)
   # {'cpus': 2, 'memory': '8G', 'confidence': 0.87}

.. admonition:: What's happening here
   :class: note

   1. ``from_history()`` loads telemetry data from past runs
   2. It extracts features (task names, durations, resource usage)
   3. It trains a gradient boosting model to predict resource needs
   4. ``recommend()`` uses the trained model to predict for new inputs

   The ``confidence: 0.87`` means the model is 87% confident in this
   prediction. High confidence → the prediction is likely accurate.


Step 3: The AdaptiveScaler
----------------------------

The AdaptiveScaler uses ML predictions to decide scaling in real-time:

.. code-block:: python

   from scalable import AdaptiveScaler

   scaler = AdaptiveScaler(
       min_workers=2,
       max_workers=20,
       scale_up_threshold=0.8,    # Scale up when 80% busy
       scale_down_threshold=0.3,  # Scale down when 30% busy
       cooldown_seconds=60,       # Wait 60s between scaling decisions
   )

.. admonition:: How adaptive scaling works with ML
   :class: note

   Without ML: scale based on simple thresholds (queue depth > N → add workers)

   With ML: predict future load based on patterns. If the model predicts a
   burst of heavy tasks coming, scale up BEFORE the queue fills. This reduces
   latency because workers are already ready when tasks arrive.


Step 4: Model Emulation with @emulatable
-------------------------------------------

The ``@emulatable`` decorator marks functions that can be approximated:

.. code-block:: python

   from scalable import emulatable

   @emulatable(
       inputs={"scenario_id": int, "num_nodes": int},
       outputs={"demand_mwh": float, "peak_load": float},
       confidence_threshold=0.9,   # Only use emulator if 90%+ confident
   )
   def run_gridlabd(scenario_id: int, num_nodes: int) -> dict:
       """Full GridLAB-D simulation — takes 5 minutes."""
       # ... expensive computation ...
       return {"demand_mwh": result, "peak_load": peak}

.. admonition:: What the decorator does
   :class: note

   When you call ``run_gridlabd(42, 1200)``:

   1. Check: is there a trained emulator for this function?
   2. If yes: ask the emulator for a prediction + uncertainty estimate
   3. If confidence ≥ 0.9 (threshold): return the fast prediction (~0.01s)
   4. If confidence < 0.9: run the full function (5 minutes) and record
      the result for future training

   This is **confidence-gated routing** — the system automatically decides
   whether to use the fast path or slow path based on how trustworthy the
   approximation is.


Step 5: Training an Emulator
-------------------------------

.. code-block:: python

   from scalable import EmulatorRegistry

   # Create a registry (manages trained emulators)
   registry = EmulatorRegistry(path="./.scalable/emulators")

   # Train an emulator from historical results
   registry.train(
       function_name="run_gridlabd",
       training_data=historical_results,   # Past function outputs
       model_type="gradient_boosting",
   )

   # The emulator is now available for @emulatable routing
   emulator = registry.get("run_gridlabd")
   prediction = emulator.predict({"scenario_id": 42, "num_nodes": 1200})
   print(prediction)
   # {'demand_mwh': 4521.3, 'peak_load': 892.1, 'confidence': 0.94}

.. admonition:: Under the Hood: How emulators learn
   :class: hint

   1. **Collect training data:** Every time the full model runs, the
      input/output pair is recorded
   2. **Train the model:** A gradient boosting model learns the relationship
      between inputs (scenario_id, num_nodes) and outputs (demand_mwh,
      peak_load)
   3. **Estimate uncertainty:** The model also estimates how uncertain it is
      (using the spread across individual trees in the forest)
   4. **Deploy:** The trained emulator is saved and used for future calls


Step 6: Active Learning — Getting Smarter Over Time
------------------------------------------------------

.. code-block:: python

   from scalable import ActiveLearner

   learner = ActiveLearner(
       emulator=registry.get("run_gridlabd"),
       acquisition_strategy="maximum_uncertainty",
   )

   # Ask: which scenarios should I run the full model on?
   suggestions = learner.suggest(n=5, candidate_pool=all_scenarios)
   print(suggestions)
   # [scenario_47, scenario_892, scenario_13, ...]
   # These are the scenarios where the emulator is LEAST confident

.. admonition:: Why active learning is efficient
   :class: note

   Without active learning: run all 1000 scenarios with the full model
   (expensive!)

   With active learning:

   1. Run 100 scenarios with full model (training set)
   2. Train emulator
   3. Ask "where are you least confident?" → get 10 suggestions
   4. Run those 10 with full model
   5. Retrain emulator (now better!)
   6. Repeat until confidence is high everywhere

   Result: ~150 full model runs instead of 1000, with similar accuracy.


Step 7: Putting It All Together
---------------------------------

A workflow using ML optimization and emulation:

.. code-block:: python

   from scalable import (
       ScalableSession, LearnedAdvisor, EmulatorRegistry, emulatable
   )

   # 1. ML-informed resource allocation
   advisor = LearnedAdvisor.from_history("./.scalable/runs")
   recommendation = advisor.recommend(task="run_gridlabd")

   # 2. Emulation-capable function
   @emulatable(
       inputs={"scenario_id": int},
       outputs={"demand_mwh": float},
       confidence_threshold=0.9,
   )
   def run_gridlabd(scenario_id: int) -> dict:
       # Full simulation (expensive)
       ...

   # 3. Run with ML-optimized resources
   session = ScalableSession.from_yaml("./scalable.yaml", target="local")

   futures = [client.submit(run_gridlabd, i, tag="gridlabd")
              for i in range(100)]
   results = client.gather(futures)

   # Some calls used the emulator (fast), others ran the full model
   # Telemetry records which path each call took


Common Questions
-----------------

**Q: Do I need ML expertise to use these features?**

No. Scalable provides sensible defaults. You just need:

* Enough telemetry history (5+ runs for the advisor)
* The ``[ml]`` extra installed

The system handles model selection, training, and evaluation.

**Q: How much data do I need for the LearnedAdvisor?**

Rule of thumb:

* 5 runs → basic predictions (limited accuracy)
* 20+ runs → reliable predictions
* 100+ runs → high accuracy with confidence intervals

More data = better predictions. The system falls back to the rule-based
advisor when insufficient data exists.

**Q: Can the emulator give wrong answers?**

Yes! Emulators are approximations. That's why the confidence threshold exists.
At 0.9 confidence, the emulator is only used when it's very sure. For
critical results, always validate with the full model.

**Q: What if my function's behavior changes?**

Retrain the emulator with new data. The registry supports versioned emulators
so you can track changes over time. Active learning automatically identifies
where the emulator needs updating.

**Q: Is there overhead to checking the emulator?**

Negligible. Checking the emulator takes ~1ms. If your full function takes
seconds or minutes, the check is invisible. If it takes <10ms, don't bother
with emulation (the overhead isn't worth it).


What You Learned
-----------------

.. list-table::
   :header-rows: 1
   :widths: 30 70

   * - Term
     - Definition
   * - Machine Learning
     - Teaching computers to find patterns and make predictions from data
   * - Training
     - Learning phase where model adjusts to fit historical data
   * - Inference
     - Prediction phase using a trained model on new inputs
   * - Features
     - Input variables the model uses for predictions
   * - Model
     - Mathematical function learned from data (inputs → predictions)
   * - Surrogate/Emulator
     - Fast approximation of an expensive computation
   * - Uncertainty
     - Quantification of how confident a prediction is
   * - Confidence Threshold
     - Minimum confidence required to use the fast path
   * - Active Learning
     - Strategically choosing which data to learn from next
   * - Cross-Validation
     - Testing model quality by splitting data into train/test sets
   * - Gradient Boosting
     - ML algorithm using sequential corrective decision trees
   * - Confidence-Gated Routing
     - Using confidence to choose between emulator and full model


Next Steps
-----------

You now understand how ML enhances workflow optimization and model emulation.

* **Next beginner tutorial:** :ref:`beginner_ai_composition` — using AI
  assistants for workflow development
* **Standard tutorial:** :ref:`tutorial_ml_advanced` — advanced ML patterns,
  hyperparameter tuning, and emulator calibration
* **Try it:** Run your workflow 5+ times with different inputs. Then use
  ``LearnedAdvisor.from_history()`` to see what it recommends. Compare the
  ML recommendation to your current resource allocation.
