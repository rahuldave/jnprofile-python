# The test tool of the python profile: pytest and pytest-cov. just install test adds it, and jnprofile-python
# installs this file.

# Run the tests with coverage, into .jnprofile-python/coverage.xml. Extra arguments go to pytest: just test tests/unit.
# Alone, a project with no tests yet passes, and the run saves JLOG_RUN for coverage-check. The integration tests in
# tests/integration run here only without the integration tool, which runs them
test *args:
    {{python_run}} {{python_steps}} begin test "$@"
    just --justfile {{quote(module_file())}} _pytest test "$@"
    {{python_run}} {{python_steps}} stamp test

# Fail on each changed line of code that no test runs, and on the first commit on each line. It reads the report of
# test only from the same run of just, JLOG_RUN, and the same tree. Otherwise it runs the tests first. When the key
# steps of .agents/stack.json has integration and the integration tool is there, a line that only the integration
# tests run counts as run, and it runs them too when their report is not from this run
coverage-check:
    {{python_run}} {{python_steps}} fresh test {{quote(module_file())}} || just --justfile {{quote(module_file())}} test
    {{python_run}} {{python_steps}} fresh integration {{quote(module_file())}} || just --justfile {{quote(module_file())}} integration
    {{python_run}} {{python_steps}} coverage {{quote(module_file())}}

# Run the tests, and show which lines they ran. Alone, a project with no tests yet passes, as for just test. The
# integration tests do not run
cov *args:
    just --justfile {{quote(module_file())}} _pytest cov "$@"

# Run only the test files FILES, for test-parent of the commit gates. It exits with 0 when tests ran and passed, with
# 1 when a test fails or a file cannot be collected, as a new test of new code on the parent commit, and with 5 when
# no test runs, as for a file whose tests are all skipped or all xfail. Any other code means that uv or pytest itself
# failed, or that a test ended the run. With no file, it exits with 5 and runs nothing. The output ends with one line
# for each test, so a test that passes next to one that fails shows
[positional-arguments]
test-paths *files:
    #!/usr/bin/env sh
    [ "$#" -eq 0 ] && { echo "just test-paths: no test file"; exit 5; }
    # A shebang recipe of a module runs in the folder of the module, and the paths start at the project.
    cd {{quote(justfile_directory())}} || exit 2
    # uv makes the environment first, so a failed install is a failed runner, not a failed test.
    uv run true || { echo "just test-paths: uv cannot make the environment of the project"; exit 2; }
    tmp=$(mktemp -d); trap 'rm -rf "$tmp"' EXIT
    code=0
    PYTEST_ADDOPTS= uv run pytest -p no:cacheprovider -o addopts= \
        -rfEsxXp --continue-on-collection-errors --junitxml="$tmp/report.xml" -- "$@" > "$tmp/out" 2>&1 || code=$?
    cat "$tmp/out"
    # The report counts the tests that ran: a skipped or xfail test does not count. uv run true made the environment,
    # so the count runs with no sync. No report means that the run ended before pytest wrote it.
    ran=$(uv run --no-sync python -I -c 'import sys, xml.etree.ElementTree as t
    print(sum(c.find("skipped") is None for c in t.parse(sys.argv[1]).iter("testcase")))' "$tmp/report.xml" 2>/dev/null) || ran=
    case "$code" in
        0) [ -z "$ran" ] && exit 2; [ "$ran" -gt 0 ] && exit 0; exit 5 ;;
        1|5) [ -z "$ran" ] && exit 2; exit "$code" ;;
        2) grep -Eq 'errors? during collection' "$tmp/out" && exit 1; exit 2 ;;
        # A conftest.py that imports new code cannot load on the parent, and that is a failure of the test.
        4) grep -q 'ImportError while loading conftest' "$tmp/out" && exit 1; exit 2 ;;
        *) exit 2 ;;
    esac
