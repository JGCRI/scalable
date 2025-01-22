A Complete Process of Adding & Scaling a New Application
=========================================================

This is another demo where a new container with a new R package is added to be 
scaled appropriately using scalable. 

The first step would be to add a new container with the new R package. This 
should be done by adding a new target to the Dockerfile which is located in the 
home directory where scalable_bootstrap is launched. In this case, the 
`HELPS <https://github.com/JGCRI/HELPS>`_ package is added as a target to 
make a new container. Since the HELPS package is a R package, and rpy2 is the 
primary method of interacting with R applications when using Scalable, it would 
be good practice to try adding HELPS through rpy2. This is the new target:

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
    RUN    echo "import rpy2.robjects.packages as rpackages" >> /install_script.py \
        && echo "utils = rpackages.importr('utils')" >> /install_script.py \
        && echo "utils.install_packages('devtools')" >> /install_script.py \
        && echo "utils.install_packages('arrow')" >> /install_script.py \
        && echo "utils.install_packages('assertthat')" >> /install_script.py 
    RUN python3 /install_script.py
    RUN    echo "import rpy2.robjects.packages as rpackages" >> /install_script.py \
        && echo "devtools = rpackages.importr('devtools')" >> /install_script.py \
        && echo "devtools.install_github('JGCRI/HELPS', dependencies=True)" >> /install_script.py 
    RUN python3 /install_script.py
    RUN    echo "import rpy2.robjects.packages as rpackages" > /install_script.py \
        && echo "helps = rpackages.importr('HELPS')" >> /install_script.py 
    RUN python3 /install_script.py
    COPY --from=scalable /scalable /scalable
    RUN pip3 install /scalable/.
    RUN pip3 install --force-reinstall xarray==2024.5.0
    RUN pip3 install --force-reinstall numpy==1.26.4    

The build_env target is included in the base Dockerfile which is automatically 
downloaded. It is recommended to use build_env as the base target for all new 
containers. The helps target is manually added. Note that rpy2 isn't needed to 
download or install the helps package, it's done here for the sake of 
consistency. To learn more about how to convert R code to Python code using 
rpy2, this guide :doc:`rpy2` can be referred to.

Now, once the the target is added, it can be selected by running the 
scalable_bootstrap and selecting the new target. It will be built locally and 
uploaded automatically to the remote system. 

The next step would be to make functions to actually run the helps package. 
This is relatively simple, just launch python3 in the terminal where the 
bootstrap lands and run the following code:

.. code-block:: python

    from scalable import *

    def run_heatstress(hurs_file_name, tas_file_name, rsds_file_name, target_year):
        import rpy2.robjects.packages as rpackages

        helps = rpackages.importr('HELPS')

        # generate a heat stress raster brick for the desired resolution
        heat_stress_raster = helps.HeatStress(
            TempRes = "month", 
            SECTOR = "SUNF_R", 
            HS = helps.WBGT_ESI, 
            YEAR_INPUT = target_year, 
            a=hurs_file_name, 
            b=tas_file_name, 
            c=rsds_file_name
        )

        return heat_stress_raster


    def run_physical_work_capacity(heat_stress_raster):
        import rpy2.robjects.packages as rpackages

        helps = rpackages.importr('HELPS')

        # generate physical work capacity raster brick
        physical_work_capacity_raster = helps.PWC(
            WBGT = heat_stress_raster,  
            LHR = helps.LHR_Hothaps, 
            workload = "high"
        )

        return physical_work_capacity_raster


    def run_annualized_physical_work_capacity(physical_work_capacity_raster):
        import rpy2.robjects.packages as rpackages

        helps = rpackages.importr('HELPS')

        # aggregate physical work capacity to annual values and reformat to a data frame
        annualized_physical_work_capacity_df = helps.MON2ANN(
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
        country_physical_work_capacity_df = helps.G2R(
            grid_annual_value = annualized_physical_work_capacity_df, 
            SECTOR = "SUNF_R", 
            rast_boundary = country_raster
        )

        return country_physical_work_capacity_df


    def run_basin_physical_work_capacity(annualized_physical_work_capacity_df):
        import rpy2.robjects.packages as rpackages
        import rpy2.robjects as robjects

        helps = rpackages.importr('HELPS')
        reg_WB_raster = robjects.r['reg_WB_raster']
        
        # map annual physical work capacity to gridded water basins
        basin_physical_work_capacity_df = helps.G2R(
            grid_annual_value = annualized_physical_work_capacity_df, 
            SECTOR = "SUNF_R", 
            rast_boundary = reg_WB_raster
        )

        return basin_physical_work_capacity_df


    if __name__ == "__main__":

        hurs_file_name = "path/to/hurs_file"
        tas_file_name = "path/to/tas_file"
        rsds_file_name = "path/to/rsds_file"

        # all the functions need to be ran for all the target years.
        # in this case, target years would be 2015 - 2100 in 5 year increments

        target_years = list(range(2015, 2105, 5))

        num_years = len(target_years)

        ## Creating a SlurmCluster object with the required parameters

        cluster = SlurmCluster(queue='short', walltime='02:00:00', account='GCIMS', silence_logs=False)

        ## Adding the helps container specifications (can be changed as needed)        
        cluster.add_container(tag="helps", cpus=4, memory="8G", dirs={"/path1":"/path1", "/path2":"/path2"})

        ## Adding workers to the cluster
        cluster.add_workers(n=num_years, tag="helps")

        # Making a client to submit jobs
        sc_client = ScalableClient(cluster)


        # run helps

        # note that the map function is used here as multiple instances of the 
        # same function is being ran with different inputs. This is essentially
        # parallelization. To make it possible, pass in multiple lists of 
        # arguments to the map function. If the target function has 2 arguments 
        # then 2 lists of the same size should be passed. The size of the list 
        # will be the same as the number of instances of the target function 
        # that will be ran.

        # n = 1 is used as the value for n because n specifies the number of 
        # workers needed for a single instance of the target function.
        heatstress_futures = sc_client.map(run_heatstress, [hurs_file_name]*num_years, [tas_file_name]*num_years, 
                                           [rsds_file_name]*num_years, target_years, n=1, tag="helps")

        pwc_futures = sc_client.map(run_physical_work_capacity, heatstress_futures, n=1, tag="helps")

        annualized_pwc_futures = sc_client.map(run_annualized_physical_work_capacity, pwc_futures, n=1, tag="helps")

        country_pwc_futures = sc_client.map(run_country_physical_work_capacity, annualized_pwc_futures, n=1, tag="helps")

        basin_pwc_futures = sc_client.map(run_basin_physical_work_capacity, annualized_pwc_futures, n=1, tag="helps")

        # now the results can be gathered and then printed or written to a file

        heatstress_results = sc_client.gather(heatstress_futures)
        pwc_results = sc_client.gather(pwc_futures)
        annualized_pwc_results = sc_client.gather(annualized_pwc_futures)
        country_pwc_results = sc_client.gather(country_pwc_futures)
        basin_pwc_results = sc_client.gather(basin_pwc_futures)


This code will run the HELPS package on the remote HPC system. The entire guide 
highlights the process of adding a new container with a new R package and 
scaling it using Scalable. Please feel free to reach out for any more help 
regarding the same or open an issue on the Scalable GitHub repository. 


