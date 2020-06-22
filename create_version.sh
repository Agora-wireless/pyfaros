#!/usr/bin/env bash

version="0.0.4"

main () {
    progname=$0
    progdir=$(dirname "${progname}")
    project_dir=$(cd "${progdir}" && pwd)

    sha=`git rev-parse HEAD`
    subsha="${sha:0:8}"

    echo "pyfaros_version=\"${version}+${subsha}\"" > "${project_dir}/version.py"
}

main "$*" || exit $?

exit 0
