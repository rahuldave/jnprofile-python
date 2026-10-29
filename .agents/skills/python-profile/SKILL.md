---
name: python-profile
description: Use when you run, add or remove the recipes of a Python project that jnterfaces set up, such as just python lint, just test or just install typecheck. It says which tool gives which recipe, and where the files are.
---

# The python profile

The python profile of jnterfaces sets up a Python project with `uv`. A tool
is one unit of the setup, for example `lint`. `just install lint` adds the
packages of the tool to a dependency group in `pyproject.toml`, copies its
config files, and adds its recipes. `just uninstall lint` takes them out.

## The tools and their recipes

| Tool | Packages, in the group | Recipes | Config files |
|---|---|---|---|
| none, always there | none | `setup` | `.gitignore` |
| `lint` | ruff, pre-commit, in `lint` | `fmt`, `lint`, `hook` | `ruff.toml`, `.pre-commit-config.yaml` |
| `test` | pytest, pytest-cov, in `test` | `test`, `cov` | none |
| `typecheck` | ty, in `lint` | `typecheck` | `ty.toml` |

The default tools are `lint` and `test`.

## How to run a recipe

- **`just python lint`** runs the recipe of the python profile.
- **`just lint`** runs the `lint` of each language of the project. In a
  project that has only Python, it is the same as `just python lint`.
- **`just verify`** runs every installed check of each language, then `git
  diff --check`. For Python, the checks are `fmt --check`, `lint`, `test`
  and `typecheck`, for each tool that is installed.
- **With more than one language**, a combined recipe such as `just test x`
  gives the same arguments to each language. To give arguments to one
  language, run `just python test x`.

If the Justfile of the project has its own recipe with the same name, that
recipe runs. Then `just python NAME` runs the recipe of the profile.

## Where the files are

- **`.agents/just/python/`** holds the recipe files. The installer writes
  them. Do not edit them, because the next `just install` names an edited
  file and does not update it. Put your own recipes in the Justfile.
- **The config files**, for example `ruff.toml`, are yours after the first
  install. A later install leaves them alone.

## Rules for agents

- Run the recipes, not the tools. Write `just test`, not `uv run pytest`.
- To add a tool, run `just install NAME`. Do not run `uv add` for the
  packages of a tool, because then the installer does not own them.
- A recipe of a tool that is not installed does not exist. If `just python
  typecheck` is missing, run `just install typecheck`.
