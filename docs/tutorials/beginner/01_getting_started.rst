.. _beginner_getting_started:

======================================================
Beginner Tutorial 1: Your First Workflow
======================================================

.. contents:: In This Tutorial
   :local:
   :depth: 2

The Big Picture
----------------

Imagine you have a Python script that processes data — maybe it analyzes
energy scenarios, runs simulations, or trains models. When the data grows,
running everything on your laptop becomes painfully slow. You need a way to
split the work across multiple processors (or multiple computers) without
rewriting your entire program.

**That's what Scalable does.** It takes your Python functions and orchestrates
them across multiple workers — whether those workers are threads on your laptop,
processes on an HPC cluster, or containers in the cloud. And it does this
through a simple configuration file rather than requiring you to write complex
parallel programming code.

This tutorial walks you through your very first Scalable workflow, explaining
every concept along the way.

.. admonition:: 💡 Key Concept: What is a Workflow?
   :class: tip

   A **workflow** is a sequence of computational steps that transforms inputs
   into outputs. Think of it like a recipe: you have ingredients (data), steps
   (functions), and a final dish (results).

   In Scalable, a workflow consists of:

   1. A **manifest** (configuration file) describing what resources you need
   2. Python **functions** that do the actual work
   3. A **target** (where the work runs — your laptop, a cluster, the cloud)

What You Will Learn
--------------------

By the end of this tutorial you will:

* Understand what Scalable is and why it exists.
* Know what Dask is and why Scalable uses it under the hood.
* Create and activate a Python virtual environment.
* Install Scalable and use its command-line interface (CLI).
* Write your first manifest file (``scalable.yaml``).
* Validate, plan, and run a workflow end-to-end.
* Read the telemetry output to see what happened.

Prerequisites
--------------

* **Python 3.11 or later** installed on your computer.
* A **terminal** (Terminal on macOS/Linux, PowerShell or Command Prompt on
  Windows).
* **Basic Python knowledge**: you can write functions, use ``import``, and know
  what ``pip`` is (even if you don't use it daily).

No HPC cluster, Docker, or cloud account is needed — everything runs locally.


Key Concepts Explained
-----------------------

Before we write any code, let's define the foundational ideas you'll encounter.

.. admonition:: 💡 Key Concept: Distributed Computing
   :class: tip

   **Distributed computing** means splitting work across multiple processors
   or computers that work together. Instead of one CPU doing all 1000 tasks
   sequentially (one after another), you might have 10 CPUs each handling 100
   tasks simultaneously.

   **Analogy:** Imagine stuffing 1000 envelopes. Doing it alone takes hours.
   With 10 friends helping, each person stuffs 100 envelopes and you finish
   10× faster. Distributed computing is getting those friends organized.

.. admonition:: 💡 Key Concept: What is Dask?
   :class: tip

   **Dask** is a Python library for parallel and distributed computing. It's
   the "engine" that Scalable uses under the hood to actually run your
   functions on multiple workers.

   Think of Dask as the engine in a car — you don't need to understand every
   piston to drive, but knowing it's there helps you understand what's
   happening.

   **Why Dask?** Scalable chose Dask because it:

   * Integrates natively with Python's scientific ecosystem (NumPy, pandas)
   * Scales from a single laptop to thousands of nodes
   * Has a mature scheduler that handles task dependencies
   * Supports dynamic scaling (adding/removing workers at runtime)
   * Is widely adopted in the scientific computing community

   Alternatives like **Ray** (more ML-focused) or **Celery** (more
   web-focused) exist, but Dask's strength is scientific workflows — exactly
   what Scalable targets.

.. admonition:: 💡 Key Concept: Command-Line Interface (CLI)
   :class: tip

   A **CLI** is a text-based way to interact with a program. Instead of
   clicking buttons in a graphical interface, you type commands like
   ``scalable run ./scalable.yaml``.

   CLIs are preferred for:

   * **Automation** — easy to script and repeat
   * **Remote work** — works over SSH where GUIs don't
   * **Reproducibility** — commands can be saved and re-run exactly

.. admonition:: 💡 Key Concept: Virtual Environment
   :class: tip

   A **virtual environment** is an isolated Python installation. It has its
   own copy of ``pip`` and installed packages, separate from your system
   Python.

   **Why bother?** Without virtual environments, installing a package for
   Project A might break Project B (if they need different versions of the
   same library). Virtual environments keep projects isolated.

   **Analogy:** Virtual environments are like separate kitchen pantries for
   each recipe — what you put in one doesn't affect the others.


Step 1: Set Up Your Environment
---------------------------------

Let's create an isolated Python environment for this tutorial.

**Open your terminal** and run:

.. code-block:: bash

   # Create a new virtual environment named ".venv"
   python -m venv .venv

   # Activate it (this changes your terminal's Python to use the isolated one)
   source .venv/bin/activate   # macOS/Linux
   # On Windows: .venv\Scripts\activate

.. admonition:: What just happened?
   :class: note

   ``python -m venv .venv`` created a folder called ``.venv`` containing a
   fresh Python installation. ``source .venv/bin/activate`` tells your terminal
   "use this Python instead of the system one." You'll see your prompt change
   (often showing ``(.venv)`` at the beginning).

Now install Scalable:

.. code-block:: bash

   pip install scalable

Verify it worked:

.. code-block:: bash

   scalable --help

You should see output like:

.. code-block:: text

   usage: scalable [-h] {validate,plan,run,report,advise,...} ...

   Scalable CLI — orchestrate distributed workflows.

   positional arguments:
     {validate,plan,run,report,advise,...}

.. admonition:: Under the Hood
   :class: hint

   When you ran ``pip install scalable``, Python downloaded Scalable and all
   its dependencies (including Dask). The ``scalable`` command is a CLI entry
   point — a small script that Python created in your virtual environment's
   ``bin/`` directory that launches Scalable's command handler.


Step 2: Create a Project Directory
------------------------------------

Scalable expects your workflow to live in a dedicated directory:

.. code-block:: bash

   mkdir my-first-workflow && cd my-first-workflow

The minimal layout is:

.. code-block:: text

   my-first-workflow/
   ├── scalable.yaml       # The manifest (configuration)
   └── workflow.py          # Your Python code

.. admonition:: 💡 Key Concept: Project Structure
   :class: tip

   Keeping configuration (``scalable.yaml``) and code (``workflow.py``) in a
   dedicated directory makes your workflow:

   * **Portable** — zip it up and it works elsewhere
   * **Version-controllable** — put it in Git
   * **Self-documenting** — everything needed is in one place


Step 3: Write Your First Manifest
-----------------------------------

.. admonition:: 💡 Key Concept: What is a Manifest?
   :class: tip

   A **manifest** is a configuration file that declares the desired state of
   your system. In Scalable, the manifest (``scalable.yaml``) answers:

   * **What** is this project?
   * **Where** should it run? (local machine? cloud? HPC cluster?)
   * **How much** resources does each piece need? (CPU, memory)
   * **What** are the work units?

   The manifest is **declarative** — more on this below.

.. admonition:: 💡 Key Concept: Declarative vs. Imperative Programming
   :class: tip

   This is a fundamental programming paradigm distinction:

   **Imperative** (how to do it):
     "SSH into server. Run this command. Check the output. If it failed,
     retry. Allocate 4GB of RAM by calling this API..."

   **Declarative** (what you want):
     "I need 2 workers with 1 CPU and 1GB RAM each."

   The manifest is declarative — you describe your desired state and Scalable
   figures out how to achieve it. This is the same philosophy behind:

   * SQL (``SELECT name FROM users`` — you say what data, not how to fetch it)
   * HTML (``<h1>Title</h1>`` — you say what it is, not how to render it)
   * Kubernetes YAML (you describe desired state, K8s makes it happen)

   **Why declarative?** It separates *intent* from *implementation*. Your
   manifest works whether you're running locally, on an HPC cluster, or in
   AWS — only the "target" section changes.

Create the file ``scalable.yaml``:

.. code-block:: yaml

   # scalable.yaml — Your first Scalable manifest
   version: 1
   project:
     name: hello-scalable

   targets:
     local:
       provider: local
       max_workers: 2
       threads_per_worker: 1
       processes: false
       containers: none

   components:
     analysis:
       cpus: 1
       memory: 1G

   tasks:
     run_analysis:
       component: analysis

Let's break this down **line by line**:

.. admonition:: 💡 Key Concept: YAML
   :class: tip

   **YAML** (YAML Ain't Markup Language) is a human-readable data format.
   It uses indentation (spaces, not tabs!) to show structure:

   .. code-block:: yaml

      # This is a comment
      key: value              # A simple key-value pair
      nested:
        child_key: child_val  # Indented = nested inside "nested"
      list:
        - item1               # Lists use dashes
        - item2

   YAML was chosen over JSON (harder to read/write by hand) and TOML (less
   expressive for nested structures).

**Section-by-section explanation:**

``version: 1``
   The schema version. This tells Scalable which format rules to apply when
   reading your manifest. Currently ``1`` is the only version.

``project: { name: hello-scalable }``
   Metadata about your project. The ``name`` appears in logs, telemetry data,
   and artifact paths so you can identify which project a run belongs to.

``targets:``
   Targets are **where** your code runs. You can have multiple targets (local,
   HPC, cloud) in one manifest and switch between them. Here we define one
   target called ``local``:

   * ``provider: local`` — Use the built-in local provider (runs on your machine)
   * ``max_workers: 2`` — Create up to 2 workers (parallel executors)
   * ``threads_per_worker: 1`` — Each worker uses 1 thread
   * ``processes: false`` — Workers run as threads (not separate processes)
   * ``containers: none`` — No containerization (bare metal)

``components:``
   Components define **resource profiles** — how much CPU and memory a piece
   of work needs. The ``analysis`` component requests 1 CPU and 1 gigabyte of
   RAM.

``tasks:``
   Tasks are **named work units** that bind to a component. When you submit a
   function to Scalable, you associate it with a task name, which tells the
   system what resources it needs.

.. admonition:: Why separate targets, components, and tasks?
   :class: hint

   This separation follows the **separation of concerns** principle:

   * **Targets** = where (infrastructure)
   * **Components** = how much (resources)
   * **Tasks** = what (work units)

   You can change where you run (swap the target) without changing what you
   run (tasks and components stay the same). This is what makes Scalable
   truly portable.


Step 4: Validate Your Manifest
-------------------------------

Before running anything, check that your manifest is correctly written:

.. code-block:: bash

   scalable validate ./scalable.yaml

Expected output:

.. code-block:: text

   ✓ Manifest is valid (0 errors, 0 warnings)

.. admonition:: 💡 Key Concept: Validation
   :class: tip

   **Validation** means checking that something meets expected rules before
   using it. It's like spell-check for your configuration.

   Scalable's validator checks:

   * Required sections exist (``version``, ``project``)
   * Key names are spelled correctly (catches typos like ``providr``)
   * References are valid (a task's ``component`` actually exists)
   * Values are the right type (``max_workers`` must be a positive number)

   **Why validate first?** It's much faster and cheaper to catch errors in a
   config file than to discover them 30 minutes into a cloud run that's
   costing you money.

Try introducing a deliberate error to see what happens:

.. code-block:: yaml

   # Change "provider" to "providr" (typo) and validate again
   targets:
     local:
       providr: local   # <-- typo!

.. code-block:: text

   ERROR targets.local: unknown provider 'providr'


Step 5: Plan the Execution
----------------------------

Planning shows you what **would** happen without actually doing it:

.. code-block:: bash

   scalable plan ./scalable.yaml --target local --dry-run

.. code-block:: text

   Plan created for target 'local' (provider: local)
   Workers: 2 × analysis (1 cpu, 1G memory)
   Manifest lock: sha256:a3b8f1...

.. admonition:: 💡 Key Concept: Dry Run
   :class: tip

   A **dry run** simulates an operation without executing it. It answers
   "what would happen if I ran this?" without consuming real resources.

   This is valuable because:

   * You can verify your configuration before spending time/money
   * You can review the plan and catch mistakes
   * In cloud environments, you can see estimated costs before committing

   The ``--dry-run`` flag is common across many tools (``terraform plan``,
   ``kubectl --dry-run``, ``rsync --dry-run``).

.. admonition:: 💡 Key Concept: Manifest Lock (Hash)
   :class: tip

   The ``sha256:a3b8f1...`` is a **hash** — a fingerprint of your manifest's
   contents. If you change anything in the manifest, the hash changes. This
   enables:

   * **Reproducibility** — you can verify that a run used the exact same
     configuration as a previous run
   * **Caching** — Scalable knows if the manifest changed since last run


Step 6: Write Your Workflow Code
---------------------------------

Now let's write the Python function that does actual work. Create
``workflow.py``:

.. code-block:: python

   """My first Scalable workflow."""
   import time
   from scalable import ScalableSession


   def analyze_scenario(scenario_id: int) -> dict:
       """Simulate an analysis task.

       In a real workflow this might run an energy model, process
       satellite data, or train a machine learning model. Here we
       just simulate work with a sleep.
       """
       time.sleep(0.5)  # Simulate 0.5 seconds of computation
       return {
           "scenario_id": scenario_id,
           "result": scenario_id * 42,
           "status": "complete",
       }


   def main():
       """Run the workflow using a ScalableSession."""
       # Create a session from our manifest
       session = ScalableSession.from_yaml(
           "./scalable.yaml",
           target="local",
       )
       plan = session.plan()
       client = session.start(plan)

       # Submit 6 tasks to be executed in parallel
       futures = []
       for i in range(6):
           future = client.submit(analyze_scenario, i, tag="analysis")
           futures.append(future)

       # Gather results (blocks until all tasks complete)
       results = client.gather(futures)

       print(f"Completed {len(results)} scenarios!")
       for r in results:
           print(f"  Scenario {r['scenario_id']}: result = {r['result']}")

       # Clean up
       session.close()


   if __name__ == "__main__":
       main()

Let's understand what this code does:

.. admonition:: Under the Hood: What happens when you call ``client.submit()``
   :class: hint

   1. Your function (``analyze_scenario``) and its arguments (``scenario_id``)
      are **serialized** (converted to bytes that can be sent over a network).
   2. The serialized task is sent to Dask's **scheduler**.
   3. The scheduler finds an available **worker** and assigns the task.
   4. The worker **deserializes** the function, executes it, and sends the
      result back.
   5. You get a **future** — a placeholder for the result that will be
      available later.

   With ``max_workers: 2``, Scalable runs 2 tasks at a time. Since we
   submitted 6 tasks, they execute in 3 batches of 2 (total ~1.5 seconds
   instead of 3 seconds sequentially).

.. admonition:: 💡 Key Concept: Futures
   :class: tip

   A **future** is a promise of a result that hasn't been computed yet. When
   you call ``client.submit()``, the task starts running in the background
   and you immediately get back a future object.

   Later, when you call ``client.gather(futures)``, Python waits until all
   the futures have their results ready, then returns them.

   **Analogy:** Ordering food at a counter — you get a receipt number (future)
   immediately. The food is being prepared in the background. When you hear
   your number called, you pick up your food (gather the result).


Step 7: Run the Workflow
--------------------------

Execute your workflow:

.. code-block:: bash

   python workflow.py

Expected output:

.. code-block:: text

   Completed 6 scenarios!
     Scenario 0: result = 0
     Scenario 1: result = 42
     Scenario 2: result = 84
     Scenario 3: result = 126
     Scenario 4: result = 168
     Scenario 5: result = 210

You can also run workflows via the CLI (for manifests that define entry
points), but the Python API gives you the most control.

.. admonition:: 🤔 Think About It
   :class: note

   With 6 tasks and 2 workers, how long should this take?

   * Sequential (no parallelism): 6 × 0.5s = 3.0 seconds
   * Parallel with 2 workers: 3 batches × 0.5s = ~1.5 seconds

   The speedup is approximately 2× with 2 workers. This is the fundamental
   value of distributed computing — trading more hardware for less time.


Step 8: Inspect Telemetry
---------------------------

.. admonition:: 💡 Key Concept: Telemetry
   :class: tip

   **Telemetry** is automated data collection about what happened during
   execution. Think of it like a flight recorder (black box) for your
   workflow — it records events so you can understand what happened after
   the fact.

After your run completes, Scalable has recorded telemetry data. Generate a
report:

.. code-block:: bash

   scalable report --last

This shows a summary of your most recent run: how many tasks succeeded, how
long they took, and resource utilization.


Common Questions
-----------------

**Q: Do I always need a manifest file?**

Yes — the manifest is the single source of truth for your workflow's resource
requirements. This is by design: it makes workflows reproducible and portable.

**Q: Why not just use Python's ``multiprocessing`` module?**

Python's ``multiprocessing`` works for simple parallelism on one machine. But
it can't:

* Scale to multiple machines (HPC clusters, cloud)
* Manage heterogeneous resources (different CPU/memory per task type)
* Cache results between runs
* Provide telemetry and observability
* Handle worker failures gracefully

Scalable (via Dask) provides all of these.

**Q: What's the difference between threads and processes?**

* **Threads** share memory (fast communication, but Python's GIL limits
  true CPU parallelism).
* **Processes** have separate memory (true parallelism, but higher overhead
  to start and communicate).

For I/O-bound work (network calls, file reading), threads work well. For
CPU-bound work (heavy math), processes are better. The ``processes: false``
setting in our manifest uses threads for simplicity.

**Q: What is the GIL?**

The **Global Interpreter Lock** (GIL) is a Python implementation detail that
prevents multiple threads from executing Python code simultaneously. It
exists for memory safety but means CPU-bound threads don't truly run in
parallel. This is why ``processes: true`` is better for computation-heavy
tasks.


What You Learned
-----------------

.. list-table::
   :header-rows: 1
   :widths: 30 70

   * - Term
     - Definition
   * - Workflow
     - A sequence of computational steps transforming inputs to outputs
   * - Distributed Computing
     - Splitting work across multiple processors/computers
   * - Dask
     - Python library for parallel computing (Scalable's engine)
   * - CLI
     - Text-based interface for running commands
   * - Virtual Environment
     - Isolated Python installation for dependency management
   * - Manifest
     - Declarative configuration file describing desired state
   * - Declarative Programming
     - Describing *what* you want, not *how* to achieve it
   * - Provider
     - Abstraction over an execution backend (local, HPC, cloud)
   * - Worker
     - A process/thread that executes tasks
   * - Future
     - A placeholder for a result being computed asynchronously
   * - Validation
     - Checking correctness before execution
   * - Dry Run
     - Simulating an operation without executing it
   * - Telemetry
     - Automated recording of execution data


Next Steps
-----------

You've run your first Scalable workflow! You now understand the fundamental
concepts that everything else builds on.

* **Next beginner tutorial:** :ref:`beginner_manifest_system` — deep dive
  into declarative configuration and YAML
* **Standard tutorial:** :ref:`tutorial_getting_started` — same topic with
  less explanation, more advanced patterns
* **Try modifying:** Change ``max_workers`` to 4 and re-run. Is it faster?
  Why or why not? (Hint: you only have 6 tasks.)
