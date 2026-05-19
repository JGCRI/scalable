Scalable Example Workflow
=========================

This demo is presented as a sequence of small steps so you can follow and run
each stage independently.

The workflow demonstrates how Scalable coordinates a small integrated modeling
pipeline across multiple software environments. GCAM runs first to generate a
model database, a lightweight extraction step reads the needed time series from
that database, and Stitches uses the extracted trajectory to build gridded
climate outputs. Each stage is submitted as a normal Python function, but
Scalable decides which container profile should execute it and passes results
between stages as Dask futures.

Step 1: Imports and logging
---------------------------

The first step imports Scalable's public API and a few modules used by the
example functions. ``from scalable import *`` provides the cluster, client,
caching decorators, and type helpers used later in the workflow. ``os`` is used
inside worker functions for path handling, and ``gcam_config`` represents a
project-specific module that describes how GCAM configuration files should be
hashed for caching.

Logging is set to ``DEBUG`` so the example prints more information about worker
startup, task submission, container selection, and any errors that occur. During
development this is useful because HPC failures can otherwise appear as delayed
or silent worker timeouts.

.. code-block:: python

    from scalable import *

    import logging
    import os
    import gcam_config

    logging.basicConfig(level=logging.DEBUG)


Step 2: Create the cluster
--------------------------

The ``SlurmCluster`` object describes how Scalable should request resources from
the HPC scheduler. The ``queue``, ``walltime``, and ``account`` values map to the
same concepts you would normally provide in a Slurm batch script. This object
does not yet start model work; it records the scheduler settings that will be
used later when workers are added.

``silence_logs=False`` keeps worker and scheduler output visible. That is
helpful for a tutorial because it exposes what Scalable is doing behind the
scenes, including whether workers were accepted by Slurm and whether they
connected back to the Dask scheduler.

.. code-block:: python

    cluster = SlurmCluster(
        queue='short',
        walltime='02:00:00',
        account='GCIMS',
        silence_logs=False,
    )


Step 3: Register container profiles
-----------------------------------

Use one container profile per software environment. A container profile tells
Scalable which image target to use, how many CPUs and how much memory each
worker should reserve, and which host directories should be mounted inside the
container. Tags such as ``"gcam"`` and ``"stitches"`` become routing labels: when
a task is submitted with a matching tag, Scalable sends it to workers running
that environment.

Directory mappings are written as ``host_path: container_path``. Functions that
run inside the container should use the container paths, not the original host
paths. This keeps code consistent even if the host filesystem layout differs
between local setup and the HPC system.

.. code-block:: python

    # GCAM can use multiple threads, so this profile reserves 6 CPUs.
    cluster.add_container(
        tag="gcam",
        cpus=6,
        memory="20G",
        dirs={
            "/path/to/gcam-core/exe": "/gcam-core/exe",
            "/path/to/gcam-core/input": "/gcam-core/input",
            "/path/to/gcam-core/output": "/gcam-core/output",
            "/path/to/shared/data": "/data",
        },
    )

.. code-block:: python

    # Stitches is typically single-threaded in this workflow.
    cluster.add_container(
        tag="stitches",
        cpus=1,
        memory="50G",
        dirs={"/path/to/shared/data": "/data", "/path/to/archive/data": "/archive"},
    )

.. code-block:: python

    # Xanthos profile (not used below, shown as an additional profile example).
    cluster.add_container(
        tag="xanthos",
        cpus=1,
        memory="20G",
        dirs={
            "/path/to/shared/data": "/data",
            "/path/to/archive/data": "/archive",
            "/path/to/project/scratch": "/scratch",
        },
    )


Step 4: Define worker functions
-------------------------------

Define each function once, then submit them in dependency order. These functions
are normal Python functions, but they should import large or container-specific
dependencies inside the function body. Doing so ensures imports happen on the
worker inside the correct container rather than on the login node or client
process.

The ``@cacheable`` decorator marks expensive deterministic steps whose outputs
can be reused. When Scalable sees the same function inputs and compatible type
metadata, it can avoid repeating work and return the cached output instead. The
``return_type`` and custom type hints, such as ``config_file=gcam_config.GcamConfig``,
help Scalable hash non-trivial inputs and outputs reliably.

The first function runs GCAM for a requested model period and returns the path to
the generated database directory. ``get_worker().id`` is used in the database
name so concurrent GCAM workers do not overwrite one another's output.

.. code-block:: python

    @cacheable(return_type=DirType, config_file=gcam_config.GcamConfig)
    def run_gcam(config_file, period):
        import gcamwrapper as gw
        from dask.distributed import get_worker

        g = gw.Gcam(os.path.basename(config_file), "/gcam-core/exe")
        g.run_period(g.convert_year_to_period(period))
        dbname = "/gcam-core/output/" + get_worker().id + "database"
        return g.print_xmldb(dbname)

The database reader runs after GCAM completes. It receives the database path
returned by ``run_gcam``, opens it with ``gcamreader``, selects one query from a
batch-query XML file, and returns the query result as tabular data. Because the
input may be a future, Scalable waits for the upstream GCAM task before running
this function.

.. code-block:: python

    def readdb(db_path):
        import gcamreader
        import os

        conn = gcamreader.LocalDBConn(os.path.dirname(db_path), os.path.basename(db_path))
        query = gcamreader.parse_batch_query("/path/to/sample-queries.xml")[2]
        return conn.runQuery(query)

The interpolation helper converts sparse model-year output into an annual time
series. Stitches expects a continuous trajectory, so this helper fills the years
between GCAM time points with linearly interpolated values.

.. code-block:: python

    def interp(years, values):
        import numpy as np

        min_year = min(years)
        max_year = max(years)
        new_years = np.arange(min_year, max_year + 1)
        new_values = np.zeros(len(new_years))

        for index, year in enumerate(new_years):
            if np.isin(year, years):
                new_values[index] = values[year == years][0]
            else:
                less_year = max(years[year > years])
                more_year = min(years[year < years])
                less_value = values[np.where(less_year == years)[0][0]]
                more_value = values[np.where(more_year == years)[0][0]]
                p = (year - less_year) / (more_year - less_year)
                new_values[index] = p * more_value + (1 - p) * less_value

        return new_years, new_values

``stitch_prep`` transforms the GCAM query result into the target format expected
by Stitches. It loads a matching archive, selects candidate climate-model data,
interpolates the GCAM trajectory, normalizes the values relative to the
1975--2014 baseline, and builds a Stitches recipe describing which archive
segments should be combined to match the target trajectory.

This function is also cacheable because recipe generation can be expensive and
is deterministic for the same input data and archive. If the GCAM output has not
changed, rerunning the workflow can skip this preparation step.

.. code-block:: python

    @cacheable
    def stitch_prep(df):
        import numpy as np
        import pandas as pd
        import pkg_resources
        import stitches

        path = pkg_resources.resource_filename('stitches', 'data/matching_archive_staggered.csv')
        data = pd.read_csv(path)
        end_yr_vector = np.arange(2100, 1800, -9)
        data = stitches.fx_processing.subset_archive(
            staggered_archive=data,
            end_yr_vector=end_yr_vector,
        )
        model_data = data[(data["model"] == "CanESM5") & (data["experiment"].str.contains('ssp585'))]

        years, values = interp(np.array(df["Year"]), np.array(df["value"]))
        df = pd.DataFrame({"year": years, "value": values})
        df['variable'] = 'tas'
        df['model'] = ''
        df['ensemble'] = ''
        df['experiment'] = 'GCAM7-Ref'
        df['unit'] = 'degC change from avg over 1975~2014'
        df.value = df.value - np.mean(df.value[(df.year <= 2014) & (df.year >= 1975)])
        df = df[['variable', 'experiment', 'ensemble', 'model', 'year', 'value', 'unit']]

        target_chunk = stitches.fx_processing.chunk_ts(df, n=9)
        target_data = stitches.fx_processing.get_chunk_info(target_chunk)

        stitches_recipe = None
        for _ in range(10):
            stitches_recipe = stitches.make_recipe(
                target_data,
                model_data,
                tol=0.0,
                N_matches=1,
                res='day',
                non_tas_variables=['tasmin', 'pr', 'hurs', 'sfcWind', 'rsds', 'rlds'],
            )

        last_period_length = (
            stitches_recipe['target_end_yr'].values[-1] - stitches_recipe['target_start_yr'].values[-1]
        )
        asy = stitches_recipe['archive_start_yr'].values
        asy[-1] = stitches_recipe['archive_end_yr'].values[-1] - last_period_length
        stitches_recipe['archive_start_yr'] = asy.copy()
        return stitches_recipe

``run_stitches`` consumes the recipe and writes gridded stitched outputs to the
requested output directory. The function sets Dask's internal scheduler to
``"synchronous"`` while calling Stitches because Stitches may create its own Dask
work internally. Keeping that work local to the selected worker avoids common
pickling and cross-environment issues when the broader Scalable cluster contains
workers with different containers.

.. code-block:: python

    @cacheable
    def run_stitches(recipe, output_path):
        import dask
        import stitches

        # Synchronous mode avoids common pickling issues in mixed environments.
        with dask.config.set(scheduler="synchronous"):
            return stitches.gridded_stitching(output_path, recipe)


Step 5: Start initial workers and client
----------------------------------------

This step starts only the workers needed for the first stage of the workflow:
two GCAM workers. Starting a small number of workers up front keeps the resource
request focused on the immediate work instead of reserving every possible
container at once.

The ``ScalableClient`` connects to the cluster and is used for all subsequent
task submission, dependency tracking, and result retrieval. It behaves like a
Dask client with additional Scalable routing options such as ``tag`` and ``n``.

.. code-block:: python

    cluster.add_workers(n=2, tag="gcam")
    sc_client = ScalableClient(cluster)


Step 6: Submit GCAM and database extraction tasks
-------------------------------------------------

The first submitted task runs GCAM in the ``"gcam"`` container. The ``n=1`` value
means the task needs one worker slot, while ``tag="gcam"`` restricts execution
to workers created from the GCAM profile. The call returns immediately with a
future instead of blocking until GCAM finishes.

The second task uses ``future1`` as its input. Passing futures directly is how
the workflow graph is constructed: Scalable knows ``readdb`` depends on
``run_gcam`` and will not execute the database query until GCAM has produced its
database path. This allows you to describe the pipeline without manually polling
for completion.

.. code-block:: python

    future1 = sc_client.submit(
        run_gcam,
        "/path/to/gcam-core/exe/configuration_ref.xml",
        2100,
        n=1,
        tag="gcam",
    )

.. code-block:: python

    future2 = sc_client.submit(readdb, future1, n=1, tag="gcam")


Step 7: Add stitches worker and prepare stitching inputs
--------------------------------------------------------

After the GCAM extraction stage is in the graph, the workflow adds a worker for
the ``"stitches"`` profile. This demonstrates dynamic scaling: the Stitches
environment is started only when the workflow is about to need it.

``stitch_prep`` is submitted to the Stitches worker and depends on ``future2``.
Once the database extraction returns tabular data, this task converts that data
into a Stitches recipe. The task runs in the Stitches container because the
function imports and calls the Stitches package.

.. code-block:: python

    cluster.add_workers(n=1, tag="stitches")
    future3 = sc_client.submit(stitch_prep, future2, n=1, tag="stitches")


Step 8: Scale down unused GCAM workers
--------------------------------------

Only remove workers after downstream tasks no longer depend on them. At this
point, the GCAM run and database extraction have already been submitted, and the
remaining work is handled by the Stitches profile. Removing the GCAM workers
frees scheduler resources and reduces the chance of idle workers occupying an
allocation that another job could use.

In a production workflow, remove workers only after you are confident no queued
or future downstream work needs that container. If later tasks still need GCAM
libraries or files that are only available in the GCAM environment, keep those
workers alive until those tasks are submitted and completed.

.. code-block:: python

    cluster.remove_workers(n=2, tag="gcam")


Step 9: Run stitches and fetch final output
-------------------------------------------

The final computational task passes the Stitches recipe future into
``run_stitches``. As with earlier steps, using a future as an argument creates a
dependency edge: Stitches will not start until recipe preparation finishes. The
output path is a container-visible directory where Stitches should write final
products.

``future4.result()`` blocks the client process until the final task completes,
then returns the value produced by ``run_stitches``. In small examples printing
the result is convenient; in a larger workflow you might gather multiple futures,
write a manifest, or submit additional post-processing tasks instead.

.. code-block:: python

    future4 = sc_client.submit(
        run_stitches,
        future3,
        '/path/to/output/directory/',
        n=1,
        tag='stitches',
    )

.. code-block:: python

    print(future4.result())


Step 10: Close the cluster
--------------------------

Closing the cluster shuts down the Dask client, scheduler, and any remaining
workers. This cleanup step is important on shared HPC systems because it releases
Slurm allocations and prevents orphaned worker jobs from continuing to consume
resources after the workflow has finished.

.. code-block:: python

    cluster.close()


This demo shows a complete multi-stage workflow where each stage runs in the
appropriate container profile and passes futures to downstream steps. If you run
into issues, open one at
`https://github.com/JGCRI/scalable/issues <https://github.com/JGCRI/scalable/issues>`_.
