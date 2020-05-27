#!/usr/bin/env bash

main () {
    progname=$0
    progdir=$(dirname "${progname}")
    project_dir=$(cd "${progdir}" && pwd)

    bash "${project_dir}/create_version.sh"
    cd ${project_dir} && python3 "./setup.py" sdist bdist_wheel
}

main "$*" || exit $?

exit 0
