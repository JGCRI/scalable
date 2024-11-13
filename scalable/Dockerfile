# syntax=docker/dockerfile:1
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
RUN apt-get install -y --no-install-recommends r-base r-base-dev
RUN apt-get install -y --no-install-recommends python3-rpy2
ENV R_LIBS_USER usr/lib/R/site-library
RUN chmod a+w /usr/lib/R/site-library
RUN cp -r /usr/lib/R/site-library /usr/local/lib/R/site-library
RUN python3 -m pip install -U pip

FROM build_env AS conda
RUN wget https://repo.anaconda.com/miniconda/Miniconda3-latest-Linux-x86_64.sh
RUN chmod +x Miniconda3-latest-Linux-x86_64.sh \
    && ./Miniconda3-latest-Linux-x86_64.sh -b
RUN eval "$(/root/miniconda3/bin/conda shell.bash hook)" \
    && conda install -y -c conda-forge python=3.10.12 \
    && conda update conda \
    && apt-get autoclean \
    && rm -rf /var/lib/apt/lists/* /var/log/dpkg.log \
    && conda clean --all --yes
ENV PATH /root/miniconda3/bin:$PATH
RUN conda init

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

FROM build_env AS stitches
RUN apt-get -y update && apt -y upgrade
RUN git clone -b daily-data-refinements --depth 1 https://github.com/JGCRI/stitches.git /stitches
RUN cd /stitches && sed -i 's/numpy>=1.23.3/numpy~=1.26.4/g' setup.py 
RUN pip3 install /stitches/.
RUN rm -rf /stitches
RUN pip3 install cftime && pip3 uninstall urllib3 -y && pip3 install --no-cache-dir -U urllib3
RUN echo "import stitches" >> /install_script.py \
    && echo "stitches.install_pkgdata.install_package_data()" >> /install_script.py
RUN python3 /install_script.py
RUN pip install -U dask[complete] pandas
COPY --from=scalable /scalable /scalable
RUN pip3 install /scalable/.
RUN pip3 install --force-reinstall xarray==2024.5.0
RUN pip3 install --force-reinstall numpy==1.26.4

FROM build_env AS tethys
RUN apt-get -y update && apt -y upgrade
RUN python3 -m pip install git+https://github.com/JGCRI/tethys
RUN mkdir /tethys
RUN echo "import tethys" >> /tethys/install_script.py \
    && echo "tethys.get_example_data()" >> /tethys/install_script.py
RUN python3 /tethys/install_script.py
COPY --from=scalable /scalable /scalable
RUN pip3 install /scalable/.
RUN pip3 install --force-reinstall xarray==2024.5.0
RUN pip3 install --force-reinstall numpy==1.26.4

FROM build_env AS xanthos
ADD "https://api.github.com/repos/JGCRI/scalable/commits/Develop?per_page=1" latest_commit
RUN apt-get -y update && apt -y upgrade
RUN mkdir /xanthos
RUN git clone -b dev --depth 1 https://github.com/JGCRI/xanthos.git /xanthos
RUN cd /xanthos && sed -i 's/numpy~=/numpy>=/g' setup.py && sed -i 's/pandas~=/pandas>=/g' setup.py \
    && sed -i 's/hyd_grid_data["elevD"][:, np.newaxis]/hyd_grid_data["elevD"].to_numpy()[:, np.newaxis]/g' xanthos/hydropower/potential.py
RUN pip install /xanthos
RUN echo "import xanthos" >> /xanthos/install_script.py \
    && echo "xanthos.get_package_data(\"/xanthos\")" >> /xanthos/install_script.py
RUN python3 /xanthos/install_script.py
COPY --from=scalable /scalable /scalable
RUN pip3 install /scalable/.
RUN pip3 install --force-reinstall xarray==2024.5.0
RUN pip3 install --force-reinstall numpy==1.26.4

FROM conda AS basd
RUN apt-get -y update && apt -y upgrade
RUN pip install git+https://github.com/JGCRI/basd.git \
    && conda install -y -c conda-forge xesmf \
    && conda install -y -c conda-forge numpy=1.26.4 \
    && conda install -y -c conda-forge xarray=2024.5.0 \
    && conda install -y -c conda-forge importlib_metadata=6.8.0
RUN conda install --solver=classic conda-forge::conda-libmamba-solver conda-forge::libmamba conda-forge::libmambapy conda-forge::libarchive
COPY --from=scalable /scalable /scalable
RUN pip3 install /scalable/.
RUN pip3 install --force-reinstall importlib_metadata==6.8.0
RUN pip3 install --force-reinstall numpy==1.26.4

FROM build_env AS hector
RUN apt-get -y update && apt -y upgrade
RUN python3 -m pip install pyhector
COPY --from=scalable /scalable /scalable
RUN pip3 install /scalable/.

FROM build_env AS osiris
RUN apt install -y software-properties-common
RUN add-apt-repository ppa:ubuntugis/ppa
RUN apt-get update
RUN apt-get install -y libcurl4-openssl-dev libssl-dev libxml2-dev libudunits2-dev libproj-dev libavfilter-dev \
    libbz2-dev liblzma-dev libfontconfig1-dev libharfbuzz-dev libfribidi-dev libgeos-dev libgdal-dev
RUN git clone --depth 1 https://github.com/JGCRI/osiris.git /osiris
RUN sed -i 's/dplyr::ungroup ->/dplyr::ungroup() ->/g' /osiris/R/grid_to_basin_yield.R \
    && sed -i 's/dplyr::ungroup  %>%/dplyr::ungroup()  %>%/g' /osiris/R/grid_to_basin_yield.R 
RUN    echo "import rpy2.robjects.packages as rpackages" >> /install_script.py \
    && echo "utils = rpackages.importr('utils')" >> /install_script.py \
    && echo "utils.install_packages('devtools')" >> /install_script.py \
    && echo "remotes = rpackages.importr('remotes')" >> /install_script.py \
    && echo "remotes.install_local('/osiris')" >> /install_script.py \
    && echo "remotes.install_version('dplyr', version='1.0.10')" >> /install_script.py
RUN python3 /install_script.py
COPY --from=scalable /scalable /scalable
RUN pip3 install /scalable/.
RUN pip3 install --force-reinstall xarray==2024.5.0
RUN pip3 install --force-reinstall numpy==1.26.4

FROM build_env AS gcam
RUN apt-get -y update && apt -y upgrade
ARG EIGEN_VERSION=3.4.0
RUN git config --global pack.windowsMemory 512m
RUN git config --global http.postBuffer 924288000
RUN git clone --depth 1 --branch gcam-v7.0 https://github.com/JGCRI/gcam-core.git /gcam-core
RUN mkdir gcam-core/libs
RUN wget https://gitlab.com/libeigen/eigen/-/archive/${EIGEN_VERSION}/eigen-${EIGEN_VERSION}.tar.gz -P /gcam-core/libs/.
RUN cd /gcam-core/libs \
    && tar -xvf eigen-${EIGEN_VERSION}.tar.gz \
    && mv eigen-${EIGEN_VERSION} eigen
ARG JARS_LINK=https://github.com/JGCRI/modelinterface/releases/download/v5.4/jars.zip
RUN wget ${JARS_LINK} -P /gcam-core \
    && cd /gcam-core \
    && unzip jars.zip \
    && rm /gcam-core/jars.zip
ENV CXX='g++ -fPIC' \
    EIGEN_INCLUDE=/gcam-core/libs/eigen \
    BOOST_INCLUDE=/usr/include \
    BOOST_LIB=/usr/lib \
    TBB_INCLUDE=/usr/include \
    TBB_LIB=/usr/lib/x86_64-linux-gnu \
    JARS_LIB='/gcam-core/jars/*' \
    JAVA_HOME=/usr/lib/jvm/java-11-openjdk-amd64 \
    JAVA_INCLUDE=/usr/lib/jvm/java-11-openjdk-amd64/include \
    JAVA_LIB=/usr/lib/jvm/java-11-openjdk-amd64/lib/server
RUN cd /gcam-core && git submodule init cvs/objects/climate/source/hector \
    && git submodule update cvs/objects/climate/source/hector
RUN cd /gcam-core && make install_hector
RUN cd /gcam-core/cvs/objects/build/linux && make -j 4 gcam
RUN cp /gcam-core/exe/gcam.exe /usr/local/bin/gcam
RUN apt-get -y update && apt -y upgrade
ENV GCAM_INCLUDE=/gcam-core/cvs/objects \
    GCAM_LIB=/gcam-core/cvs/objects/build/linux
RUN git clone --branch GIL_Changes https://github.com/JGCRI/gcamwrapper.git /gcamwrapper
RUN cd /gcamwrapper && sed -i "s/python_requires='>=3.6.*, <4'/python_requires='>=3.6, <4'/g" setup.py
RUN cd /gcamwrapper && pip3 install .
RUN pip install gcamreader
RUN git clone https://github.com/JGCRI/gcam_config.git /gcam_config
RUN pip3 install /gcam_config/.
RUN pip3 install dtaidistance scipy
COPY --from=scalable /scalable /scalable
RUN pip3 install /scalable/.
RUN pip3 install --force-reinstall numpy==1.26.4


FROM build_env AS apptainer
RUN apt-get install -y libseccomp-dev pkg-config uidmap squashfs-tools fakeroot cryptsetup tzdata autoconf \
    libtool-bin libtool fuse libfuse3-dev libfuse-dev \
    && apt-get -y update && apt -y upgrade
RUN apt-get -y update && apt -y upgrade
ARG APPTAINER_COMMITISH="main"
ARG APPTAINER_TMPDIR="/tmp-apptainer/tmp"
ARG APPTAINER_CACHEDIR="/tmp-apptainer/cache"
ARG MCONFIG_OPTIONS="--with-suid" 
RUN export GOVERSION=1.23.0 OS=linux ARCH=amd64 \
    && wget -O /tmp/go${GOVERSION}.${OS}-${ARCH}.tar.gz \
    https://dl.google.com/go/go${GOVERSION}.${OS}-${ARCH}.tar.gz \
    && tar -C /usr/local -xzf /tmp/go${GOVERSION}.${OS}-${ARCH}.tar.gz
ADD "https://api.github.com/repos/apptainer/apptainer/commits?per_page=1" latest_commit
RUN export PATH=$PATH:/usr/local/go/bin \ 
    && git clone --depth 1 --branch ${APPTAINER_COMMITISH} https://github.com/apptainer/apptainer.git \
    && cd apptainer \
    && ./mconfig $MCONFIG_OPTIONS -p /usr/local/apptainer \
    && cd builddir \
    && make \
    && make install \
    && cd .. \
    && ./scripts/download-dependencies \
    && ./scripts/compile-dependencies \
    && ./scripts/install-dependencies
ENTRYPOINT ["/usr/local/apptainer/bin/apptainer"]