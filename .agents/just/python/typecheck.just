# The typecheck tool of the python profile: ty, with the settings in ty.toml. just install typecheck adds it, and
# jnprofile-python installs this file.

# Check the types. Extra arguments go to ty: just typecheck src
typecheck *args:
    uv run ty check "$@"
