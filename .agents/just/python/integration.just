# The integration tool of the python profile: pytest and pytest-cov, for the tests in tests/integration. just install
# integration adds it, and jnprofile-python installs this file.

# Run the integration tests in tests/integration with coverage, into .jnprofile-python/integration.xml. Extra
# arguments go to pytest in place of the folder: just integration tests/integration/test_db.py. With no folder
# tests/integration, it passes. When they passed before in this run of just, on this tree, they do not run again
integration *args:
    {{python_run}} {{python_steps}} ran integration "$@" || just --justfile {{quote(module_file())}} _integration "$@"

# The run of integration: the run ID and the tree go into .jnprofile-python, for coverage-check
_integration *args:
    {{python_run}} {{python_steps}} begin integration "$@"
    just --justfile {{quote(module_file())}} _pytest integration "$@"
    {{python_run}} {{python_steps}} stamp integration
