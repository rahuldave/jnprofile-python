# jnprofile-python

jnprofile-python is the Python profile of
[jnterfaces](https://github.com/rahuldave/jnterfaces). A profile sets up a
project in one language. It has tools, for example `lint`, and each tool
brings its packages, its config files and its recipes.

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
| `.agents/just/python/` | One recipe file for each tool. The installer copies the folder into the project. |
| `files/` | The config files that a tool copies when the project has none. |
| `.agents/skills/python-profile/` | The skill that tells an agent how to use the recipes. |

## License

MIT. See [LICENSE](LICENSE).
