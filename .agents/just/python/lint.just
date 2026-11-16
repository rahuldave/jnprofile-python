# The lint tool of the python profile: ruff. just install lint adds it, and jnprofile-python installs
# this file.

# Format the code. Extra arguments go to ruff: just fmt --check
fmt *args:
    uv run ruff format "$@"

# Check the format of the code, and change no file
fmt-check:
    uv run ruff format --check

# Check the code against the rules in ruff.toml. Extra arguments go to ruff: just lint --fix
lint *args:
    uv run ruff check "$@"
