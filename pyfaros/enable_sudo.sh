#!/bin/sh
if [ -z "$1" ]; then
    echo "Starting up visudo with this script as first parameter"
    export EDITOR=$0 && sudo -E visudo
else
    if [ -z "$2" ]; then
        filename=$1
    else
        filename=$2
    fi
    echo "Changing sudoers $filename"
    echo "sklk ALL=(ALL) NOPASSWD: ALL" >> $filename
fi
