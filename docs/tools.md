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
| `just test` | Runs the tests, and writes their coverage to `.jnprofile-python/coverage.xml`. Extra arguments go to pytest: `just test tests/unit`. With no arguments, a project with no tests yet passes. With the tool `integration`, the tests in `tests/integration` do not run, because `just integration` runs them |
| `just coverage-check` | Fails on each changed line of code that no test runs. It is a step of `just check` |
| `just cov` | Runs the tests, and shows the lines that they ran. With no arguments, a project with no tests yet passes |
| `just python::test-paths FILE...` | Runs only the test files that you name, for `test-parent` of the commit gates. It exits with 0 when tests ran and passed, with 1 when a test fails or a file cannot be collected, and with 5 when no test runs, as for a file whose tests are all skipped or all xfail. Any other code means that uv or pytest itself failed, or that a test ended the run. The output ends with one line for each test. A file whose name starts with `-` goes to pytest as `./NAME`, because pytest on Python 3.10 and 3.11 reads it as an option |

The tool adds `.pytest_cache/`, `.coverage`, `htmlcov/` and `.jnprofile-python/` to `.gitignore` and to `.worktreedisposable`.

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

### coverage-check

`coverage-check` compares the coverage report with the parent commit. It runs diff-cover with a limit of 100%.

- **A line that no test runs** fails. A line with `# pragma: no cover` counts as run.
- **A changed file that no test imports** fails, because the report does not have it.
- **No report** fails, with the message "write tests". pytest-cov writes no report when no test runs.
- **The first commit** has no parent. Then each line of code must run in the tests.
- **The files that do not count** are the test files and the files in `.agents`, `.claude` and `.codex`. The files that `.agents/generated.txt` or `.agents/coverage-exclude.txt` names do not count either. The step reads both lists from the parent commit, so a commit cannot exempt its own code with them. The config of coverage.py, such as `exclude_also` in `[tool.coverage.report]`, comes from the commit itself, so `test-review` judges each change to it.
- **The report of the same run.** `test` saves the run ID of `just check`, `JLOG_RUN`, with the tree of the worktree. `coverage-check` reads the report only when both match. Otherwise it runs the tests first.
- **The integration tests.** A line that only the integration tests run counts as run when two things are true. The project has the `integration` tool. The key `steps` of `.agents/stack.json` has `integration`, so `just check` runs it. Then `coverage-check` reads the reports of `test` and of `integration`, and a line counts as run when one of them runs it. When the report of `integration` is not from the same run, `coverage-check` runs the integration tests first.

## integration

The packages are pytest and pytest-cov, in the group `test`. The tool is not a default tool. Add it with `just install integration`.

| Recipe | What it does |
|---|---|
| `just integration` | Runs the tests in `tests/integration`, and writes their coverage to `.jnprofile-python/integration.xml`. Extra arguments go to pytest in place of the folder: `just integration tests/integration/test_db.py`. With no folder `tests/integration`, it passes. It is a step of `just check` |

`just check` runs `integration` before `coverage-check`. So `coverage-check` reads the report of the step `integration` of the same run, and does not run the integration tests again. When `just integration` runs after it passed in the same run, on the same tree, it says "it passed before in this run" and does not run the tests again.

The tool adds the same lines to `.gitignore` and to `.worktreedisposable` as the tool `test`.

## docstring

The tool has no package. uv runs interrogate in the environment of the project, so interrogate reads the code with the Python of the project.

| Recipe | What it does |
|---|---|
| `just docstring-check` | Fails on each module, class, function or method with no docstring, public or private. It names the file and the line. It is a step of `just check` |

A magic method, such as `__repr__`, and `__init__` do not count. The protocol and the docstring of the class say what they do. An `@overload` stub, a property setter and a property deleter do not count either, because the function and the getter have the docstring. The test files, the files in `.agents`, `.claude` and `.codex`, and the files that `.agents/generated.txt` of the parent commit names do not count.

`api-check` of the tool `api` checks the docments. `docstring-check` does not. A docment is the comment after a parameter or after the return type.

## api

The tool has no package. uv runs smalldocs 0.5.12 in a copy of the environment of the project, so smalldocs can import the code. smalldocs needs Python 3.11 or later, so uv runs it with Python 3.11 or later, also when `.python-version` or `UV_PYTHON` names an older one. The step gives uv the floor 3.11 and the `requires-python` of the project at once, such as `>=3.11,>=3.10,<3.12`. So uv takes a Python that both allow, not a newer one above the upper limit of the project. The copy is isolated, so `.venv` of the project keeps its own Python.

The tool is a default tool, and its check runs in a project with the docs role of jnterfaces.

| Recipe | What it does |
|---|---|
| `just api-check` | Runs `smalldocs api check`. It fails on each function, method or class with no docstring, no type for a parameter or the return, or no docment. It names the module and the function, for example `m:sub(a): no docment`. Then it runs `api-prose-check` |
| `just api-prose-check` | Checks the API page of each changed module with the checker of nossaifd. A changed module is a module with a change against `HEAD`, or each module on the first commit. In CI, or with `--base REF`, it is a module with a change since the base, as for `prose-check`: `just api-prose-check --base main` |

The settings of `api-check`:

- **With a key `api` in `docs/_smalldocs.yml`**, smalldocs reads its settings there. The key `packages` names the packages to check.
- **Otherwise**, the step writes a temporary config. It names each package at the top of the project or in `src/`. A package is a folder with an `__init__.py`. It also names the module with the name of the project in `pyproject.toml`. For the project `my-app`, that module is `my_app.py`. Other files at the top, such as `noxfile.py`, are often scripts, and an import would run them. So the step leaves them out. A name that starts with `_` is private, and the step leaves it out. The test files and the files that `.agents/generated.txt` of the parent commit names do not count.
- **With a list of sections under the key `api`**, `api-prose-check` fails with exit 2. It reads only one section of Python settings.
- **With no package and no such module**, the step passes.
- **When an import fails**, smalldocs exits with 2, and the step says so. Name the packages in the key `api` of `docs/_smalldocs.yml`.
- **When `requires-python` of the project allows no Python 3.11 or later**, smalldocs cannot run. Then the step passes with a note.
- **When uv cannot run the project with Python 3.11 or later for another reason**, the step fails with the error of uv. Examples are no Python 3.11 on the machine with no download, and a dependency that does not build. With a key `api` in `docs/_smalldocs.yml`, the project asks for the check, so the step fails.

smalldocs checks every function, public and private. Its pages show only the public ones.

The page that `api-prose-check` checks has the whole docstring of the module in its body, with the first paragraph. The checker of nossaifd does not read the front matter or a quoted string, so the step never puts a docstring there. A module with no public function, method or class has no API page, so the step does not check its docstring.

Where the checks run:

- **`api-check`** runs in the step `docs-check` of the docs role of jnterfaces. That step runs the `api-check` of each language that has one. The docments are a check of the docs site, so without the docs role no step of `just check` runs `api-check`. You can still run `just api-check`, and `just verify` runs it.
- **`api-prose-check`** runs in `api-check`. The step `prose-check` of nossaifd runs it too. It runs once in a run. When it passed before in the same run of `just check`, on the same tree and with the same base, it says so and does not run again. A call with another base runs again.

The changed modules of `api-prose-check`:

- **On a machine**, without CI and without `--base`, the step does not load `prose_gate.py`. A changed module has a change against `HEAD`, in the index or the working tree, or is a new file.
- **In CI**, a checkout is clean, so the changes against `HEAD` hold no module. So in CI the step takes the base that `prose-check` of nossaifd takes. On a pull request, the base is the merge base of the base branch and `HEAD`. CI is on when the variable `CI` is set to a value other than empty, `false` and `0`.
- **With `--base REF`**, the base is the merge base of `REF` and `HEAD`, also outside CI. As in `check-changed` of nossaifd, the last `--base` counts, and `-v` does nothing here.
- **With a base**, a changed module has a change since the base, in the commits or in the working tree.
- **The rule of the base** is not in this profile. The step loads `.agents/skills/nossaifd/scripts/prose_gate.py`, which the prose role installs, and calls its `base_commit`. So in CI, both steps compare with the same commit. A failure of `base_commit` fails the step with exit 2.
- **An error of the base**, as a shallow clone or a base that is not a commit, fails the step with exit 2 and the message of nossaifd. An error of the base never gives a pass.
- **An older install of nossaifd** has no `base_commit`. Then the step fails with exit 2 in CI or with `--base`, and asks you to run `just install`. Without CI and without `--base`, nothing changes. An install between nossaifd #17 and #18 has `base_commit`. It works, but on the push that makes the default branch, it compares with `HEAD^`, not with the empty tree.

`api-prose-check` writes each page into a temporary folder outside the project. The page is the text that `smalldocs api module NAME` prints. The step makes it with the same function of smalldocs, in one run for all the modules.

Then it runs `.agents/skills/nossaifd/scripts/check.py` on the pages. A hard problem fails the step. Fix it in the docstring that it comes from. Without the prose role, which installs the checker, the step passes and says so.

### The rule of the API pages for the commit gate

A change to a docstring of a public function changes an API page. So the commit gate of agent_gest_git_skills asks for a record of the docs and of the prose. The gate must know which code files feed the API pages. The file `.agents/just/python/api_rule.py` tells it.

- **The interface.** The file defines `is_api(path)`. It gives `True` when `path`, relative to the top of the repository, is a source file of the API pages. The gate loads the file from the parent commit and calls `is_api` on each changed path.
- **How it runs.** The rule needs Python 3.9 or later and its standard library only. It runs with `python -I -B`, in the top of the repository, and writes nothing. It needs no YAML library. It reads the key `api` of `docs/_smalldocs.yml` with a small reader of its own.
- **Where it comes from.** The profile package installs the folder `.agents/just/python` in each Python project, so every project gets the file. The installer does not let `files` of `profile.json` write into `.agents/just`. `.agents/generated.txt` does not name the file.
- **Without the api tool or the docs role,** as `.agents/stack.json` records them, `is_api` gives `False` for every path. Then no step of `just check` runs `api-check`.
- **When the rule cannot read the settings of `api`,** `is_api` gives `True` for each Python file. A file in `.agents`, `.claude` or `.codex`, or in `.agents/generated.txt`, still gives `False`. So the gate asks for a record, and a config that the rule cannot read never turns the gate off without notice. Without the api tool or the docs role, `is_api` still gives `False`. `is_api` never stops with an error.

The rule is the rule of `api-check`. Only a Python file counts.

- **With the key `api`** in `docs/_smalldocs.yml`, the rule reads each section of the language `python`. For each package of `packages`, such as `pkg.sub`, it takes the folder `src/pkg/sub` or `pkg/sub`, or the module `src/pkg/sub.py` or `pkg/sub.py`. It finds them as Python imports them, first in `src/`. A folder with an `__init__.py` or a module wins over a folder without one. Each glob of `check` adds the files that it matches. The folders start at `root`, which smalldocs reads from `docs/`.
- **Without the key `api`**, the rule takes the packages that `api-check` finds. A package is a folder with an `__init__.py` at the top of the project or in `src/`. The rule also takes the module with the name of the project. A package or a module that is a test file, a file of the tools or a file of `.agents/generated.txt` does not count. In a package that counts, each file counts, as smalldocs documents each module of it.

The reader of the key `api` reads a mapping or a list of mappings. A value is a plain value, a list in brackets on one line, or a list of lines that start with `- `. Other forms of YAML are out of its scope. For them, `is_api` gives `True` for each Python file, as for any config that it cannot read:

- a section in braces, such as `api: {packages: [pkg]}`;
- a dash alone on its line, with the mapping under it;
- a list in brackets over more than one line;
- a key in quotes;
- a value with `>` or `|`;
- a key `api` with no section, or a section of Python with no `packages`, which smalldocs does not take either;
- a `root` out of the repository.

On Python 3.10 or older, the rule has no `tomllib`. Then it does not read the name of the project from a dotted key, such as `project.name = "my-app"`. A package that only an install puts on the path, such as a folder `python/`, is out of the scope of the rule too.

`just live-api-rule` in this repository runs the live lab of the rule. It installs the profile and the docs role into a new project with the installer of jnterfaces, and makes a commit. Then it changes only a docstring, and checks that `is_api` of the parent commit accepts the file.

## typecheck

The package is ty, in the group `lint`.

| Recipe | What it does |
|---|---|
| `just typecheck` | Checks the types. Extra arguments go to ty: `just typecheck src` |

The part is a unit of `ty.toml`, the key `exclude` in the table `[src]`. It leaves out `.agents`, `.claude` and `.codex`. When your `pyproject.toml` has a `[tool.ty]` table, the installer adds no part to `ty.toml`, because ty reads `ty.toml` in place of the settings in `pyproject.toml`.
