# The test tool of the python profile: pytest and pytest-cov. just install test adds it, and jnprofile-python
# installs this file.

# Run the tests. Extra arguments go to pytest: just test tests/unit. Alone, a project with no tests yet passes
test *args:
    just --justfile {{quote(module_file())}} _pytest test "$@"

# Run the tests, and show which lines they ran. Alone, a project with no tests yet passes, as for just test
cov *args:
    just --justfile {{quote(module_file())}} _pytest cov "$@"

# pytest for test and cov. test is a step of just check, and jlog logs only the lines of a recipe with no shebang
# line, so test runs this script in one line, through just. module_file() is the file of this module, and
# just runs it in the folder of the project, so the line works also when another Justfile loads this project.
# pytest exits 5 when no test runs. With arguments that is a miss, and it fails. With none, it passes only when pytest
# finds no test file at all: with addopts and PYTEST_ADDOPTS off, and with its summary saying so, because a conftest
# hook that removes every test also exits 5. A coverage gate such as fail_under still fails it.
_pytest name *args:
    #!/usr/bin/env sh
    name="$1"; shift
    if [ "$name" = cov ]; then set -- --cov --cov-report=term-missing "$@"; given=$(($# - 2)); else given=$#; fi
    uv run pytest "$@" && exit 0 || code=$?
    if [ "$code" -eq 5 ] && [ "$given" -eq 0 ]; then
        out=$(PYTEST_ADDOPTS= uv run pytest --collect-only -q -o addopts= 2>&1) || all=$?
        if [ "${all:-0}" -eq 5 ] && printf '%s\n' "$out" | grep -q '^no tests collected in '; then
            echo "just $name: no tests yet"; exit 0
        fi
    fi
    exit "$code"
