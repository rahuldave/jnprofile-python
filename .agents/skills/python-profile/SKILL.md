---
name: python-profile
description: Use when you run, add or remove the recipes of a Python project that jnterfaces set up, such as just python lint, just test or just install typecheck. It says which tool gives which recipe, and where the files are.
---

# The python profile

The python profile of jnterfaces sets up a Python project with `uv`. A tool
is one unit of the setup, for example `lint`. `just install lint` adds the
packages of the tool to a dependency group in `pyproject.toml`, adds its parts to the config files, and adds its recipes. `just uninstall lint` takes them out.

## The tools and their recipes

| Tool | Packages, in the group | Recipes | Parts in config files | Lines in `.gitignore` and `.worktreedisposable` |
|---|---|---|---|---|
| none, always there | none | `setup` | none | `.venv/`, `__pycache__/`, `*.pyc`; also `.local/`, `dist/`, `build/` in `.gitignore` |
| `lint` | ruff, in `lint` | `fmt`, `fmt-check`, `lint` | `ruff.toml` | `.ruff_cache/` |
| `test` | pytest, pytest-cov, in `test` | `test`, `coverage-check`, `cov` | none | `.pytest_cache/`, `.coverage`, `htmlcov/`, `.jnprofile-python/` |
| `docstring` | none; uv runs interrogate | `docstring-check` | none | none |
| `typecheck` | ty, in `lint` | `typecheck` | `ty.toml` | none |

The default tools are `lint`, `test` and `docstring`.

## Parts in shared files

A tool adds a part to a file that other profiles and you share, such as
`.gitignore` or `ruff.toml`. `profile.json` lists the lines of a tool under
`lines`, and its other parts under `parts`. `just install` writes the lines
of each tool in a block of their own, at the start of the file.

A config
file gets an include, such as an `extend` or an `extends`, that reads an own
file under `.agents/config/python/`. The key `parts` in `.agents/stack.json`
records each part. `just uninstall` of the tool takes its parts out again,
unless another tool needs them. Your own lines and settings stay, and your
settings win over the settings of the own file.

## How to run a recipe

- **`just python lint`** runs the recipe of the python profile.
- **`just lint`** runs the `lint` of each language of the project. In a
  project that has only Python, it is the same as `just python lint`.
- **`just verify`** runs every installed check of each language, then `git
  diff --check`. For Python, the checks are `fmt-check`, `lint`, `test`,
  `coverage-check`, `docstring-check` and `typecheck`, for each tool that is
  installed.
- **With more than one language**, a combined recipe such as `just test x`
  gives the same arguments to each language. To give arguments to one
  language, run `just python test x`.

A project that jnterfaces started has the combined recipes, such as `just
lint` and `just verify`. If its Justfile has its own recipe with the
same name, that recipe runs. A project with a Justfile of its own gets the
module only, so it runs `just python NAME`.

## Where the files are

- **`.agents/just/python/`** holds the recipe files. The installer writes
  them. Do not edit them, because the next `just install` names an edited
  file and does not update it. Put your own recipes in the Justfile.
- **`.agents/config/python/`** holds the own files, such as `ruff.toml`. The
  installer writes them. Do not edit them. Put a setting of yours in
  `ruff.toml`, where it wins.

## The steps of `just check`

- **`fmt-check`** fails when ruff would change the format of a file. It
  changes no file. Run `just fmt` to fix it.
- **`coverage-check`** fails on each changed line of code that no test runs.
  On the first commit, it fails on each line of code that no test runs.
  - A line with `# pragma: no cover` counts as run. The `test-review` target
    judges each new pragma.
  - A changed file that no test imports fails.
  - It reads the report that `test` wrote in the same run of `just check`.
    Otherwise it runs the tests first.
  - The test files, `.agents`, `.claude` and `.codex` do not count. Nor do
    the files that `.agents/generated.txt` or `.agents/coverage-exclude.txt`
    of the parent commit names. The config of coverage.py comes from the
    commit itself, so `test-review` judges each change to it.
- **`docstring-check`** fails on each module, class, function or method with
  no docstring, public or private. It names the file and the line. A magic
  method, such as `__repr__`, `__init__`, an `@overload` stub, a property
  setter and a property deleter do not count. The files that
  `.agents/generated.txt` of the parent commit names do not count.

## Rules for agents

- Run the recipes, not the tools. Write `just test`, not `uv run pytest`.
- To add a tool, run `just install NAME`. Do not run `uv add` for the
  packages of a tool, because then the installer does not own them.
- A recipe of a tool that is not installed does not exist. If `just python
  typecheck` is missing, run `just install typecheck`.
