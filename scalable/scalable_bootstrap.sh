#!/bin/bash

GO_VERSION_LINK="https://go.dev/VERSION?m=text"
GO_DOWNLOAD_LINK="https://go.dev/dl/*.linux-amd64.tar.gz"
SCALABLE_REPO="https://github.com/JGCRI/scalable.git"
APPTAINER_VERSION="1.3.2"

# set -x

set -o pipefail

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

echo -e "${GREEN}To prevent local environment setup every time on launch, please run the \
scalable_bootstrap script from the same directory each time.${NC}"

prompt "$RED" "Do you want to build and transfer containers? (Y/n): "
transfer=$input
build=()
if [[ "$transfer" =~ [Yy]|^[Yy][Ee]|^[Yy][Ee][Ss]$ ]]; then
    if [[ ! -f "Dockerfile" ]]; then
        flush
        echo -e "${YELLOW}Dockefile not found in current directory. Downloading from remote...${NC}"
        wget "https://raw.githubusercontent.com/JGCRI/scalable/master/Dockerfile"
        check_exit_code $?
    fi
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
    [[ -d \"$work_dir\" ]] && 
    [[ -d \"$work_dir/logs\" ]] &&
    echo '$work_dir already exists on remote'
} || 
{
    mkdir -p $work_dir
    mkdir -p $work_dir/logs
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
ssh -t $user@$host \
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
    [[ -f \"$work_dir/communicator\" ]] && 
    echo '$work_dir/communicator file already exists on remote' &&
    [[ -f \"$work_dir/scalable/communicator/communicator\" ]] && 
    cp $work_dir/scalable/communicator/communicator $work_dir/.
} ||
{
    cd $work_dir/scalable/communicator && 
    $GO_PATH mod init communicator && 
    $GO_PATH build src/communicator.go &&
    cd &&
    cp $work_dir/scalable/communicator/communicator $work_dir/.
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

if [[ "$transfer" =~ [Yy]|^[Yy][Ee]|^[Yy][Ee][Ss]$ ]]; then

    flush
    mkdir -p containers
    check_exit_code $?
    mkdir -p cache
    check_exit_code $?
    mkdir -p run_scripts
    check_exit_code $?

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

    done

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
        IMAGE_NAME=$(docker images | grep $target\_container | sed -E 's/[\t ][\t ]*/ /g' | cut -d ' ' -f 1)
        IMAGE_TAG=$(docker images | grep $target\_container | sed -E 's/[\t ][\t ]*/ /g' | cut -d ' ' -f 2)
        flush
        docker run --rm -v //var/run/docker.sock:/var/run/docker.sock -v /$(pwd):/work -v /$(pwd)/tmp-apptainer:/tmp-apptainer \
        apptainer_container build --userns --force containers/$target\_container.sif docker-daemon://$IMAGE_NAME:$IMAGE_TAG
        check_exit_code $?
    done
    
fi

SHELL="bash"
RC_FILE="~/.bashrc"

flush
docker run --rm -v /$(pwd):/host -v /$HOME/.ssh:/root/.ssh scalable_container \
    bash -c "chmod 700 /root/.ssh && chmod 600 ~/.ssh/* \
    && cd /host \
    && rsync -aP --include '*.sif' containers $user@$host:~/$work_dir \
    && rsync -aP --include '*.sh' run_scripts $user@$host:~/$work_dir \
    && rsync -aP Dockerfile $user@$host:~/$work_dir"
check_exit_code $?

ssh -L 8787:deception.pnl.gov:8787 -t $user@$host \
"{
    module load apptainer/$APPTAINER_VERSION && 
    cd $work_dir &&
    $SHELL --rcfile <(echo \". $RC_FILE; 
    python3() {
        ./communicator -s >> logs/communicator.log &
        COMMUNICATOR_PID=\\\$!
        apptainer exec --userns --compat --home ~/$work_dir --cwd ~/$work_dir ~/$work_dir/containers/scalable_container.sif python3 \\\$@
        kill -9 \\\$COMMUNICATOR_PID
    } \" ); 
}"
