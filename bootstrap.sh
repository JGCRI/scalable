#!/bin/bash

GO_VERSION_LINK="https://go.dev/VERSION?m=text"
GO_DOWNLOAD_LINK="https://go.dev/dl/*.linux-amd64.tar.gz"
SCALABLE_REPO="https://github.com/JGCRI/scalable.git"

# set -x

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[0;33m'
NC='\033[0m'

prompt() {
    local color="$1"
    local prompt_text="$2"
    echo -e -n "${color}${prompt_text}${NC}" # Print prompt in specified color
    read input
}

flush() {
    read -t 0.1 -n 10000 discard
}

echo -e "${RED}Connection to HPC/Cloud...${NC}"
flush
prompt "$RED" "Hostname: "
host=$input
flush
prompt "$RED" "Username: "
user=$input
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

check_exit_code() {
    if [ $1 -ne 0 ]; then
        echo -e "${RED}Command failed with exit code $1${NC}"
        echo -e "${RED}Exiting...${NC}"
        exit $1
    fi
}

GO_VERSION=$(ssh $user@$host "curl -s $GO_VERSION_LINK | head -n 1 | tr -d '\n'")
check_exit_code $?

DOWNLOAD_LINK="${GO_DOWNLOAD_LINK//\*/$GO_VERSION}"

FILENAME=$(basename $DOWNLOAD_LINK)
check_exit_code $?

flush
prompt "$RED" "Enter Work Directory Name \
(created in home directory of remote system or if it already exists): "
work_dir=$input

prompt "$RED" "Do you want to build and transfer containers? (Y/n): "
build=$input
if [[ "$build" =~ [Yy]|^[Yy][Ee]|^[Yy][Ee][Ss]$ ]]; then
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
fi

echo -e "${YELLOW}To reinstall any directory or file already on remote, \
please delete it from remote and run this script again${NC}"

flush
ssh $user@$host \
"{
    [[ -d \"$work_dir\" ]] && 
    echo '$work_dir already exists on remote'
} || 
{
    mkdir -p $work_dir
}"
check_exit_code $?

flush
ssh -t $user@$host \
"{
    [[ -d \"$work_dir/go\" ]] && 
    echo '$work_dir/go already exists on remote' 
} || 
{
    wget $DOWNLOAD_LINK -P $work_dir && 
    tar -C $work_dir -xzf $work_dir/$FILENAME
}"
check_exit_code $?

flush
ssh $user@$host \
"{
    [[ -d \"$work_dir/scalable\" ]] && 
    echo '$work_dir/scalable already exists on remote'
} ||
{
    git clone $SCALABLE_REPO $work_dir/scalable
}"
check_exit_code $?

GO_PATH=$(ssh $user@$host "cd $work_dir/go/bin/ && pwd")
GO_PATH="$GO_PATH/go"
flush
ssh -t $user@$host \
"{ 
    [[ -f \"$work_dir/scalable/communicator/communicator\" ]] && 
    echo '$work_dir/scalable/communicator/communicator file already exists on remote' 
} || 
{
    cd $work_dir/scalable/communicator && 
    $GO_PATH mod init communicator && 
    $GO_PATH build src/communicator.go &&
    cd &&
    cp $work_dir/scalable/communicator/communicator $work_dir/.
}"
check_exit_code $?

flush
ssh $user@$host "cp $work_dir/scalable/communicator/communicator $work_dir/."
check_exit_code $?

HTTPS_PROXY="http://proxy01.pnl.gov:3128"
NO_PROXY="*.pnl.gov,*.pnnl.gov,127.0.0.1"

if [[ "$build" =~ [Yy]|^[Yy][Ee]|^[Yy][Ee][Ss]$ ]]; then

    flush
    echo 'Creating container directory locally...'
    mkdir -p containers
    check_exit_code $?

    targets+=('scalable')
    build=()
    for target in "${targets[@]}"
    do
        check=$target\_container
        ssh $user@$host "[[ -f \"$work_dir/containers/$check.sif\" ]]"
        if [ "$?" -eq 0 ]; then
            echo -e "${YELLOW}$check.sif already exists in $work_dir/containers.${NC}"
            flush
            prompt "$RED" "Do you want to overwrite $check.sif & $check.tar? (Y/n): "
            choice=$input
            if [[ "$choice" =~ [Nn]|^[Nn][Oo]$ ]]; then
                continue
            fi
        fi
        flush
        docker build --target $target --build-arg https_proxy=$HTTPS_PROXY \
        --build-arg no_proxy=$NO_PROXY -t $target\_container .
        check_exit_code $?
        flush
        build+=("$target")
    done

    docker images | grep apptainer_container
    if [ "$?" -ne 0 ]; then
        flush
        docker build --target apptainer --build-arg https_proxy=$HTTPS_PROXY \
        --build-arg no_proxy=$NO_PROXY -t container_container .
        check_exit_code $?
    fi

    for target in "${build[@]}"
    do
        flush
        IMAGE_NAME=$(docker images | grep $target\_container | sed -E 's/[\t ][\t ]*/ /g' | cut -d ' ' -f 1)
        IMAGE_TAG=$(docker images | grep $target\_container | sed -E 's/[\t ][\t ]*/ /g' | cut -d ' ' -f 2)
        flush
        docker run --rm -v //var/run/docker.sock:/var/run/docker.sock -v /$(pwd):/work \
        apptainer_container build containers/$target\_container.sif docker-daemon://$IMAGE_NAME:$IMAGE_TAG
        check_exit_code $?
    done

    rsync -aP --include '*.sif' containers $user@$host:~/$work_dir
    check_exit_code $?
    
fi

ssh -L 8787:deception.pnl.gov:8787 -t $user@$host \
"{
    cd $work_dir && 
    ./communicator -s > communicator.log & 
    module load apptainer && 
    cd $work_dir &&
    apptainer exec containers/scalable_container.sif python3
}"