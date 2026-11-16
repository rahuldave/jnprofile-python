"""The rule of the API pages of the python profile: is_api(path) tells the commit gate whether a file feeds them.

The commit gate of agent_gest_git_skills loads this file from the parent commit and calls is_api on each changed path.
A change to such a file, such as a docstring of a public function, then needs a record of the docs and of the prose.

The rule is the rule of api-check, in steps.py and smalldocs:

- With the key api in docs/_smalldocs.yml, each package of packages, such as pkg.sub, is the folder src/pkg/sub or
  pkg/sub, or the module src/pkg/sub.py or pkg/sub.py, as the import system of Python finds it, first in src/. Each
  glob of check adds the files it matches.
  The folders are relative to root, which smalldocs reads as a folder from docs/.
- Without the key api, the packages are the folders with an __init__.py at the top of the project or in src/, and the
  module of the name of the project in pyproject.toml, as api-check finds them. A package or module that is a test
  file, a file of the tools or a file of .agents/generated.txt does not count. Each file of a package counts.
- Only a Python file counts.

is_api is False for each path in a project without the api tool or without the docs role, as .agents/stack.json
records them. It is False too when a setting cannot be read, so a broken config never stops the gate.

The file stands alone: it needs Python 3.9 or later and its standard library only, and no YAML library, so it reads
the key api with a small reader of its own. It writes nothing. Its paths are relative to the current folder, the top
of the repository, which is also the top of the project.
"""
import json
import os
import re

STACK = '.agents/stack.json'
DOCS_CONFIG = 'docs/_smalldocs.yml'
GENERATED = '.agents/generated.txt'
# The test files, as the key tests of profile.json names them, and the folders of the agents and the tools.
TESTS = ('tests/**', '**/test_*.py', '**/*_test.py', '**/conftest.py')
TOOL_FOLDERS = ('.agents/', '.claude/', '.codex/')


def is_api(path):
    """True when PATH, relative to the top of the repository, is a source file of the API pages. False on any error."""
    try:
        return _is_api(path)
    except Exception:  # noqa: BLE001 - a setting that cannot be read gives False, so the gate never stops on it
        return False


def _is_api(path):
    """is_api, which may raise on a setting that cannot be read."""
    path = clean(path)
    if not path or not path.endswith('.py') or not api_on():
        return False
    text = read(DOCS_CONFIG)
    if text is not None and re.search(r'^api\s*:', text, re.MULTILINE):
        return any(in_section(path, section) for section in api_sections(text))
    return in_found(path)


def clean(path):
    """PATH as a plain relative path with /, or '' for a path out of the repository."""
    path = str(path).replace('\\', '/')
    while path.startswith('./'):
        path = path[2:]
    parts = [part for part in path.split('/') if part not in ('', '.')]
    if path.startswith('/') or '..' in parts:
        return ''
    return '/'.join(parts)


def read(name):
    """The text of the file NAME, or None when there is none."""
    try:
        with open(name, encoding='utf-8') as file:
            return file.read()
    except (OSError, UnicodeDecodeError):
        return None


def api_on():
    """True when .agents/stack.json records the api tool of the python profile and the docs role."""
    data = json.loads(read(STACK) or '{}')
    tools = data.get('tools') or []
    choices = data.get('choices') or {}
    return isinstance(tools, list) and 'python:api' in tools and isinstance(choices, dict) and choices.get('docs') is True


def glob_regex(pattern):
    """A glob as smalldocs reads it: * and ? stop at /, ** crosses folders, and **/ is any folders or none."""
    out, i = '', 0
    while i < len(pattern):
        if pattern.startswith('**/', i):
            out, i = out + '(?:.*/)?', i + 3
        elif pattern.startswith('**', i):
            out, i = out + '.*', i + 2
        elif pattern[i] == '*':
            out, i = out + '[^/]*', i + 1
        elif pattern[i] == '?':
            out, i = out + '[^/]', i + 1
        elif pattern[i] == '[' and pattern.find(']', i + 1) > i:
            end = pattern.find(']', i + 1)
            body = pattern[i + 1:end]
            out, i = out + '[' + ('^' + body[1:] if body.startswith('!') else body) + ']', end + 1
        else:
            out, i = out + re.escape(pattern[i]), i + 1
    return re.compile(out + r'\Z')


# The small reader of the key api: a mapping, or a list of mappings, of plain values and lists.

def scalar(text):
    """A plain value of YAML: a quoted or a bare string, with no comment."""
    text = text.strip()
    if text[:1] in ('"', "'"):
        end = text.find(text[0], 1)
        if end < 0:
            raise ValueError(f'a quote is not closed: {text}')
        return text[1:end]
    return re.sub(r'\s+#.*$', '', text).strip()


def value(text):
    """A value on the line of its key: a flow list [a, b], or a plain value."""
    text = re.sub(r'\s+#.*$', '', text.strip()) if text.strip()[:1] not in ('"', "'") else text.strip()
    if text.startswith('['):
        if not text.endswith(']'):
            raise ValueError(f'a list is not closed: {text}')
        return [scalar(item) for item in text[1:-1].split(',') if item.strip()]
    return scalar(text)


def mapping(lines):
    """The mapping of LINES, (indent, text) pairs of one level: key: value, or key: and a block list under it."""
    out, i = {}, 0
    while i < len(lines):
        indent, text = lines[i]
        found = re.match(r'([A-Za-z_][\w-]*)\s*:(?:\s+(.*))?$', text)
        if not found:
            raise ValueError(f'not a key: {text}')
        key, rest = found.group(1), (found.group(2) or '').strip()
        i += 1
        if rest and not rest.startswith('#'):
            out[key] = value(rest)
            continue
        items = []
        while i < len(lines) and lines[i][0] >= indent and lines[i][1].startswith('- '):
            items.append(scalar(lines[i][1][2:]))
            i += 1
        while i < len(lines) and lines[i][0] > indent:
            i += 1  # a deeper mapping, which the rule does not read
        out[key] = items
    return out


def api_sections(text):
    """The sections of the key api of the config TEXT: one mapping, or each mapping of a list."""
    lines = text.splitlines()
    start = next(n for n, line in enumerate(lines) if re.match(r'api\s*:', line))
    rest = re.sub(r'^api\s*:', '', lines[start]).strip()
    if rest and not rest.startswith('#'):
        raise ValueError('the rule reads the key api only as a block')
    block = []
    for line in lines[start + 1:]:
        if not line.strip() or line.lstrip().startswith('#'):
            continue
        indent = len(line) - len(line.lstrip(' '))
        # YAML lets the items of a list under a key start at the column of the key: api: then - packages: [pkg].
        if indent == 0 and not (line.startswith('- ') and (not block or block[0] == (0, block[0][1]))):
            break
        block.append((indent, line.strip()))
    if not block:
        return []
    if not block[0][1].startswith('- '):
        return [mapping(block)]
    sections, current = [], None
    for indent, line in block:
        if line.startswith('- ') and indent == block[0][0]:
            current = [(indent + 2, line[2:].strip())]
            sections.append(current)
        else:
            current.append((indent, line))
    return [mapping(section) for section in sections]


def site_root(section):
    """The folder of ROOT of a section, relative to the top, as smalldocs reads it from docs/: '' for the top."""
    at_root = os.path.exists('docs/pyproject.toml') or os.path.exists('docs/.git')
    root = os.path.normpath(os.path.join('docs', str(section.get('root', '.' if at_root else '..'))))
    if root == '.':
        return ''
    if root.startswith('..') or os.path.isabs(root):
        raise ValueError('the root of the api settings is out of the repository')
    return root.replace(os.sep, '/') + '/'


def in_section(path, section):
    """True when PATH is a file of a python section of the api settings: of its packages or of its check globs."""
    if str(section.get('language', 'python')) != 'python':
        return False
    root = site_root(section)
    if not path.startswith(root):
        return False
    inner = path[len(root):]
    packages = section.get('packages') or section.get('package') or []
    for name in [packages] if isinstance(packages, str) else packages:
        for found in find(str(name), [root + 'src', root.rstrip('/') or '.']):
            found = os.path.normpath(found).replace(os.sep, '/')
            if path == found or path.startswith(found + '/'):
                return True
    checks = section.get('check') or []
    hidden = any(part.startswith('.') for part in inner.split('/')) or 'site-packages' in inner
    return not hidden and any(glob_regex(glob.lstrip('/')).match(inner) for glob in
                              ([checks] if isinstance(checks, str) else checks))


def find(name, locations):
    """The folders or the file of the package or module NAME, such as pkg.sub, as the import system of Python finds
    it from the folders LOCATIONS, in order: smalldocs puts src/ and then the root of the project on sys.path. In each
    folder, a package with an __init__.py or a module NAME.py wins, and the first one counts. A folder with neither is
    a part of a namespace package, which counts only when no folder has a package or a module."""
    for part in name.split('.'):
        found, spaces = None, []
        for location in locations:
            folder = os.path.join(location, part)
            if os.path.isfile(os.path.join(folder, '__init__.py')):
                found = [folder]
                break
            if os.path.isfile(folder + '.py'):
                found = [folder + '.py']
                break
            if os.path.isdir(folder):
                spaces.append(folder)
        found = found or spaces
        if not found:
            return []
        locations = found
    return locations


def project_name():
    """The name of the project in pyproject.toml, as a Python name: my-app gives my_app. None when there is none."""
    text = read('pyproject.toml') or ''
    try:
        import tomllib
    except ImportError:
        tomllib = None
    if tomllib is not None:
        try:
            data = tomllib.loads(text)
        except ValueError:
            return None
        table = lambda value: value if isinstance(value, dict) else {}  # noqa: E731
        name = table(data.get('project')).get('name') or table(table(data.get('tool')).get('poetry')).get('name')
        return re.sub(r'[-.]+', '_', name).lower() if isinstance(name, str) and name else None
    # Python 3.10 or older has no tomllib, so a regular expression reads the table instead.
    for header in (r'project', r'tool\.poetry'):
        table = re.search(r'^\s*\[' + header + r'\][ \t]*(?:#[^\n]*)?$(.*?)(?=^\s*\[|\Z)', text, re.MULTILINE | re.DOTALL)
        found = table and re.search(r'^\s*name\s*=\s*["\']([^"\']+)["\']', table.group(1), re.MULTILINE)
        if found:
            return re.sub(r'[-.]+', '_', found.group(1)).lower()
    return None


def generated(path):
    """True when a pattern of .agents/generated.txt names PATH, as a git pathspec with the magic word glob."""
    for line in (read(GENERATED) or '').splitlines():
        pattern = line.strip().lstrip('/')
        if not pattern or pattern.startswith('#'):
            continue
        if glob_regex(pattern).match(path) or path.startswith(pattern.rstrip('/') + '/'):
            return True
    return False


def in_found(path):
    """True when PATH is a file of the packages and the module that api-check finds without the key api."""
    parts = path.split('/')
    inner = parts[1:] if parts[0] == 'src' else parts
    if len(inner) >= 2:
        # As top_names of steps.py: the __init__.py of the package must be a code file, not a test, a file of the
        # tools or a generated file. Then smalldocs documents each module of the package, so each file counts.
        top = '/'.join(parts[:len(parts) - len(inner) + 1]) + '/__init__.py'
        return (inner[0].isidentifier() and not inner[0].startswith('_') and os.path.isfile(top)
                and not excluded(top))
    return (len(inner) == 1 and inner[0] == f'{project_name()}.py' and inner[0] != 'setup.py'
            and not excluded(path))


def excluded(path):
    """True when PATH is a test file, a file of the tools or a file of .agents/generated.txt."""
    return path.startswith(TOOL_FOLDERS) or any(glob_regex(test).match(path) for test in TESTS) or generated(path)
