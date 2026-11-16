# jnprofile-python

jnprofile-python is the Python profile of
[jnterfaces](https://github.com/rahuldave/jnterfaces). A profile sets up a
project in one language. It has tools, for example `lint`, and each tool
brings its packages, its parts of the config files and its recipes. A part is
the piece of a shared config file that a tool owns. A recipe is a command of
the project's Justfile, such as `just lint`.

The documentation site is https://rahuldave.github.io/jnprofile-python/. Its
pages are in `docs/`. `just docs` shows a preview of the site, and
`just docs-publish` publishes it to the branch `gh-pages`.

## Install

Run this command in a project that has the jnterfaces installer:

```bash
just install --profile python
```

Then add or remove a tool:

```bash
just install typecheck
just uninstall lint
```

The machine needs `just` and `uv`. `uv` runs Python and the tools.

## What is here

| Path | What it holds |
|---|---|
| `profile.json` | The profile: its manifest, the commands that add and remove packages, and its tools. |
| `.agents/just/python/` | One recipe file for each tool. The installer copies the folder into the project. A step of `just check`, such as `test`, has no shebang line, so that jlog, the program that logs each line of a recipe, logs the line of the step and its exit code. Its script is in a private recipe, which the step runs in one line with `just`. |
| `files/` | The sources of the parts. For `ruff.toml`, `just install` copies the source to a file of its own under `.agents/config/` and adds an include of that file to `ruff.toml`. For the other config files, it adds the keys and the list items of the source. `just uninstall` takes the parts out. |
| `.agents/skills/python-profile/` | The skill that tells an agent how to use the recipes. |
| `scripts/lint_recipes.py` | The lint of the recipe files. The installer does not copy it. |

## Checks of this repository

The Justfile of this repository has the same five recipes as each profile of jnterfaces:

| Recipe | What it does |
|---|---|
| `just lint` | Runs ruff 0.17.5 on the Python files, with the settings of `ruff.toml`. Then it reads the recipe files together with `just`, and checks that no step of `just check` is a shebang recipe or has a line that starts with `-`. |
| `just test` | Runs all the tests, with the live lab. The lab installs the profile into a new project with the installer of jnterfaces. |
| `just prose-check` | Runs the checker of nossaifd on each Markdown page. A hard note fails it. |
| `just docs-check` | Runs `smalldocs check docs`. |
| `just check` | Runs `lint`, `test`, `prose-check` and `docs-check`, in that order. |

These settings name the clones that the checks use:

- **`NOSSAIFD_CHECK`** names the checker of nossaifd. The default is `~/Projects/nossaifd/check.py`.
- **`JNTERFACES_INSTALLER`** names the installer of jnterfaces. The default is `~/Projects/jnterfaces/scripts/install_stack.py`.
- **`SKILL_PACKAGES_DIR`** names the folder of the other packages that the installer installs. The default is the folder of the clone of jnterfaces.

CI runs `just check` on each push and each pull request, in `.github/workflows/verify.yml`. CI clones jnterfaces, agent_gest_git_skills and nossaifd at pinned commits. CI runs no agent.

On a machine, a test that needs a missing program or clone skips. In CI, such a test fails, so a missing program cannot pass the run. CI is on when the variable `CI` is set to a value other than empty, `false` and `0`.

## License

The license is MIT. See [LICENSE](LICENSE).
