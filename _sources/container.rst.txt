How to add custom containers for scalable as workers
====================================================

Containers are quite central to scalable. Everything runs in a container to 
maintain isolation and reproducibility. A Dockerfile is provided with scalable 
which has targets for in-house JGCRI climate models. However, these targets can 
either be modified or extended to have custom ones. In the provided Dockerfile,
all the targets are built from a base or "build_env" target. Let's look at this
target:

.. code-block:: dockerfile
    
    FROM ubuntu:22.04 AS build_env

    ENV DEBIAN_FRONTEND=noninteractive
    RUN apt-get -y update && apt-get install -y \ 
        wget unzip openjdk-11-jdk-headless build-essential libtbb-dev \
        libboost-dev libboost-filesystem-dev libboost-system-dev \
        python3 python3-pip libboost-python-dev libboost-numpy-dev \
        ssh nano locate curl net-tools netcat-traditional git python3 \
        python3-pip python3-dev gcc libboost-python1.74 libboost-numpy1.74 \
        openjdk-11-jre-headless libtbb12 rsync
    RUN apt-get -y update && apt -y upgrade
    RUN pip3 install --upgrade dask[complete] dask-jobqueue dask_mpi pyyaml \
        joblib versioneer tomli xarray
    RUN apt-get -y update && apt -y upgrade
    RUN apt-get install -y --no-install-recommends r-base r-base-dev
    RUN apt-get install -y --no-install-recommends python3-rpy2
    ENV R_LIBS_USER usr/lib/R/site-library
    RUN chmod a+w /usr/lib/R/site-library
    RUN cp -r /usr/lib/R/site-library /usr/local/lib/R/site-library
    RUN python3 -m pip install -U pip


The target above details the libraries and packages needed for most JGCRI 
climate models. Not all of these libraries are needed for any one model but 
most are useful in general. Now, let's look at a target for scalable itself and
a specific model, in this case demeter:

.. code-block:: dockerfile

    FROM build_env AS scalable
    ADD "https://api.github.com/repos/JGCRI/scalable/commits?per_page=1" latest_commit
    RUN git clone https://github.com/JGCRI/scalable.git /scalable
    RUN pip3 install /scalable/.
    RUN pip3 install --force-reinstall xarray==2024.5.0
    RUN pip3 install --force-reinstall numpy==1.26.4

    FROM build_env AS demeter
    RUN apt-get -y update && apt -y upgrade
    RUN python3 -m pip install git+http://github.com/JGCRI/demeter.git#egg=demeter
    RUN mkdir /demeter
    RUN echo "import demeter" >> /demeter/install_script.py \
        && echo "demeter.get_package_data(\"/demeter\")" >> /demeter/install_script.py
    RUN python3 /demeter/install_script.py
    COPY --from=scalable /scalable /scalable
    RUN pip3 install /scalable/.
    RUN pip3 install --force-reinstall xarray==2024.5.0
    RUN pip3 install --force-reinstall numpy==1.26.4

Right off the bat, one thing that stands out is the force reinstallation of 
xarray and numpy. This is because the versions of these libraries used in most, 
if not all, JGCRI climate models are not the latest. So, this is done to ensure 
that nothing breaks when the models are ran. While different containers can 
have different environments, libraries like numpy, xarry, and dask are used 
by all models and should have the same versions in all the containers. Python 
versions should also be the same in all the containers. 

The scalable target simply installs the latest version of the scalable package 
and corrects for any library versions at the end. Please feel free to remove 
the force reinstallation of numpy and xarray if you are sure that the models 
you are running will not break with the latest versions of these libraries. 

The demeter target also just installs the latest version of the demeter along 
with installing its package data. The scalable package is then copied from 
the scalable target to the demeter target. This is important and it's highly 
recommended to do the same in any custom target. Along with ensuring that the 
scalable package is installed in the target container which is needed, it also 
ensures that the same version of the scalable package is used in all the 
targets. 

For a custom target, a similar template as demeter should be followed. Start 
with the build_env target, add the desired libraries or applications, and copy 
the scalable package from the scalable target. Ensure to have a scalable target 
which is named "scalable". It's used by the bootstrap script. If any library 
version corrections are needed, they can be made at the end of the target.
The reinstallation commands should be at the end to prevent any unintended 
side effects by other commands. 
