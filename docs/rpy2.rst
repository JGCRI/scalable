How to convert R code to Python code using rpy2
===============================================

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
directly by just replacing the R syntax with Python syntax. If any issues arise 
or any help is needed converting a specific piece of code, please feel free 
to open an issue on the scalable github repo 
`here <https://github.com/JGCRI/scalable/issues>`_.