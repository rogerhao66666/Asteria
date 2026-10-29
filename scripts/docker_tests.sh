#!/usr/bin/env bash
# The test suite on a clean Linux machine (Docker), one Python version after another.
#
#   scripts/docker_tests.sh                    # Python 3.12 and 3.13, the whole suite
#   scripts/docker_tests.sh 3.12               # one version
#   scripts/docker_tests.sh 3.13 -- -x tests/test_mouse_control.py   # pytest arguments
#   PINS="PySide6==6.11.2" scripts/docker_tests.sh 3.13              # other package versions
#   scripts/docker_tests.sh --commit HEAD 3.13   # exactly one commit
#
# The container gets only the files git knows (tracked, plus new files not ignored), so a
# test that leans on something that exists only on this Mac (an ignored file, a path under
# /Users, a font, a package missing from pyproject.toml) fails here. With --commit it gets
# that commit's files and nothing else - what a fresh clone has, untouched by work other
# sessions have not committed. Lint (ruff) runs first.
# Sound is off and the windows are offscreen. One container at a time keeps the memory low.
set -euo pipefail
cd "$(dirname "$0")/.."

commit=""
if [[ "${1:-}" == "--commit" ]]; then
    commit="$(git rev-parse --verify "${2:?--commit needs a revision}^{commit}")"
    shift 2
fi
versions=()
while [[ $# -gt 0 && "$1" != "--" ]]; do
    versions+=("$1")
    shift
done
[[ "${1:-}" == "--" ]] && shift
[[ ${#versions[@]} -eq 0 ]] && versions=(3.12 3.13)
pytest_args=("$@")
[[ ${#pytest_args[@]} -eq 0 ]] && pytest_args=(tests -q -p no:cacheprovider)
pins="${PINS:-}"

project_files() {
    if [[ -n "${commit}" ]]; then
        git archive --format=tar "${commit}"
    else
        # COPYFILE_DISABLE: macOS tar leaves out its ._ files (Linux would read them as code)
        git ls-files -z -co --exclude-standard | COPYFILE_DISABLE=1 tar --null -T - -cf -
    fi
}

status=0
for version in "${versions[@]}"; do
    tag="asteria-tests:py${version}${pins:+-pinned}"
    echo "== Python ${version}${pins:+ ($pins)}${commit:+, commit ${commit:0:8}}: image ${tag}"
    docker build -q -f docker/Dockerfile --build-arg PYTHON="${version}" \
        --build-arg PINS="${pins}" -t "${tag}" . >/dev/null
    if project_files \
        | docker run -i --rm "${tag}" bash -c '
            set -e
            tar -xf - -C /work
            pip install --no-cache-dir --no-deps -q -e .
            ruff check -q src scripts tests reference_projects
            ruff format -q --check src scripts tests reference_projects
            python -m pytest "$@"' _ "${pytest_args[@]}"; then
        echo "== Python ${version}: passed"
    else
        echo "== Python ${version}: FAILED"
        status=1
    fi
done
exit "${status}"
