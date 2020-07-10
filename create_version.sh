#!/usr/bin/env bash

version="0.0.4"

main () {
    progname=$0
    progdir=$(dirname "${progname}")
    project_dir=$(cd "${progdir}" && pwd)

    sha=`git rev-parse HEAD`
    subsha="${sha:0:8}"

    pyfaros_version="${version}+${subsha}"
    echo "pyfaros_version=\"${pyfaros_version}\"" > "${project_dir}/version.py"
    echo $pyfaros_version
}

main "$*" || exit $?

exit 0
