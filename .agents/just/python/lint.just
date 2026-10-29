# The lint tool of the python profile: ruff and pre-commit. just install lint adds it, and jnprofile-python installs
# this file.

# Format the code. Extra arguments go to ruff: just fmt --check
fmt *args:
    uv run ruff format "$@"

# Check the code against the rules in ruff.toml. Extra arguments go to ruff: just lint --fix
lint *args:
    uv run ruff check "$@"

# Install the git hook: the checks of .pre-commit-config.yaml before every commit. Once per clone
hook:
    uv run pre-commit install
