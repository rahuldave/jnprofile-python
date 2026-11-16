# The docstring tool of the python profile: interrogate. just install docstring adds it, and jnprofile-python installs
# this file.

# Fail on each module, class, function or method with no docstring, public or private, and name its file and line
docstring-check:
    uv run --quiet --with interrogate==1.7.0 python {{python_steps}} docs
