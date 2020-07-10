#!/usr/bin/env bash

main () {
    progname=$0
    progdir=$(dirname "${progname}")
    project_dir=$(cd "${progdir}" && pwd)

    pyfaros_version=`bash "${project_dir}/create_version.sh"`
    cd ${project_dir} && python3 "./setup.py" sdist bdist_wheel
    pyfaros_package="${project_dir}/dist/pyfaros-${pyfaros_version}.tar.gz"
    echo "Packaged ${pyfaros_package}"
    cp "${pyfaros_package}" "${project_dir}/pyfaros.tar.gz"
}

main "$*" || exit $?

exit 0
