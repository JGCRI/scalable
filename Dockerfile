# syntax=docker/dockerfile:1
FROM ubuntu:22.04 AS build_env

RUN apt-get -y update && DEBIAN_FRONTEND=noninteractive apt-get install -y wget unzip openjdk-11-jdk-headless \
build-essential libtbb-dev libboost-dev libboost-filesystem-dev libboost-system-dev
RUN apt-get -y update && apt -y upgrade
RUN DEBIAN_FRONTEND=noninteractive apt-get install -y python3 python3-pip python3-numpy libboost-python-dev \
libboost-numpy-dev
RUN apt-get -y update && apt -y upgrade
RUN apt-get -y update && DEBIAN_FRONTEND=noninteractive apt-get install -y ssh nano locate curl net-tools netcat git \
python3 python3-pip python3-numpy python3-dev gcc libboost-python1.74 libboost-numpy1.74 openjdk-11-jre-headless \
libtbb12 rsync
RUN python3 -m pip install dask[complete] dask-jobqueue --upgrade dask_mpi pyyaml joblib

FROM build_env as rbase
RUN apt-get -y update && apt -y upgrade
RUN apt-get install r-base r-base-dev -y
RUN apt-get install -y python3-rpy2

FROM build_env as scalable
ADD "https://api.github.com/repos/JGCRI/scalable/commits?per_page=1" latest_commit
RUN git clone https://github.com/JGCRI/scalable.git /scalable
RUN pip3 install /scalable/.

FROM build_env AS demeter
RUN apt-get -y update && apt -y upgrade
RUN python3 -m pip install git+http://github.com/JGCRI/demeter.git#egg=demeter
RUN mkdir /demeter
RUN echo "import demeter" >> /demeter/install_script.py && \
echo "demeter.get_package_data(\"/demeter\")" >> /demeter/install_script.py
RUN python3 /demeter/install_script.py
COPY --from=scalable /scalable /scalable
RUN pip3 install /scalable/.

FROM build_env AS stitches
RUN apt-get -y update && apt -y upgrade
RUN python3 -m pip install git+https://github.com/JGCRI/stitches.git
RUN mkdir /stitches
RUN echo "import stitches" >> /stitches/install_script.py && \
echo "stitches.install_package_data()" >> /stitches/install_script.py
RUN python3 /stitches/install_script.py
COPY --from=scalable /scalable /scalable
RUN pip3 install /scalable/.

FROM build_env AS tethys
RUN apt-get -y update && apt -y upgrade
RUN python3 -m pip install git+https://github.com/JGCRI/tethys
RUN mkdir /tethys
RUN echo "import tethys" >> /tethys/install_script.py && \
echo "tethys.get_example_data()" >> /tethys/install_script.py
RUN python3 /tethys/install_script.py
COPY --from=scalable /scalable /scalable
RUN pip3 install /scalable/.

FROM build_env AS xanthos
RUN apt-get -y update && apt -y upgrade
RUN mkdir /xanthos
RUN git clone --depth 1 https://github.com/JGCRI/xanthos.git /xanthos
RUN cd /xanthos && sed -i 's/numpy~=/numpy>=/g' setup.py 
RUN pip install /xanthos
RUN echo "import xanthos" >> /xanthos/install_script.py && \
echo "xanthos.get_package_data(\"/xanthos\")" >> /xanthos/install_script.py
RUN python3 /xanthos/install_script.py
COPY --from=scalable /scalable /scalable
RUN pip3 install /scalable/.

FROM rbase AS hector
RUN apt-get -y update && apt -y upgrade
RUN python3 -m pip install pyhector
COPY --from=scalable /scalable /scalable
RUN pip3 install /scalable/.

FROM build_env AS gcam
RUN apt-get -y update && apt -y upgrade
ARG EIGEN_VERSION=3.4.0
RUN git clone --depth 1 --branch gcam-v7.0 https://github.com/JGCRI/gcam-core.git /gcam-core
RUN mkdir gcam-core/libs
RUN wget https://gitlab.com/libeigen/eigen/-/archive/${EIGEN_VERSION}/eigen-${EIGEN_VERSION}.tar.gz -P /gcam-core/libs/.
RUN cd /gcam-core/libs && tar -xvf eigen-${EIGEN_VERSION}.tar.gz && mv eigen-${EIGEN_VERSION} eigen
ARG JARS_LINK=https://github.com/JGCRI/modelinterface/releases/download/v5.4/jars.zip
RUN wget ${JARS_LINK} -P /gcam-core && cd /gcam-core && unzip jars.zip && rm /gcam-core/jars.zip
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
RUN cd /gcam-core && git submodule init cvs/objects/climate/source/hector && \
git submodule update cvs/objects/climate/source/hector
RUN cd /gcam-core && make install_hector
RUN cd /gcam-core/cvs/objects/build/linux && make -j 4 gcam
RUN cp /gcam-core/exe/gcam.exe /usr/local/bin/gcam
RUN apt-get -y update && apt -y upgrade
ENV GCAM_INCLUDE=/gcam-core/cvs/objects \
    GCAM_LIB=/gcam-core/cvs/objects/build/linux
RUN git clone --branch GIL_Changes https://github.com/JGCRI/gcamwrapper.git /gcamwrapper
RUN cd /gcamwrapper && pip3 install .
RUN pip install gcamreader
RUN git clone https://github.com/JGCRI/gcam_config.git /gcam_config
RUN pip3 install /gcam_config/. 
COPY --from=scalable /scalable /scalable
RUN pip3 install /scalable/.


FROM golang:1.22.1-alpine3.19 as builder

RUN apk add --no-cache \
        # Required for apptainer to find min go version
        bash \
        cryptsetup \
        gawk \
        gcc \
        git \
        libc-dev \
        linux-headers \
        libressl-dev \
        libuuid \
        libseccomp-dev \
        make \
        util-linux-dev

ARG APPTAINER_COMMITISH="main"
ARG APPTAINER_TMPDIR="/tmp-apptainer"
ARG APPTAINER_CACHEDIR="/tmp-apptainer"
ARG MCONFIG_OPTIONS="--with-suid"
WORKDIR $GOPATH/src/github.com/apptainer
ADD "https://api.github.com/repos/apptainer/apptainer/commits?per_page=1" latest_commit
RUN git clone https://github.com/apptainer/apptainer.git \
    && cd apptainer \
    && git checkout "$APPTAINER_COMMITISH" \
    && ./mconfig $MCONFIG_OPTIONS -p /usr/local/apptainer \
    && cd builddir \
    && make \
    && make install

FROM alpine:latest AS apptainer
COPY --from=builder /usr/local/apptainer /usr/local/apptainer
ENV PATH="/usr/local/apptainer/bin:$PATH" \
    APPTAINER_TMPDIR=${APPTAINER_TMPDIR} \
    APPTAINER_CACHEDIR=${APPTAINER_CACHEDIR}
RUN apk add --no-cache ca-certificates libseccomp squashfs-tools tzdata \
    && mkdir -p $APPTAINER_TMPDIR \
    && cp /usr/share/zoneinfo/UTC /etc/localtime \
    && apk del tzdata \
    && rm -rf /tmp/* /var/cache/apk/*
WORKDIR /work
ENTRYPOINT ["/usr/local/apptainer/bin/apptainer"]