# The recipes of the python profile that every Python project has. jnprofile-python installs this file.

# uv runs the helper script of the steps, steps.py, with Python 3.11 or later and no package. docstring-check runs it
# in the environment of the project instead, which can have Python 3.9 or later
python_run := "uv run --no-project --quiet --python '>=3.11' python"
python_steps := quote(source_directory() / "steps.py")

# Install Python and every dependency into .venv, as the lockfile says
setup:
    uv sync

# pytest for test, cov and integration, with coverage: test and integration write their reports for coverage-check,
# and cov shows the report. test and integration are steps of just check, and jlog logs only the lines of a recipe
# with no shebang line, so each runs this script in one line, through just. module_file() is the file of this
# module, and just runs it in the folder of the project, so the line works also when another Justfile loads this
# project. test and cov leave out tests/integration. integration runs only tests/integration when it gets no
# argument, and with no such folder it passes.
# pytest exits 5 when no test runs. With arguments that is a miss, and it fails. With none, it passes only when pytest
# finds no test file at all: with addopts and PYTEST_ADDOPTS off, and with its summary saying so, because a conftest
# hook that removes every test also exits 5. A coverage gate such as fail_under still fails it.
_pytest name *args:
    #!/usr/bin/env sh
    name="$1"; shift
    given=$#
    # Without the integration tool, nothing else runs tests/integration, so test and cov run it.
    where=--ignore=tests/integration
    printf '%s\n' $(just --justfile {{quote(module_file())}} --summary) | grep -qx integration || where=--ignore=.jnprofile-python
    case "$name" in
        cov) set -- --cov --cov-report=term-missing "$where" "$@" ;;
        test)
            # A data file of its own, which begin deletes, so an --cov-append of the project adds to no old run.
            export COVERAGE_FILE=.jnprofile-python/.coverage
            set -- --cov --cov-report=xml:.jnprofile-python/coverage.xml "$where" "$@" ;;
        integration)
            where=tests/integration
            if [ "$given" -eq 0 ]; then
                [ -d tests/integration ] || { echo "just integration: no integration tests yet, in tests/integration"; exit 0; }
                set -- tests/integration
            fi
            export COVERAGE_FILE=.jnprofile-python/.coverage-integration
            set -- --cov --cov-report=xml:.jnprofile-python/integration.xml "$@" ;;
        *) echo "_pytest: no run named $name"; exit 2 ;;
    esac
    uv run pytest "$@" && exit 0 || code=$?
    if [ "$code" -eq 5 ] && [ "$given" -eq 0 ]; then
        out=$(PYTEST_ADDOPTS= uv run pytest --collect-only -q -o addopts= "$where" 2>&1) || all=$?
        if [ "${all:-0}" -eq 5 ] && printf '%s\n' "$out" | grep -q '^no tests collected in '; then
            echo "just $name: no tests yet"; exit 0
        fi
    fi
    exit "$code"
