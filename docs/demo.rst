Scalable Example Workflow
=========================

This demo is presented as a sequence of small steps so you can follow and run
each stage independently.

Step 1: Imports and logging
---------------------------

.. code-block:: python

    from scalable import *

    import logging
    import os
    import gcam_config

    logging.basicConfig(level=logging.DEBUG)


Step 2: Create the cluster
--------------------------

.. code-block:: python

    cluster = SlurmCluster(
        queue='short',
        walltime='02:00:00',
        account='GCIMS',
        silence_logs=False,
    )


Step 3: Register container profiles
-----------------------------------

Use one container profile per software environment.

.. code-block:: python

    # GCAM can use multiple threads, so this profile reserves 6 CPUs.
    cluster.add_container(
        tag="gcam",
        cpus=6,
        memory="20G",
        dirs={
            "/qfs/people/lamb678/work/gcam-core/exe": "/gcam-core/exe",
            "/qfs/people/lamb678/work/gcam-core/input": "/gcam-core/input",
            "/qfs/people/lamb678/work/gcam-core/output": "/gcam-core/output",
            "/qfs": "/qfs",
        },
    )

.. code-block:: python

    # Stitches is typically single-threaded in this workflow.
    cluster.add_container(
        tag="stitches",
        cpus=1,
        memory="50G",
        dirs={"/qfs": "/qfs", "/rcfs": "/rcfs"},
    )

.. code-block:: python

    # Xanthos profile (not used below, shown as an additional profile example).
    cluster.add_container(
        tag="xanthos",
        cpus=1,
        memory="20G",
        dirs={
            "/qfs": "/qfs",
            "/rcfs": "/rcfs",
            "/rcfs/projects/gcims/projects/scalable/": "/scratch",
        },
    )


Step 4: Define worker functions
-------------------------------

Define each function once, then submit them in dependency order.

.. code-block:: python

    @cacheable(return_type=DirType, config_file=gcam_config.GcamConfig)
    def run_gcam(config_file, period):
        import gcamwrapper as gw
        from dask.distributed import get_worker

        g = gw.Gcam(os.path.basename(config_file), "/gcam-core/exe")
        g.run_period(g.convert_year_to_period(period))
        dbname = "/gcam-core/output/" + get_worker().id + "database"
        return g.print_xmldb(dbname)

.. code-block:: python

    def readdb(db_path):
        import gcamreader
        import os

        conn = gcamreader.LocalDBConn(os.path.dirname(db_path), os.path.basename(db_path))
        query = gcamreader.parse_batch_query("/qfs/people/lamb678/sample-queries.xml")[2]
        return conn.runQuery(query)

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

.. code-block:: python

    cluster.add_workers(n=2, tag="gcam")
    sc_client = ScalableClient(cluster)


Step 6: Submit GCAM and database extraction tasks
-------------------------------------------------

.. code-block:: python

    future1 = sc_client.submit(
        run_gcam,
        "/qfs/people/lamb678/work/gcam-core/exe/configuration_ref.xml",
        2100,
        n=1,
        tag="gcam",
    )

.. code-block:: python

    future2 = sc_client.submit(readdb, future1, n=1, tag="gcam")


Step 7: Add stitches worker and prepare stitching inputs
--------------------------------------------------------

.. code-block:: python

    cluster.add_workers(n=1, tag="stitches")
    future3 = sc_client.submit(stitch_prep, future2, n=1, tag="stitches")


Step 8: Scale down unused GCAM workers
--------------------------------------

Only remove workers after downstream tasks no longer depend on them.

.. code-block:: python

    cluster.remove_workers(n=2, tag="gcam")


Step 9: Run stitches and fetch final output
-------------------------------------------

.. code-block:: python

    future4 = sc_client.submit(
        run_stitches,
        future3,
        '/rcfs/projects/gcims/projects/scalable/',
        n=1,
        tag='stitches',
    )

.. code-block:: python

    print(future4.result())


Step 10: Close the cluster
--------------------------

.. code-block:: python

    cluster.close()


This demo shows a complete multi-stage workflow where each stage runs in the
appropriate container profile and passes futures to downstream steps. If you run
into issues, open one at
`https://github.com/JGCRI/scalable/issues <https://github.com/JGCRI/scalable/issues>`_.
