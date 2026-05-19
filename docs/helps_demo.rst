A Complete Process of Adding & Scaling a New Application
=========================================================

This demo is broken into clear stages for adding an R-based application
(`HELPS <https://github.com/JGCRI/HELPS>`_) and running it at scale with
Scalable.

Step 1: Add a new container target
----------------------------------

Add a ``helps`` target to your Dockerfile (the one used by
``scalable_bootstrap``).

.. code-block:: dockerfile

    FROM ubuntu:22.04 AS build_env

    ENV DEBIAN_FRONTEND=noninteractive
    RUN apt-get -y update && apt-get install -y \
        wget unzip openjdk-11-jdk-headless build-essential libtbb-dev \
        libboost-dev libboost-filesystem-dev libboost-system-dev \
        python3 python3-pip libboost-python-dev libboost-numpy-dev \
        ssh nano locate curl net-tools netcat-traditional git python3 python3-pip \
        python3-dev gcc libboost-python1.74 libboost-numpy1.74 openjdk-11-jre-headless libtbb12 rsync
    RUN apt-get -y update && apt -y upgrade
    RUN pip3 install --upgrade dask[complete] dask-jobqueue dask_mpi pyyaml joblib versioneer tomli xarray
    RUN apt-get -y update && apt -y upgrade
    RUN mkdir -p /usr/lib/R/site-library
    ENV R_LIBS_USER /usr/lib/R/site-library
    RUN chmod a+w /usr/lib/R/site-library
    RUN apt-get install -y --no-install-recommends r-base r-base-dev
    RUN apt-get install -y --no-install-recommends python3-rpy2
    RUN python3 -m pip install -U pip

.. code-block:: dockerfile

    FROM build_env AS helps
    RUN apt-get -y update && apt -y upgrade && apt-get -y -f install
    RUN apt install --fix-missing -y software-properties-common
    RUN add-apt-repository ppa:ubuntugis/ppa
    RUN apt-get update
    ENV R_LIBS_USER /usr/lib/R/site-library
    RUN chmod a+w /usr/lib/R/site-library
    RUN apt-get install -y libcurl4-openssl-dev libssl-dev libxml2-dev libudunits2-dev libproj-dev libavfilter-dev \
        libbz2-dev liblzma-dev libfontconfig1-dev libharfbuzz-dev libfribidi-dev libgeos-dev libgdal-dev
    RUN git clone https://github.com/JGCRI/HELPS.git /HELPS

    RUN echo "import rpy2.robjects.packages as rpackages" >> /install_script.py \
        && echo "utils = rpackages.importr('utils')" >> /install_script.py \
        && echo "utils.install_packages('devtools')" >> /install_script.py \
        && echo "utils.install_packages('arrow')" >> /install_script.py \
        && echo "utils.install_packages('assertthat')" >> /install_script.py
    RUN python3 /install_script.py

    RUN echo "import rpy2.robjects.packages as rpackages" > /install_script.py \
        && echo "devtools = rpackages.importr('devtools')" >> /install_script.py \
        && echo "devtools.install_github('JGCRI/HELPS', dependencies=True)" >> /install_script.py
    RUN python3 /install_script.py

    RUN echo "import rpy2.robjects.packages as rpackages" > /install_script.py \
        && echo "helps = rpackages.importr('HELPS')" >> /install_script.py
    RUN python3 /install_script.py

    COPY --from=scalable /scalable /scalable
    RUN pip3 install /scalable/.
    RUN pip3 install --force-reinstall xarray==2024.5.0
    RUN pip3 install --force-reinstall numpy==1.26.4

Notes:

* ``build_env`` is a recommended base for new targets.
* ``rpy2`` is used here for consistency with runtime access patterns.
* Keep core package version pins aligned with other Scalable targets.


Step 2: Build and publish the new target
----------------------------------------

Run ``scalable_bootstrap`` and select ``helps`` when prompted for targets.
Bootstrap will build locally and upload to the remote system.


Step 3: Create a preload script for R imports
---------------------------------------------

Preloading R objects avoids repeated session initialization and reduces runtime
issues.

.. code-block:: python

    def dask_setup(worker):
        import rpy2.robjects.packages as rpackages
        import rpy2.robjects as r

        helps = rpackages.importr('HELPS')
        worker.imports = {}
        worker.imports['HELPS'] = helps
        worker.imports['country_raster'] = r.r['country_raster']
        worker.imports['reg_WB_raster'] = r.r['reg_WB_raster']


Step 4: Define task functions
-----------------------------

Each function pulls R objects from ``worker.imports``.

.. code-block:: python

    from scalable import *

    def run_heatstress(hurs_file_name, tas_file_name, rsds_file_name, target_year):
        worker = get_worker()
        helps = worker.imports['HELPS']

        return helps.cal_heat_stress(
            TempRes="month",
            SECTOR="SUNF_R",
            HS=helps.WBGT_ESI,
            YEAR_INPUT=target_year,
            a=hurs_file_name,
            b=tas_file_name,
            c=rsds_file_name,
        )

.. code-block:: python

    def run_physical_work_capacity(heat_stress_raster):
        worker = get_worker()
        helps = worker.imports['HELPS']

        return helps.cal_pwc(
            WBGT=heat_stress_raster,
            LHR=helps.LHR_Hothaps,
            workload="high",
        )

.. code-block:: python

    def run_annualized_physical_work_capacity(physical_work_capacity_raster):
        worker = get_worker()
        helps = worker.imports['HELPS']

        return helps.monthly_to_annual(
            input_rack=physical_work_capacity_raster,
            SECTOR="SUNF_R",
        )

.. code-block:: python

    def run_country_physical_work_capacity(annualized_physical_work_capacity_df):
        worker = get_worker()
        helps = worker.imports['HELPS']
        country_raster = worker.imports['country_raster']

        return helps.grid_to_region(
            grid_annual_value=annualized_physical_work_capacity_df,
            SECTOR="SUNF_R",
            rast_boundary=country_raster,
        )

.. code-block:: python

    def run_basin_physical_work_capacity(annualized_physical_work_capacity_df):
        worker = get_worker()
        helps = worker.imports['HELPS']
        reg_WB_raster = worker.imports['reg_WB_raster']

        return helps.grid_to_region(
            grid_annual_value=annualized_physical_work_capacity_df,
            SECTOR="SUNF_R",
            rast_boundary=reg_WB_raster,
        )


Step 5: Configure runtime inputs
--------------------------------

.. code-block:: python

    hurs_file_name = "path/to/hurs_file"
    tas_file_name = "path/to/tas_file"
    rsds_file_name = "path/to/rsds_file"

    # 2015 through 2100 in 5-year increments
    target_years = list(range(2015, 2105, 5))
    num_years = len(target_years)


Step 6: Create cluster and add HELPS container profile
-------------------------------------------------------

.. code-block:: python

    cluster = SlurmCluster(
        queue='short',
        walltime='02:00:00',
        account='GCIMS',
        silence_logs=False,
    )

    cluster.add_container(
        tag="helps",
        cpus=1,  # R workloads are commonly single-threaded
        memory="8G",
        preload_script='/path/to/preload_script.py',
        dirs={"/path1": "/path1", "/path2": "/path2"},
    )


Step 7: Start workers and create a client
-----------------------------------------

.. code-block:: python

    cluster.add_workers(n=num_years, tag="helps")
    sc_client = ScalableClient(cluster)


Step 8: Submit the pipeline using ``map``
-----------------------------------------

Use ``map`` when running the same function over a sequence of arguments.

.. code-block:: python

    heatstress_futures = sc_client.map(
        run_heatstress,
        [hurs_file_name] * num_years,
        [tas_file_name] * num_years,
        [rsds_file_name] * num_years,
        target_years,
        n=1,
        tag="helps",
    )

.. code-block:: python

    pwc_futures = sc_client.map(run_physical_work_capacity, heatstress_futures, n=1, tag="helps")
    annualized_pwc_futures = sc_client.map(run_annualized_physical_work_capacity, pwc_futures, n=1, tag="helps")
    country_pwc_futures = sc_client.map(run_country_physical_work_capacity, annualized_pwc_futures, n=1, tag="helps")
    basin_pwc_futures = sc_client.map(run_basin_physical_work_capacity, annualized_pwc_futures, n=1, tag="helps")


Step 9: Gather results
----------------------

.. code-block:: python

    heatstress_results = sc_client.gather(heatstress_futures)
    pwc_results = sc_client.gather(pwc_futures)
    annualized_pwc_results = sc_client.gather(annualized_pwc_futures)
    country_pwc_results = sc_client.gather(country_pwc_futures)
    basin_pwc_results = sc_client.gather(basin_pwc_futures)


This workflow demonstrates how to add a new R-based container, preload R
dependencies, and scale a year-by-year analysis pipeline through Scalable.
For troubleshooting, open an issue at
`https://github.com/JGCRI/scalable/issues <https://github.com/JGCRI/scalable/issues>`_.

