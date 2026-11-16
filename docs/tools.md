---
title: The tools
---

Each tool of the profile brings its packages, its recipes and its parts. The installer adds the packages to a dependency group of `pyproject.toml` with `uv add`. The profile sets `tool.uv.default-groups = "all"`, so `uv sync` and `uv run` install every group.

## The base

Every project of the profile gets the base, even a project with no tool.

| Recipe | What it does |
|---|---|
| `just setup` | Installs Python and every dependency into `.venv`, as `uv.lock` says |

The base adds `.venv/`, `.local/`, `__pycache__/`, `*.pyc`, `dist/` and `build/` to `.gitignore`. It adds `.venv/`, `__pycache__/` and `*.pyc` to `.worktreedisposable`. That file lists the ignored files that a command can make again. `just worktrees-prune` keeps a worktree that has ignored files, but it does not count these files.

## lint

The package is ruff, in the group `lint`.

| Recipe | What it does |
|---|---|
| `just fmt` | Formats the code. Extra arguments go to ruff: `just fmt --check` |
| `just fmt-check` | Fails when ruff would change the format of a file. It changes no file. It is a step of `just check` |
| `just lint` | Checks the code against the rules of ruff. Extra arguments go to ruff: `just lint --fix` |

The parts:

- **`ruff.toml`**: an include of `.agents/config/python/ruff.toml`. That file sets `line-length = 120`, leaves out `.agents`, `.claude` and `.codex`, and selects the rules `E`, `W` and `F`. When your `pyproject.toml` has a `[tool.ruff]` table, the installer adds no part to `ruff.toml`, because ruff reads `ruff.toml` in place of the settings in `pyproject.toml`.

The tool adds `.ruff_cache/` to `.gitignore` and to `.worktreedisposable`.

The profile does not install pre-commit or a git hook. The tasker role, from agent_gest_git_skills, installs them for every language, with the commit gate. `just check` runs `fmt-check` and `lint`, so the hook needs no ruff of its own. A project from an older profile, which installed pre-commit for `lint`, loses it at the next `just install`. The `before_remove` of `lint` still names pre-commit, so the installer runs `pre-commit uninstall` first, and no commit fails on a hook without its config.

## test

The packages are pytest and pytest-cov, in the group `test`.

| Recipe | What it does |
|---|---|
| `just test` | Runs the tests, and writes their coverage to `.jnprofile-python/coverage.xml`. Extra arguments go to pytest: `just test tests/unit`. With no arguments, a project with no tests yet passes |
| `just coverage-check` | Fails on each changed line of code that no test runs. It is a step of `just check` |
| `just cov` | Runs the tests, and shows the lines that they ran. With no arguments, a project with no tests yet passes |
| `just python::test-paths FILE...` | Runs only the test files that you name, for `test-parent` of the commit gates. It exits with 0 when tests ran and passed, with 1 when a test fails or a file cannot be collected, and with 5 when no test runs, as for a file whose tests are all skipped or all xfail. Any other code means that uv or pytest itself failed, or that a test ended the run. The output ends with one line for each test |

The tool adds `.pytest_cache/`, `.coverage`, `htmlcov/` and `.jnprofile-python/` to `.gitignore` and to `.worktreedisposable`.

### coverage-check

`coverage-check` compares the coverage report with the parent commit. It runs diff-cover with a limit of 100%.

- **A line that no test runs** fails. A line with `# pragma: no cover` counts as run.
- **A changed file that no test imports** fails, because the report does not have it.
- **No report** fails, with the message "write tests". pytest-cov writes no report when no test runs.
- **The first commit** has no parent. Then each line of code must run in the tests.
- **The files that do not count** are the test files and the files in `.agents`, `.claude` and `.codex`. The files that `.agents/generated.txt` or `.agents/coverage-exclude.txt` names do not count either. The step reads both lists from the parent commit, so a commit cannot exempt its own code with them. The config of coverage.py, such as `exclude_also` in `[tool.coverage.report]`, comes from the commit itself, so `test-review` judges each change to it.
- **The report of the same run.** `test` saves the run ID of `just check`, `JLOG_RUN`, with the tree of the worktree. `coverage-check` reads the report only when both match. Otherwise it runs the tests first.

## docstring

The tool has no package. uv runs interrogate in the environment of the project, so interrogate reads the code with the Python of the project.

| Recipe | What it does |
|---|---|
| `just docstring-check` | Fails on each module, class, function or method with no docstring, public or private. It names the file and the line. It is a step of `just check` |

A magic method, such as `__repr__`, and `__init__` do not count. The protocol and the docstring of the class say what they do. An `@overload` stub, a property setter and a property deleter do not count either, because the function and the getter have the docstring. The test files, the files in `.agents`, `.claude` and `.codex`, and the files that `.agents/generated.txt` of the parent commit names do not count.

The profile names its files for the commit gates. The code is `**/*.py`. The test files are `tests/**`,
`**/test_*.py`, `**/*_test.py` and `**/conftest.py`. `test-parent` copies only the test files into the parent commit,
so no new code reaches it.

The tool also adds the item `"."` to `tool.pytest.ini_options.pythonpath` in `pyproject.toml`. So a test in `tests/` can import a module at the top of the project, such as `app.py`.

- **Your `pythonpath` list** keeps its items, and gets `"."` too.
- **A `pythonpath` string of yours**, such as `"src"`, stays as it is. The installer adds nothing to it.
- **A pytest config of your own** makes the installer leave out the part. pytest reads only one config, so the part would hide yours. The installer looks for these configs:
  - `[tool.pytest]` with settings in `pyproject.toml`, which pytest 9 reads
  - `pytest.toml`, `.pytest.toml`, `pytest.ini` or `.pytest.ini`
  - `[pytest]` in `tox.ini`, or `[tool:pytest]` in `setup.cfg`

  In that case, if your tests need it, add `pythonpath = ["."]` to your config yourself.

  The installer looks for these configs only when it adds the part. If you add a pytest config after the install, the part stays in `pyproject.toml`, and pytest no longer reads the part. Add `pythonpath = ["."]` to your config, or run `just uninstall test` and `just install test` to take the part out.

## typecheck

The package is ty, in the group `lint`.

| Recipe | What it does |
|---|---|
| `just typecheck` | Checks the types. Extra arguments go to ty: `just typecheck src` |

The part is a unit of `ty.toml`, the key `exclude` in the table `[src]`. It leaves out `.agents`, `.claude` and `.codex`. When your `pyproject.toml` has a `[tool.ty]` table, the installer adds no part to `ty.toml`, because ty reads `ty.toml` in place of the settings in `pyproject.toml`.
