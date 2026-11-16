#!/usr/bin/env python3
"""The lint of the recipe files of the profile, in .agents/just/python, as the module of the installer imports them.

It writes a module that imports each recipe file, with the settings of the module of the installer, and reads it with
just --dump. So a file that does not parse, or two files that define one recipe, fail. Then it checks each step of
just check that the files define, as the lint of the steps of jnterfaces does. jlog logs each line of a step through
its shell, so a step must not be a shebang recipe or have [script]. A line must not start with -, so that a failure
stops the step. A step must not have [no-cd] or [working-directory], so that jlog finds its log folder.

    lint_recipes.py [FOLDER]    lint the recipe files of FOLDER, by default .agents/just/python; exit 1 on a finding
"""
import json
from pathlib import Path
import subprocess
import sys
import tempfile

REPO = Path(__file__).resolve().parent.parent
FOLDER = REPO / '.agents/just/python'
# The steps of just check, as jnterfaces names them.
STEPS = ('fmt-check', 'lint', 'typecheck', 'test', 'integration', 'coverage-check', 'docstring-check', 'docs-check',
         'prose-check', 'diff-check')
# The settings of the module that the installer writes, without its shell, jlog, which the lint does not need.
SETTINGS = "set positional-arguments\nset working-directory := '../..'\n"
FORBIDDEN = ('script', 'no-cd', 'working-directory')


def dump(folder):
    """The recipes of the module that imports each recipe file of FOLDER, from just --dump, or an error text. An alias
    comes in as the recipe that it names, so a step that is an alias gets the lint of its recipe."""
    with tempfile.TemporaryDirectory() as temp:
        module = Path(temp) / 'just/python.just'
        module.parent.mkdir()
        (module.parent / 'python').symlink_to(folder.resolve())
        imports = ''.join(f"import 'python/{path.name}'\n" for path in sorted(folder.glob('*.just')))
        module.write_text(SETTINGS + imports)
        run = subprocess.run(['just', '--justfile', str(module), '--dump', '--dump-format', 'json'],
                             capture_output=True, text=True)
    if run.returncode:
        return None, run.stderr.strip()
    data = json.loads(run.stdout)
    recipes = dict(data['recipes'])
    for name, alias in (data.get('aliases') or {}).items():
        recipes.setdefault(name, data['recipes'].get(alias.get('target'), {}))
    return recipes, None


def findings(recipes):
    """The problems of the steps among RECIPES, one text for each."""
    out = []
    for name in STEPS:
        recipe = recipes.get(name)
        if recipe is None:
            continue
        if recipe.get('shebang'):
            out.append(f'{name}: a step is a shebang recipe, so jlog does not log its lines')
        attributes = [next(iter(a)) if isinstance(a, dict) else a for a in recipe.get('attributes') or []]
        for attribute in FORBIDDEN:
            if attribute in attributes:
                out.append(f'{name}: a step has the attribute [{attribute}]')
        for line in recipe.get('body') or []:
            if line and isinstance(line[0], str) and line[0].lstrip('@').startswith('-'):
                out.append(f'{name}: a line starts with -, so a failure does not stop the step')
    return out


def main(argv):
    """Lint the folder of ARGV, or FOLDER, and return the exit code."""
    folder = Path(argv[0]) if argv else FOLDER
    recipes, error = dump(folder)
    if error:
        print(f'lint_recipes.py: just cannot read the recipe files of {folder}: {error}', file=sys.stderr)
        return 1
    problems = findings(recipes)
    for problem in problems:
        print(f'lint_recipes.py: {problem}', file=sys.stderr)
    if not problems:
        print(f'lint_recipes.py: {len(recipes)} recipes, and no problem in the steps')
    return 1 if problems else 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
