# The api tool of the python profile: smalldocs api check, for the API pages of the docs site. just install api adds
# it, and jnprofile-python installs this file. uv runs smalldocs in the environment of the project, which needs
# Python 3.11 or later.

# Fail on each function, method or class with no docstring, no type, or no docment: the comment after a parameter or
# after the return type. The settings are the key api of docs/_smalldocs.yml, or else the packages at the top of the
# project or in src/ and the module named after the project. Then run api-prose-check. The step docs-check of the
# docs role runs this recipe. Without that role, no step runs it
api-check:
    {{python_run}} {{python_steps}} api check
    just --justfile {{quote(module_file())}} api-prose-check

# Check the API page of each changed module with the checker of nossaifd. The page goes into a temporary folder,
# outside the project. A changed module changed since HEAD. In CI, or with --base REF, it changed since the base that
# check-changed of nossaifd takes, in the commits or in the working tree. Without the prose role, which installs the
# checker, it passes. When it passed before in this run of just, on this tree and with the same base, it does not
# run again, so api-check and prose-check can both call it
[positional-arguments]
api-prose-check *args:
    {{python_run}} {{python_steps}} ran prose "$@" || just --justfile {{quote(module_file())}} _api-prose-check "$@"

# The run of api-prose-check: the run ID, the tree and the base go into .jnprofile-python, so that it runs once in a
# run
[positional-arguments]
_api-prose-check *args:
    {{python_run}} {{python_steps}} begin prose "$@"
    {{python_run}} {{python_steps}} api prose "$@"
    {{python_run}} {{python_steps}} stamp prose
