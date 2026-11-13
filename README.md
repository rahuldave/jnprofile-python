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

## License

The license is MIT. See [LICENSE](LICENSE).
