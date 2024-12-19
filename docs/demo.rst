Scalable Example Workflow
=========================

This is a simple example workflow that demonstrates how the Scalable package can
be useful for running complex experiments and analysis. 

.. code-block:: python

    from scalable import *

    import os
    import logging
    import gcam_config



    ## Enabling debug level logging for the demo
    logging.basicConfig(level=logging.DEBUG)


    ## Creating a SlurmCluster object with the required parameters
    cluster = SlurmCluster(queue='short', walltime='02:00:00', account='GCIMS', silence_logs=False)



    ## Adding containers to the cluster
    cluster.add_container(tag="gcam", cpus=6, memory="20G", dirs={"/qfs/people/lamb678/work/gcam-core/exe":"/gcam-core/exe", 
                                                                "/qfs/people/lamb678/work/gcam-core/input":"/gcam-core/input", 
                                                                "/qfs/people/lamb678/work/gcam-core/output":"/gcam-core/output", 
                                                                "/qfs":"/qfs"})

    cluster.add_container(tag="stitches", cpus=6, memory="50G", dirs={"/qfs":"/qfs", "/rcfs":"/rcfs"})

    cluster.add_container(tag="xanthos", cpus=6, memory="20G", dirs={"/qfs":"/qfs", "/rcfs":"/rcfs", 
                                                                    "/rcfs/projects/gcims/projects/scalable/":"/scratch"})


    ## Adding functions which will be executed on the workers

    ## This function will be executed in a gcam worker and so a gcam container.
    ## The import statements inside will only be valid on the gcam workers and
    ## will throw an error on other workers. 

    ## Cacheable decorator is used to cache the output of the function. The 
    ## return value of the function is the name of the output directory so the 
    ## return_type is set to DirType. The config_file parameter's data type is
    ## set to gcam_config.GcamConfig as that's the type that can most effectively
    ## hash the config file path.
    @cacheable(return_type=DirType, config_file=gcam_config.GcamConfig)
    def run_gcam(config_file, period):
        import gcamwrapper as gw
        from dask.distributed import get_worker
        g = gw.Gcam(os.path.basename(config_file), "/gcam-core/exe")
        g.run_period(g.convert_year_to_period(period))
        dbname = "/gcam-core/output/" + get_worker().id + "database"
        pth = g.print_xmldb(dbname)
        return pth


    ## This function will extract the data from the gcam database output depending
    ## on saved queries.
    def readdb(db_path):
        import gcamreader
        import os
        coon = gcamreader.LocalDBConn(os.path.dirname(db_path), os.path.basename(db_path))
        query = gcamreader.parse_batch_query("/qfs/people/lamb678/sample-queries.xml")[2]
        res = coon.runQuery(query)
        return res

    def interp(years, values):
        import numpy as np
        min_year = min(years)
        max_year = max(years)
        new_years = np.arange(min_year, max_year+1)
        new_values = np.zeros(len(new_years))
        for index, year in enumerate(new_years):
            if np.isin(year, years):
                new_values[index] = values[year == years][0]
            else:
                less_year = max(years[year > years])
                more_year = min(years[year < years])
                less_value = values[np.where(less_year == years)[0][0]]
                more_value = values[np.where(more_year == years)[0][0]]
                p = (year - less_year)/(more_year - less_year)
                new_values[index] = p * more_value + (1-p) * less_value
        return new_years, new_values


    ## This function converts the dataframe result from gcam query to data in the 
    ## expected format for stitches. Cacheable without any parameters is used for
    ## default options although default options may not be the best every time.
    @cacheable
    def stitch_prep(df):
        import stitches
        import pkg_resources
        import pandas as pd
        import numpy as np
        path = pkg_resources.resource_filename('stitches', 'data/matching_archive_staggered.csv')
        data = pd.read_csv(path)
        end_yr_vector = np.arange(2100,1800,-9)
        data = stitches.fx_processing.subset_archive(staggered_archive = data, end_yr_vector = end_yr_vector)
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
        for i in range(10):
            stitches_recipe = stitches.make_recipe(target_data, model_data, tol=0., N_matches=1, res='day', 
                                                non_tas_variables=['tasmin', 'pr', 'hurs', 'sfcWind', 'rsds', 'rlds'])
        last_period_length = stitches_recipe['target_end_yr'].values[-1] - stitches_recipe['target_start_yr'].values[-1]
        asy = stitches_recipe['archive_start_yr'].values
        asy[-1] = stitches_recipe['archive_end_yr'].values[-1] - last_period_length
        stitches_recipe['archive_start_yr'] = asy.copy()
        return stitches_recipe

    ## This function will run the stitches gridded stitching. This function also
    ## runs the stitching in synchronous mode to avoid any issues with dask. This
    ## mode may be used if certain errors are received during execution. 
    @cacheable
    def run_stitches(recipe, output_path):
        import stitches
        import dask
        ## The dask config is set to synchronous to avoid any issues. 
        with dask.config.set(scheduler="synchronous"):
            outputs = stitches.gridded_stitching(output_path, recipe)
        return outputs

    ## Two workers are added to the cluster with the tag "gcam". This identifies
    ## the environment/container the worker will be running in. 
    cluster.add_workers(n=2, tag="gcam")

    ## Scalable Client is made. This is how functions will be sent to the cluster.
    sc_client = ScalableClient(cluster)


    ## Main workflow starts below

    ## The GCAM Reference Scenario is given as the configuration to run gcam.
    ## The tag "gcam" is used to identify the worker to run the function on and is
    ## necessary for expected behavior.
    future1 = sc_client.submit(run_gcam, "/qfs/people/lamb678/work/gcam-core/exe/configuration_ref.xml", 2100, n=1, tag="gcam")

    ## The output of the gcam run is then read to extract the data. future1 can be 
    ## directly used as the input to this function when submitting it to the 
    ## cluster. 
    future2 = sc_client.submit(readdb, future1, n=1, tag="gcam")

    ## Adding stitches workers to the cluster.
    cluster.add_workers(n=1, tag="stitches")

    ## The data extracted from the gcam database is then prepared for stitches.
    future3 = sc_client.submit(stitch_prep, future2, n=1, tag="stitches")

    ## Now the gcam workers can be removed as their results have been used. 
    ## Removing workers before their results are used will lead to a loss of results.

    cluster.remove_workers(n=2, tag="gcam")

    ## The prepared data is then used to run stitches. The output of this function
    ## is the output directory where the stitched data is stored.

    future4 = sc_client.submit(run_stitches, future3, '/rcfs/projects/gcims/projects/scalable/', n=1, tag='stitches')

    ## The output of the stitches run is then fetched and printed.

    print(future4.result())

    ## At this point, the workflow is completed and the cluster can be closed.
    ## The closing of the cluster would cancel all current slurm jobs and remove
    ## all workers.

    cluster.close()

    quit()

This workflow is an excellent demonstration of how the Scalable package can be 
used for running workflows with multiple parts to them and which may use 
multiple libraries or models. If a certain workflow cannot be completed for any 
reason, please feel free to open an issue 
`here <https://github.com/JGCRI/scalable/issues>`_.