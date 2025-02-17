How to convert R code to Python code using rpy2 and run it through Scalable
============================================================================

While using scalable, there may be multiple instances where a model which needs 
to be scaled is written in R or can only be interacted with in R. While it is 
possible to scale R code by writing it all in an Rscript and calling the script 
from Python, it is generally recommended to the R code to Python code using 
rpy2. This is to allow for better integration of such code with Python and make 
it much easier to modify inputs, get precise outputs, and debug the code.

The full documentation for rpy2 can be found on this
`website <https://rpy2.github.io/doc.html>`_. In this guide, only the important 
methods for converting R code to Python code will be discussed which is all 
that is needed in most of the cases. 

Let's look at an example with R code to convert. The 
`HELPS <https://github.com/JGCRI/HELPS>`_ package will be used to demonstrate 
the conversion. The R code is as follows:


.. code-block:: r

    library(HELPS)

    # test
    esi.mon <- cal_heat_stress(TempRes = "month", SECTOR = "SUNF_R", HS = WBGT_ESI, YEAR_INPUT = 2024,
                            "path/hurs_mon_basd_CanESM5_W5E5v2_GCAM_ref_2015.nc",
                            "path/tas_mon_basd_CanESM5_W5E5v2_GCAM_ref_2015-2100.nc",
                            "path/rsds_mon_basd_CanESM5_W5E5v2_GCAM_ref_2015.nc")


    pwc.mon.hothaps <- cal_pwc(WBGT = esi.mon,  LHR = LHR_Hothaps, workload = "high")
    pwc.hothaps.ann <- monthly_to_annual(input_rack = pwc.mon.hothaps, SECTOR = "SUNF_R")
    ctry_pwc <- grid_to_region(grid_annual_value = pwc.hothaps.ann, SECTOR = "SUNF_R", rast_boundary = country_raster)
    glu_pwc <- grid_to_region(grid_annual_value = pwc.hothaps.ann, SECTOR = "SUNF_R", rast_boundary = reg_WB_raster)


A simple conversion of the above code to Python code using rpy2 is as follows:

.. code-block:: python

    import rpy2.robjects.packages as rpackages
    import rpy2.robjects as robjects

    helps = rpackages.importr('HELPS')
    
    esi_mon = helps.cal_heat_stress(TempRes = "month", SECTOR = "SUNF_R", HS = helps.WBGT_ESI, YEAR_INPUT = 2024, 
                                    a="hurs_mon_basd_CanESM5_W5E5v2_GCAM_ref_2015-2100.nc",
                                    b="tas_mon_basd_CanESM5_W5E5v2_GCAM_ref_2015-2100.nc", 
                                    c="rsds_mon_basd_CanESM5_W5E5v2_GCAM_ref_2015-2100.nc")

    pwc_mon_hothaps = helps.cal_pwc(WBGT = esi_mon,  LHR = helps.LHR_Hothaps, workload = "high")
    pwc_hothaps_ann = helps.monthly_to_annual(input_rack = pwc_mon_hothaps, SECTOR = "SUNF_R")
    
    country_raster = robjects.r['country_raster']
    ctry_pwc = helps.grid_to_region(grid_annual_value = pwc_hothaps_ann, SECTOR = "SUNF_R", rast_boundary = country_raster)
    
    reg_WB_raster = robjects.r['reg_WB_raster']
    glu_pwc = helps.grid_to_region(grid_annual_value = pwc_hothaps_ann, SECTOR = "SUNF_R", rast_boundary = reg_WB_raster)


The above code is a simple conversion of the R code to Python code using rpy2. 
A couple of important things to note are:

*   The HELPS package is imported at ``helps = rpackages.importr('HELPS')``. 
    This is similar to importing a package in R using ``library(HELPS)``. 
    Unlike R, all the functions in a package are not automatically imported. 
    Instead an object is created whose attributes corresponds to the methods in 
    that package. 

*   If there are functions or values in the R code which are either not defined 
    in any particular package, are defined in the global environment, or it's 
    simply unknown where exactly they may reside then the ``robjects.r`` object
    can be used to access them. For example, in the above code, the 
    ``country_raster`` and ``reg_WB_raster`` functions are not defined in the 
    HELPS package, and without any knowledge where they may reside, the 
    ``robjects.r`` object can be used to access by just looking up the name of 
    the function or value in the R code. Another example is if ``pi`` is used 
    in the R code, then it can be accessed in Python using 
    ``pi = robjects.r['pi']``.

*   A more subtle point to note is that the ``HeatStress`` function in R takes 
    three positional arguments at the end. These are matched to the ``...`` 
    argument in the R code. However, no positional arguments should be passed 
    to the rpy2 function in python to avoid confusion. To make sure that the 
    extra arguments get matched with ``...`` internally, arbitrary names can 
    be used for the arguments. In the above code, such arguments are named 
    ``a``, ``b``, and ``c``.

These are the only two important things to note when converting R code to 
Python code using rpy2 in most cases. The rest of the code can be converted 
directly by just replacing the R syntax with Python syntax.

Running R code through Scalable
-------------------------------

Running R code on scalable, while ensuring that no unexpected behavior occurs, 
can be a little tricky. While making functions having code similar to the above 
example can work to run them through scalable, a crucial step should be taken 
to avoid any unexpected behavior. This step involves a preload script. Let's 
look at another example. Let's say the python functions below are desired to be 
run through scalable:

.. code-block:: python

    def run_annualized_physical_work_capacity(physical_work_capacity_raster):
        import rpy2.robjects.packages as rpackages

        helps = rpackages.importr('HELPS')

        # aggregate physical work capacity to annual values and reformat to a data frame
        annualized_physical_work_capacity_df = helps.monthly_to_annual(
            input_rack = physical_work_capacity_raster, 
            SECTOR = "SUNF_R"
        )

        return annualized_physical_work_capacity_df


    def run_country_physical_work_capacity(annualized_physical_work_capacity_df):
        import rpy2.robjects.packages as rpackages
        import rpy2.robjects as robjects

        helps = rpackages.importr('HELPS')
        country_raster = robjects.r['country_raster']

        # map annual physical work capacity to gridded countries
        country_physical_work_capacity_df = helps.grid_to_region(
            grid_annual_value = annualized_physical_work_capacity_df, 
            SECTOR = "SUNF_R", 
            rast_boundary = country_raster
        )

        return country_physical_work_capacity_df


The above functions would run fine in most cases through scalable. However, 
since rpy2 launches an implicit R session when it is imported, it is important 
to ensure that the R session is launched before the functions are run to 
prevent deadlocks or multiple R sessions from being launched. This can be done 
with the use of a preload python script. All this script needs to do is import
rpy2 and everything that may be needed in any of the functions. It should look 
something like this if the above functions are to be run:

.. code-block:: python

    def dask_setup(worker):
        import rpy2.robjects.packages as rpackages
        import rpy2.robjects as r
        from rpy2.robjects import StrVector
        helps = rpackages.importr('HELPS')
        terra = rpackages.importr('terra')
        arrow = rpackages.importr('arrow')
        worker.imports = {}
        worker.imports['HELPS'] = helps
        worker.imports['terra'] = terra
        worker.imports['arrow'] = arrow
        worker.imports['country_raster'] = r.r['country_raster']
        worker.imports['reg_WB_raster'] = r.r['reg_WB_raster']
        worker.imports['StrVector'] = StrVector

The script above calls the ``dask_setup`` function with the worker argument. 
In this function, everything that may be needed from the R environment is 
imported and stored in the worker.imports dictionary. This dictionary is then 
used to import the necessary objects in the functions. The path to the preload 
script just needs to be passed into the ``PreloadScript`` argument in the 
scalable ``add_container`` function. The original functions also need to be 
modified a little to use the objects created in the preload script. 

The modified functions would look like this:

.. code-block:: python

    from scalable import *

    def run_annualized_physical_work_capacity(physical_work_capacity_raster):
        worker = get_worker()
        helps = worker.imports['HELPS']

        # aggregate physical work capacity to annual values and reformat to a data frame
        annualized_physical_work_capacity_df = helps.monthly_to_annual(
            input_rack = physical_work_capacity_raster, 
            SECTOR = "SUNF_R"
        )

        return annualized_physical_work_capacity_df

    def run_country_physical_work_capacity(annualized_physical_work_capacity_df):
        worker = get_worker()
        helps = worker.imports['HELPS']
        country_raster = worker.imports['country_raster']

        # map annual physical work capacity to gridded countries
        country_physical_work_capacity_df = helps.grid_to_region(
            grid_annual_value = annualized_physical_work_capacity_df, 
            SECTOR = "SUNF_R", 
            rast_boundary = country_raster
        )

        return country_physical_work_capacity_df

The above functions can now be run through scalable without any issues. As a 
reminder, the ``add_container`` function should be called with the preload 
script path passed into the ``preload_script`` argument. It should look 
something like this:

.. code-block:: python

    from scalable import *

    cluster = SlurmCluster(
        queue='short', 
        walltime='02:00:00', 
        account='GCIMS', 
        silence_logs=False
    )

    cluster.add_container(
        tag='HELPS',
        # 1 cpu since R is single-threaded
        cpus=1,
        memory='8GB',
        preload_script='path/to/preload_script.py'
    )

Ensuring that the above steps are used to run R code through scalable will 
prevent any unexpected behavior. The above steps are general and should work 
for most cases where R code needs to be run through scalable.

If any issues arise or any help is needed converting a specific piece of code, 
please feel free to open an issue on the scalable github repo 
`here <https://github.com/JGCRI/scalable/issues>`_.