#!/usr/bin/env bash

### EDITABLE CONSTANTS ###

GO_VERSION_LINK="https://go.dev/VERSION?m=text"
GO_DOWNLOAD_LINK="https://go.dev/dl/*.linux-amd64.tar.gz"
SCALABLE_REPO="https://github.com/JGCRI/scalable.git"
APPTAINER_VERSION="1.3.2"
DEFAULT_PORT="1919"
CONFIG_FILE="/tmp/.scalable_config"

# set -x

set -o pipefail

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[0;33m'
NC='\033[0m'

if [[ $* == *"-i"* ]]; then
    while getopts ":i:" flag; do
        case $flag in
        i)
            echo -e "${YELLOW}Found Identity${NC}"
            alias ssh='ssh -i $OPTARG'
        ;;
        esac
    done
fi

### FUNCTIONS ###

### check_exit_code: checks the exit code of the last command and exits if it is non-zero

check_exit_code() {
    if [ $1 -ne 0 ]; then
        echo -e "${RED}Command failed with exit code $1${NC}"
        echo -e "${RED}Exiting...${NC}"
        exit $1
    fi
}

### prompt: prompts the user for input

prompt() {
    local color="$1"
    local prompt_text="$2"
    echo -e -n "${color}${prompt_text}${NC}"
    read input
}

### flush: flushes the input buffer

flush() {
    read -t 0.1 -n 10000 discard
}

echo -e "${RED}Connection to HPC/Cloud...${NC}"

choice="N"

if [[ -f $CONFIG_FILE ]]; then
    echo -e "${YELLOW}Found saved configuration file${NC}"
    flush
    prompt "$RED" "Do you want to use the saved configuration? (Y/n): "
    choice=$input
fi

if [[ "$choice" =~ [Yy]|^[Yy][Ee]|^[Yy][Ee][Ss]$ ]]; then
    source $CONFIG_FILE
    check_exit_code $?
else
    flush
    prompt "$RED" "Hostname: "
    host=$input
    flush
    prompt "$RED" "Username: "
    user=$input

    flush
    prompt "$RED" "Enter Remote Work Directory Name (created in home directory of remote system/if one exists): "
    work_dir=$input

    flush
    prompt "$RED" "Do you want to save the username, hostname, and work directory for future use? (Y/n): "
    save=$input

    if [[ "$save" =~ [Yy]|^[Yy][Ee]|^[Yy][Ee][Ss]$ ]]; then
        rm -f $CONFIG_FILE
        check_exit_code $?
        echo -e "host=$host\nuser=$user\nwork_dir=$work_dir" > $CONFIG_FILE
        check_exit_code $?
    fi
fi

### Go version is set to latest ###
GO_VERSION=$(ssh $user@$host "curl -s $GO_VERSION_LINK | head -n 1 | tr -d '\n'")
check_exit_code $?

DOWNLOAD_LINK="${GO_DOWNLOAD_LINK//\*/$GO_VERSION}"

FILENAME=$(basename $DOWNLOAD_LINK)
check_exit_code $?

echo -e "${GREEN}To prevent local environment setup every time on launch, please run the \
scalable_bootstrap script from the same directory each time.${NC}"

if [[ ! -f "Dockerfile" ]]; then
    flush
    echo -e "${YELLOW}Dockefile not found in current directory. Downloading default Dockerfile from remote...${NC}"
    curl -O "https://raw.githubusercontent.com/JGCRI/scalable/master/scalable/Dockerfile"
    check_exit_code $?
fi

prompt "$RED" "Do you want to build and transfer containers? (Y/n): "
transfer=$input
build=()
if [[ "$transfer" =~ [Yy]|^[Yy][Ee]|^[Yy][Ee][Ss]$ ]]; then
    echo -e "${YELLOW}Available container targets: ${NC}"
    avail=$(sed -n -E 's/^FROM[[:space:]]{1,}[^ ]{1,}[[:space:]]{1,}AS[[:space:]]{1,}([^ ]{1,})$/\1/p' Dockerfile)
    check_exit_code $?
    avail=$(sed -E '/build_env/d ; /scalable/d ; /apptainer/d' <<< "$avail")
    check_exit_code $?
    echo -e "${GREEN}$avail${NC}"
    echo -e \
    "${RED}Please enter the containers you'd like to build and upload to the remote system (separated by spaces): ${NC}"
    flush
    read -r -a targets
    check_exit_code $?
    echo -e "${RED}Checking if entered container names are valid... ${NC}"
    for target in "${targets[@]}"
    do
        echo "$avail" | grep "$target"
        check_exit_code $?
    done
    targets+=('scalable')
    for target in "${targets[@]}"
    do
        check=$target\_container
        ssh $user@$host "[[ -f \"$work_dir/containers/$check.sif\" ]]"
        if [ "$?" -eq 0 ]; then
            echo -e "${YELLOW}$check.sif already exists in $work_dir/containers.${NC}"
            flush
            prompt "$RED" "Do you want to overwrite $check.sif? (Y/n): "
            choice=$input
            if [[ "$choice" =~ [Nn]|^[Nn][Oo]$ ]]; then
                continue
            fi
        fi
        build+=("$target")
    done
fi

echo -e "${YELLOW}To reinstall any directory or file already on remote, \
please delete it from remote and run this script again${NC}"

flush
ssh -t $user@$host \
"{
    if [[ -d \"$work_dir\" && -d \"$work_dir/logs\" ]]; then 
        echo '$work_dir already exists on remote'
    else 
        mkdir -p $work_dir
        mkdir -p $work_dir/logs
    fi
} &&
{
    if [[ -d \"$work_dir/go\" ]]; then
        echo '$work_dir/go already exists on remote' 
    else 
        echo 'go directory not found on remote...installing version $GO_VERSION (likely latest)' &&
        wget $DOWNLOAD_LINK -P $work_dir && 
        tar -C $work_dir -xzf $work_dir/$FILENAME
    fi
} &&
{
    if [[ -d \"$work_dir/scalable\" ]]; then
        echo '$work_dir/scalable already exists on remote'
    else
        git clone $SCALABLE_REPO $work_dir/scalable
    fi
} &&
{ 
    if [[ -f \"$work_dir/communicator\" ]]; then
        echo '$work_dir/communicator file already exists on remote'
    elif [[ -f \"$work_dir/scalable/communicator/communicator\" ]]; then 
        cp $work_dir/scalable/communicator/communicator $work_dir/.
    else
        cd $work_dir/scalable/communicator && 
        ../../go/bin/go mod init communicator && 
        ../../go/bin/go build src/communicator.go &&
        cp communicator ../../.
    fi
}"
check_exit_code $?

HTTPS_PROXY="http://proxy01.pnl.gov:3128"
NO_PROXY="*.pnl.gov,*.pnnl.gov,127.0.0.1"
# leaving these in; but local apptainer does NOT utilize a cache/tmp directory for now
mkdir -p tmp-apptainer
mkdir -p tmp-apptainer/tmp
mkdir -p tmp-apptainer/cache
APPTAINER_TMPDIR="/tmp-apptainer/tmp"
APPTAINER_CACHEDIR="/tmp-apptainer/cache"

ssh $user@$host "[[ -f $work_dir/containers/scalable_container.sif ]]"
exist=$(echo $?)
if [[ "$exist" -eq 0 ]]; then
    docker images | grep scalable_container
    exist=$(echo $?)
fi
if [[ "$exist" -ne 0 ]]; then
    echo -e "${YELLOW}Scalable container not found locally or on remote. Building and transferring...${NC}"
    transfer=Y
    build+=("scalable")
fi

if [[ "$transfer" =~ [Yy]|^[Yy][Ee]|^[Yy][Ee][Ss]$ ]]; then

    flush
    mkdir -p containers
    check_exit_code $?
    mkdir -p cache
    check_exit_code $?
    mkdir -p run_scripts
    check_exit_code $?

    rebuild="false"
    docker images | grep apptainer_container
    if [ "$?" -ne 0 ]; then
        rebuild="true"
    fi
    current_version=$(docker run --rm apptainer_container version)
    if [ "$current_version" != "$APPTAINER_VERSION" ]; then
        rebuild="true"
    fi
    if [ "$rebuild" == "true" ]; then
        flush
        APPTAINER_COMMITISH="v$APPTAINER_VERSION"
        docker build --target apptainer --build-arg APPTAINER_COMMITISH=$APPTAINER_COMMITISH \
        --build-arg APPTAINER_TMPDIR=$APPTAINER_TMPDIR --build-arg APPTAINER_CACHEDIR=$APPTAINER_CACHEDIR \
        -t apptainer_container .
        check_exit_code $?
    fi

    for target in "${build[@]}"
    do
        flush
        docker build --target $target -t $target\_container .
        check_exit_code $?
        
        flush
        docker run --rm --mount type=bind,source=/$(pwd)/run_scripts,target=/run_scripts $target\_container \
        bash -c "cp /root/.bashrc /run_scripts/$target\_script.sh"
        check_exit_code $?

        flush
        sed -i '1i#!/bin/bash' run_scripts/$target\_script.sh
        check_exit_code $?

        flush
        echo "\"\$@\"" >> run_scripts/$target\_script.sh
        check_exit_code $?

        flush
        chmod +x run_scripts/$target\_script.sh
        check_exit_code $?

        flush
        IMAGE_NAME=$(docker images | grep $target\_container | sed -E 's/[\t ][\t ]*/ /g' | cut -d ' ' -f 1)
        IMAGE_TAG=$(docker images | grep $target\_container | sed -E 's/[\t ][\t ]*/ /g' | cut -d ' ' -f 2)
        
        flush
        docker run --rm -v //var/run/docker.sock:/var/run/docker.sock -v /$(pwd):/work -v /$(pwd)/tmp-apptainer:/tmp-apptainer \
        apptainer_container build --userns --force //work/containers/$target\_container.sif docker-daemon://$IMAGE_NAME:$IMAGE_TAG
        check_exit_code $?
    done
    
fi

SHELL="bash"
RC_FILE="~/.bashrc"

flush
docker run --rm -v /$(pwd):/host -v /$HOME/.ssh:/root/.ssh scalable_container \
    bash -c "chmod 700 /root/.ssh && chmod 600 ~/.ssh/* \
    && cd /host \
    && (rsync -aP --include '*.sif' containers $user@$host:~/$work_dir || true) \
    && (rsync -aP --include '*.sh' run_scripts $user@$host:~/$work_dir || true) \
    && rsync -aP Dockerfile $user@$host:~/$work_dir"
check_exit_code $?

COMM_PORT=$DEFAULT_PORT
ssh $user@$host "netstat -tuln | grep :$COMM_PORT"
while [[ $? -eq 0 && "$COMM_PORT" != "8787" ]]; do
    COMM_PORT=$(awk -v min=1024 -v max=49151 'BEGIN{srand(); print int(min+rand()*(max-min+1))}')
    check_exit_code $?
    ssh $user@$host "netstat -tuln | grep :$COMM_PORT"
done

ssh $user@$host "netstat -tuln | grep :8787"
if [ $? -eq 0 ]; then
    echo -e "${RED}Port 8787 is already in use on remote system${NC}"
    echo -e "${YELLOW}Not forwarding port 8787, dask dashboard may be unavailable...${NC}"
    connect="ssh"
else
    connect="ssh -L 8787:$host:8787"
fi

$connect -t $user@$host \
"{
    module load apptainer/$APPTAINER_VERSION && 
    cd $work_dir &&
    $SHELL --rcfile <(echo \". $RC_FILE; 
    python3() {
        ./communicator -s $COMM_PORT >> logs/communicator.log &
        COMMUNICATOR_PID=\\\$!
        apptainer exec --userns --compat --env COMM_PORT=$COMM_PORT --home ~/$work_dir --cwd ~/$work_dir ~/$work_dir/containers/scalable_container.sif python3 \\\$@
        kill -9 \\\$COMMUNICATOR_PID
    } \" ); 
}"
