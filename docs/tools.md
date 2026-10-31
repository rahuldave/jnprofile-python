---
title: The tools
---

Each tool of the profile brings its packages, its recipes and its parts. The installer adds the packages to a dependency group of `pyproject.toml` with `uv add`. The profile sets `tool.uv.default-groups = "all"`, so `uv sync` and `uv run` install every group.

## The base

Each project of the profile gets the base, with no tool.

| Recipe | What it does |
|---|---|
| `just setup` | Installs Python and every dependency into `.venv`, as `uv.lock` says |

The base adds `.venv/`, `.local/`, `__pycache__/`, `*.pyc`, `dist/` and `build/` to `.gitignore`. It adds `.venv/`, `__pycache__/` and `*.pyc` to `.worktreedisposable`, the list of files that a command makes again, so that they do not keep a worktree.

## lint

The packages are ruff and pre-commit, in the group `lint`.

| Recipe | What it does |
|---|---|
| `just fmt` | Formats the code. Extra arguments go to ruff: `just fmt --check` |
| `just lint` | Checks the code against the rules of ruff. Extra arguments go to ruff: `just lint --fix` |
| `just hook` | Installs the git hook, which runs the checks of `.pre-commit-config.yaml` before every commit. Run it once for each clone |

The parts:

- **`ruff.toml`**: an include of `.agents/config/python/ruff.toml`. That file sets `line-length = 120`, leaves out `.agents`, `.claude` and `.codex`, and selects the rules `E`, `W` and `F`. When your `pyproject.toml` has a `[tool.ruff]` table, the installer adds no part to `ruff.toml`, because ruff reads `ruff.toml` in place of the settings in `pyproject.toml`.
- **`.pre-commit-config.yaml`**: one item of `repos` for each repository of checks. The checks are the checks of any file from pre-commit-hooks, then ruff, the linter and then the formatter.

The tool adds `.ruff_cache/` to `.gitignore` and to `.worktreedisposable`.

`just uninstall lint` also takes out the git hook that `just hook` installed.

## test

The packages are pytest and pytest-cov, in the group `test`.

| Recipe | What it does |
|---|---|
| `just test` | Runs the tests. Extra arguments go to pytest: `just test tests/unit`. A project with no tests yet passes |
| `just cov` | Runs the tests, and shows the lines that they ran |

The tool adds `.pytest_cache/`, `.coverage` and `htmlcov/` to `.gitignore` and to `.worktreedisposable`.

## typecheck

The package is ty, in the group `lint`.

| Recipe | What it does |
|---|---|
| `just typecheck` | Checks the types. Extra arguments go to ty: `just typecheck src` |

The part is a unit of `ty.toml`, the key `exclude` in the table `[src]`. It leaves out `.agents`, `.claude` and `.codex`. When your `pyproject.toml` has a `[tool.ty]` table, the installer adds no part to `ty.toml`, for the same reason.
