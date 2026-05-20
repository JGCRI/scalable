How to Contribute
=================

Contributions are welcome and appreciated. This page outlines practical ways to
contribute and the expected pull request workflow.

Ways to contribute
------------------

You can help by:

* Reporting bugs and usability issues.
* Proposing features or architecture improvements.
* Improving documentation clarity, examples, and cross-links.
* Submitting code fixes or enhancements with tests.

Development Setup
-----------------

Before contributing code, set up a local development environment using a virtual
environment and an editable install:

.. code-block:: bash

    # Fork & clone your fork
    git clone https://github.com/<your-username>/scalable.git
    cd scalable

    # Create and activate a virtual environment
    python -m venv .venv
    source .venv/bin/activate   # Linux / macOS
    # .venv\Scripts\activate    # Windows

    # Install in editable mode with dev dependencies
    pip install -e ".[dev]"

The ``-e`` (editable) flag means your local source changes are picked up
immediately — no need to reinstall after every edit.

To verify everything is working:

.. code-block:: bash

    pytest                   # run the test suite
    ruff check scalable/     # lint
    mypy scalable/           # type-check (optional)

.. note::

   Always work inside the activated virtual environment.  If you open a new
   terminal, re-activate with ``source .venv/bin/activate``.

Contribution workflow
---------------------

#. Fork the repository and create a focused branch.
#. Set up the development environment as described above.
#. Make changes in small, reviewable commits.
#. Run tests locally (``pytest``) before opening a pull request.
#. Update documentation and examples when behavior changes.
#. Open a pull request describing the problem, approach, and validation steps.

Issue tracker
-------------

Open issues and feature requests at:

`https://github.com/JGCRI/scalable/issues <https://github.com/JGCRI/scalable/issues>`_
