# The test tool of the python profile: pytest and pytest-cov. just install test adds it, and jnprofile-python
# installs this file.

# Run the tests. Extra arguments go to pytest: just test tests/unit. Alone, a project with no tests yet passes
test *args:
    #!/usr/bin/env sh
    # pytest exits 5 when no test runs. With arguments that is a miss, and it fails. With none, it passes only when
    # pytest finds no test file at all: with addopts and PYTEST_ADDOPTS off, and with its summary saying so, because a
    # conftest hook that removes every test also exits 5. A coverage gate such as fail_under still fails it.
    uv run pytest "$@" && exit 0 || code=$?
    if [ "$code" -eq 5 ] && [ "$#" -eq 0 ]; then
        out=$(PYTEST_ADDOPTS= uv run pytest --collect-only -q -o addopts= 2>&1) || all=$?
        if [ "${all:-0}" -eq 5 ] && printf '%s\n' "$out" | grep -q '^no tests collected in '; then
            echo "just test: no tests yet"; exit 0
        fi
    fi
    exit "$code"

# Run the tests, and show which lines they ran. Alone, a project with no tests yet passes, as for just test
cov *args:
    #!/usr/bin/env sh
    uv run pytest --cov --cov-report=term-missing "$@" && exit 0 || code=$?
    if [ "$code" -eq 5 ] && [ "$#" -eq 0 ]; then
        out=$(PYTEST_ADDOPTS= uv run pytest --collect-only -q -o addopts= 2>&1) || all=$?
        if [ "${all:-0}" -eq 5 ] && printf '%s\n' "$out" | grep -q '^no tests collected in '; then
            echo "just cov: no tests yet"; exit 0
        fi
    fi
    exit "$code"
