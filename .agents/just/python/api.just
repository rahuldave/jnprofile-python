# The api tool of the python profile: smalldocs api check, for the API pages of the docs site. just install api adds
# it, and jnprofile-python installs this file. uv runs smalldocs in the environment of the project, which needs
# Python 3.11 or later.

# Fail on each function, method or class with no docstring, no type, or no docment: the comment after a parameter or
# after the return type. The settings are the key api of docs/_smalldocs.yml, or else the packages at the top of the
# project or in src/ and the module named after the project. Then run api-prose-check, when the step prose-check of the
# project does not run it.
# The step docs-check of the docs role runs this recipe, and docstring-check runs it when docs-check does not
api-check:
    {{python_run}} {{python_steps}} ran api || just --justfile {{quote(module_file())}} _api-check {{quote(env("JNPROFILE_PYTHON_ROOT", justfile()))}}

# The run of api-check: the run ID and the tree go into .jnprofile-python, so it runs once in a run of just check.
# ROOT is the Justfile of the project, whose step prose-check can run api-prose-check
_api-check root:
    {{python_run}} {{python_steps}} begin api
    {{python_run}} {{python_steps}} api check
    {{python_run}} {{python_steps}} hook {{quote(root)}} {{quote(module_file())}} prose-check api-prose-check
    {{python_run}} {{python_steps}} stamp api

# Check the API page of each changed module with the checker of nossaifd: smalldocs api module NAME writes it into a
# temporary folder, outside the project. Without the prose role, which installs the checker, it passes
api-prose-check:
    {{python_run}} {{python_steps}} api prose
