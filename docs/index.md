---
title: jnprofile-python
---

jnprofile-python is the Python profile of [jnterfaces](https://rahuldave.github.io/jnterfaces/). A profile sets up a project in one language. It has tools, for example `lint`, and each tool brings its packages, its parts of the config files and its recipes. A recipe is a command of the project's Justfile, such as `just lint`.

The profile is for a Python project with uv. The installer finds such a project by its `pyproject.toml` or `uv.lock`.

## Install

Run this command in a project that has the jnterfaces installer:

```bash
just install --profile python
```

The command installs the tools `lint` and `test`. It also turns on the default roles of the profile, `tasker` and `prose`, unless you choose otherwise. [The roles](https://rahuldave.github.io/jnterfaces/#roles) in the jnterfaces guide tells what each role installs. In a folder with no `pyproject.toml`, it first runs `uv init --bare --no-workspace`.

Then add or remove a tool:

```bash
just install typecheck
just uninstall lint
```

The machine needs `just` and `uv`. `uv` runs Python and the tools. To install Python and every dependency into `.venv`, run `just setup`.

## The tools

| Tool | Packages | Recipes |
|---|---|---|
| `lint` | ruff, pre-commit | `just fmt`, `just lint`, `just hook` |
| `test` | pytest, pytest-cov | `just test`, `just cov` |
| `typecheck` | ty | `just typecheck` |

[The tools](tools.md) gives each recipe and each part that a tool adds to a config file.

## How the parts work

A part is the piece of a shared config file that a tool owns. `just install` adds the part, and `just uninstall` takes out only that part. Your own settings stay.

- **`ruff.toml` gets an include.** The installer writes the settings of the profile to `.agents/config/python/ruff.toml`, and adds `extend = ".agents/config/python/ruff.toml"` to your `ruff.toml`. A setting in your `ruff.toml` wins over the setting of the profile.
- **`pyproject.toml` gets the unit `tool.uv.default-groups = "all"`.** So `uv sync` and `uv run` install the dependency groups of every tool.
- **`ty.toml` and `.pre-commit-config.yaml` get units.** A unit is one key or one item of a list. Each unit has a comment on the line before it, which names its owner.
- **`.gitignore` and `.worktreedisposable` get a block of lines.** A block starts and ends with a comment that names its owner.

Do not edit a file under `.agents/config/`. Only the installer writes it. [Shared files and the record](https://rahuldave.github.io/jnterfaces/stack-guide.html#shared-files-and-the-record) in the jnterfaces guide tells you how the installer keeps a record of each part.

## The other sites

- [jnterfaces](https://rahuldave.github.io/jnterfaces/): the installer, and the `just`, `jagt-protocol` and `cx` skills.
- [jnprofile-typescript](https://rahuldave.github.io/jnprofile-typescript/): the TypeScript profile.
- [agent_gest_git_skills](https://rahuldave.github.io/agent_gest_git_skills/): the tasker role and its g skills.
