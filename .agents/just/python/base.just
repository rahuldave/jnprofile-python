# The recipes of the python profile that every Python project has. jnprofile-python installs this file.

# uv runs the helper script of the steps, steps.py, with Python 3.11 or later and no package. docstring-check runs it
# in the environment of the project instead, which can have Python 3.9 or later
python_run := "uv run --no-project --quiet --python '>=3.11' python"
python_steps := quote(source_directory() / "steps.py")

# Install Python and every dependency into .venv, as the lockfile says
setup:
    uv sync
