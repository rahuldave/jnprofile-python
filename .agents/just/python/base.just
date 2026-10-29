# The recipes of the python profile that every Python project has. jnprofile-python installs this file.

# Install Python and every dependency into .venv, as the lockfile says
setup:
    uv sync
