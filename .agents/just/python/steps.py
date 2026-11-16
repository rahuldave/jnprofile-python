"""The helper of the steps of the python profile: coverage-check, integration, docstring-check and api-check.

The recipes in this folder run it with uv: python steps.py coverage MODULE, docs, fresh NAME MODULE, ran NAME ARG...,
begin NAME ARG..., stamp NAME, api check, api prose and pages. NAME is test, integration or prose. begin, stamp and
fresh tie a coverage report, or the pass of api-prose-check, to the run ID JLOG_RUN of the root Justfile and to the
worktree tree. So coverage-check reads the reports of test and integration only from the same run, and a check that
two steps need runs once in a run. It needs Python 3.9 or later. The step
coverage-check also needs diff-cover, which it runs with uv and Python 3.11 or later. docs runs in the environment
of the project, with interrogate, so that it parses the code with the Python of the project. pages runs there too,
with smalldocs.

The lists .agents/generated.txt and .agents/coverage-exclude.txt come from the parent commit, through
git show HEAD:./PATH, so a commit cannot exempt its own code. With no parent, both lists are empty. git matches
their patterns, as pathspecs with the magic word glob. Every path is relative to the current folder, the top of
the project, which can be a subfolder of the git repository.
"""
import ast
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import xml.etree.ElementTree as ElementTree

DIFF_COVER = 'diff-cover==11.0.1'
GENERATED = '.agents/generated.txt'
COVERAGE_EXCLUDE = '.agents/coverage-exclude.txt'
# The test files, as the key tests of profile.json names them. They hold tests and no code to cover or document.
TESTS = ('tests/**', '**/test_*.py', '**/*_test.py', '**/conftest.py')
# The folders of the agents and of the installed tools, which hold no code of the project, as ruff.toml leaves out.
TOOL_FOLDERS = ('.agents/', '.claude/', '.codex/')
WORK = Path('.jnprofile-python')
REPORT = WORK / 'coverage.xml'
INTEGRATION = WORK / 'integration.xml'
# The report of each kind of run that begin and stamp tie to a run of just. test and integration write a coverage
# report. api-prose-check writes none, so only its pass counts.
REPORTS = {'test': REPORT, 'integration': INTEGRATION, 'prose': None}
# The data file of coverage.py for each run, so that an --cov-append of the project adds to no old run.
DATA = {'test': WORK / '.coverage', 'integration': WORK / '.coverage-integration'}
RECORD = Path('.agents/stack.json')
SMALLDOCS = 'smalldocs==0.5.5'
DOCS_CONFIG = Path('docs/_smalldocs.yml')
# The checker of nossaifd, which the prose role installs. api prose checks the API pages with it.
PROSE_CHECKER = Path('.agents/skills/nossaifd/scripts/check.py')
# A file at the top of the project that is a script, not a module of the API: an import would run it.
SCRIPTS = ('setup.py',)


def git(*args):
    """Run git with ARGS in the current folder, and return the finished process, with its output as text."""
    return subprocess.run(['git', *args], capture_output=True, text=True)


def has_parent():
    """True when HEAD names a commit, so that the next commit has a parent."""
    return git('rev-parse', '--verify', '--quiet', 'HEAD^{commit}').returncode == 0


def top():
    """The real path of the current folder, the top of the project. Every path of the steps is relative to it."""
    return Path(os.path.realpath('.'))


def parent_list(path):
    """The patterns of the list file PATH in the parent commit: one for each line that is not blank or a comment.

    A missing parent or a file that the parent does not have gives no patterns.
    """
    if not has_parent():
        return []
    run = git('show', f'HEAD:./{path}')
    if run.returncode:
        return []
    return [line.strip() for line in run.stdout.splitlines() if line.strip() and not line.strip().startswith('#')]


def listed(patterns):
    """The tracked and the untracked files, that git does not ignore, that one of PATTERNS matches, as a set.

    git matches the patterns, as pathspecs with the magic word glob, so the steps and the gate read a list in the same
    way. A * does not match a /, ** matches any number of folders, and a folder names all that it holds. A leading /
    is the top of the project.
    """
    if not patterns:
        return set()
    specs = [':(glob)' + pattern.lstrip('/') for pattern in patterns]
    run = git('ls-files', '-z', '--cached', '--others', '--exclude-standard', '--', *specs)
    if run.returncode:
        raise SystemExit(f'steps.py: git cannot read the patterns {patterns}: {run.stderr.strip()}')
    return set(filter(None, run.stdout.split('\0')))


def code_files(excluded):
    """The Python files of the project that git tracks or does not ignore, without the test files, the files in the
    folders of the tools and EXCLUDED."""
    tests = listed(TESTS)
    return sorted(path for path in listed(['**/*.py']) if path not in tests and path not in excluded
                  and not path.startswith(TOOL_FOLDERS) and Path(path).is_file())


def changed_code():
    """The changed Python files against HEAD, tracked and staged or not, and the untracked ones, as two lists.

    The deleted files are left out.
    """
    tracked = git('diff', '-z', '--name-only', '--relative', '--diff-filter=d', 'HEAD', '--', '*.py')
    untracked = git('ls-files', '-z', '--others', '--exclude-standard', '--', '*.py')
    names = lambda run: sorted(set(filter(None, run.stdout.split('\0'))))
    return names(tracked), names(untracked)


def relative(path, root):
    """PATH relative to ROOT, with / between its parts, or None for a path outside ROOT."""
    full = Path(os.path.realpath(root / path))
    try:
        return full.relative_to(root).as_posix()
    except ValueError:
        return None


def report_files(tree, root):
    """Map each class element of the Cobertura report TREE to the path of its file, relative to ROOT, or None.

    coverage.py writes each file name relative to one of the folders in sources.
    """
    sources = [Path(source.text.strip()) for source in tree.iter('source') if source.text and source.text.strip()]
    files = {}
    for element in tree.iter('class'):
        name = element.get('filename', '')
        candidates = [source / name for source in sources] or [Path(name)]
        found = next((candidate for candidate in candidates if (root / candidate).is_file()), candidates[0])
        files[element] = relative(found, root)
    return files


def filter_report(tree, root, wanted):
    """Keep in the report TREE only the class elements of the files in WANTED, and return their paths.

    So the test files, the files in the folders of the tools and the files of the two lists do not count.
    """
    files = report_files(tree, root)
    for classes in tree.iter('classes'):
        for element in list(classes):
            if element.tag == 'class' and files.get(element) not in wanted:
                classes.remove(element)
    return {path for path in files.values() if path in wanted}


def missed_lines(tree, root, wanted):
    """The lines that the report TREE has as not run, in the files of WANTED, as lines FILE:LINE."""
    found = []
    for element, path in report_files(tree, root).items():
        if path in wanted:
            found += [(path, int(line.get('number'))) for line in element.iter('line') if line.get('hits') == '0']
    return [f'{path}:{line}: no test runs this line' for path, line in sorted(set(found))]


def worktree_tree():
    """The tree hash of every file of the worktree, staged or not, that git does not ignore, or None on an error.

    It uses a temporary index of its own, as the spec of the commit gates says, so neither the real index nor a
    second run at the same time changes. The folder of the reports never counts. A file that git cannot index, such
    as a nested repository with no commit, gives None, and git's message goes to the error output.
    """
    WORK.mkdir(parents=True, exist_ok=True)
    handle, name = tempfile.mkstemp(dir=WORK, suffix='.index')
    os.close(handle)
    index = Path(name).resolve()
    index.unlink()
    env = dict(os.environ, GIT_INDEX_FILE=str(index))
    try:
        if has_parent():
            subprocess.run(['git', 'read-tree', 'HEAD'], env=env, check=True, capture_output=True)
        # git refuses to name an ignored path, even to exclude it, so the exclude is only for a folder that git sees.
        ignored = git('check-ignore', '--quiet', '--', str(WORK)).returncode == 0
        specs = [':/'] if ignored else [':/', f':(exclude){WORK}']
        subprocess.run(['git', 'add', '-A', '--', *specs], env=env, check=True, capture_output=True)
        return subprocess.run(['git', 'write-tree'], env=env, check=True, capture_output=True,
                              text=True).stdout.strip()
    except subprocess.CalledProcessError as exc:
        print(f'steps.py: git cannot compute the worktree tree: {(exc.stderr or b"").decode(errors="replace").strip()}',
              file=sys.stderr)
        return None
    finally:
        index.unlink(missing_ok=True)
        Path(str(index) + '.lock').unlink(missing_ok=True)


def recipe_of(name):
    """The recipe of the run NAME, for a message: prose is the run of api-prose-check."""
    return 'api-prose-check' if name == 'prose' else name


def run_file(name):
    """The file that holds the run ID and the tree of the last run of NAME that passed."""
    return WORK / ('run.json' if name == 'test' else f'{name}-run.json')


def pending_file(name):
    """The file that holds the run ID and the tree of the run of NAME that is going on."""
    return WORK / ('run.pending' if name == 'test' else f'{name}-run.pending')


def begin(name, args):
    """Save the run ID and the worktree tree before a run of NAME, test, integration or prose, in its pending file.

    Only a run with no ARGS, inside a run of just that has JLOG_RUN, saves them. Any other run saves nothing, so the
    next step runs it again. The old report goes, so a failed run leaves none. Returns the exit code, always 0.
    """
    WORK.mkdir(parents=True, exist_ok=True)
    for path in (run_file(name), pending_file(name), REPORTS[name], DATA.get(name)):
        if path is not None:
            path.unlink(missing_ok=True)
    run = os.environ.get('JLOG_RUN', '')
    tree = worktree_tree() if not args and run else None
    if tree:
        pending_file(name).write_text(json.dumps({'run': run, 'tree': tree}) + '\n')
    return 0


def stamp(name):
    """After the run of NAME passed, keep the saved run as its run file when the tree did not change.

    A change to a file during the run means that the report may come from the old code, so the run is dropped.
    Returns the exit code, always 0.
    """
    try:
        saved = json.loads(pending_file(name).read_text())
    except (OSError, ValueError):
        return 0
    finally:
        pending_file(name).unlink(missing_ok=True)
    if isinstance(saved, dict) and saved.get('tree') and saved['tree'] == worktree_tree():
        # A run with no test passes and writes no report. It still counts as run, with no report.
        report = REPORTS[name]
        saved['report'] = report is not None and report.is_file()
        run_file(name).write_text(json.dumps(saved) + '\n')
    else:
        print(f'{recipe_of(name)}: a file changed during the run, so the next step that needs it runs it again',
              file=sys.stderr)
    return 0


def same_run(name):
    """The run ID when the last run of NAME that passed comes from this run of just, JLOG_RUN, and from the current
    worktree tree, and the report that it wrote is still there. Otherwise None.

    A person can set JLOG_RUN by hand, so the tree must match too. An old run of the same tree is a valid run.
    """
    run = os.environ.get('JLOG_RUN', '')
    try:
        saved = json.loads(run_file(name).read_text())
    except (OSError, ValueError):
        saved = None
    report = REPORTS[name]
    if (run and isinstance(saved, dict) and saved.get('run') == run
            and (report is None or not saved.get('report', True) or report.is_file())
            and saved.get('tree') and saved['tree'] == worktree_tree()):
        return run
    return None


def recipes_of(justfile):
    """The names of the public recipes of JUSTFILE, as just --summary gives them, or an empty set on an error."""
    run = subprocess.run(['just', '--justfile', str(justfile), '--summary'], capture_output=True, text=True)
    return set(run.stdout.split()) if run.returncode == 0 else set()


def integration_counts(module):
    """True when the report of integration counts for coverage-check. The module MODULE must have the recipe
    integration, and the key steps of .agents/stack.json must name it, so that just check runs it."""
    try:
        steps = json.loads(RECORD.read_text()).get('steps')
    except (OSError, ValueError, AttributeError):
        steps = None
    return isinstance(steps, list) and 'integration' in steps and 'integration' in recipes_of(module)


def fresh(name, module):
    """True when the run of NAME in this run of just and on this tree wrote the report that coverage-check reads.

    For integration, it is also True when its report does not count, so that coverage-check does not run it.
    """
    if name == 'integration' and not integration_counts(module):
        return True
    run = same_run(name)
    what = 'tests' if name == 'test' else 'integration tests'
    if run:
        print(f'coverage-check: the {what} of this run, {run}, wrote the report, so they do not run again')
        return True
    print(f'coverage-check: no report of the {what} of this run and this tree, so they run now', flush=True)
    return False


def ran(name, args):
    """True when NAME passed before in this run of just and on this tree, and ARGS is empty. So a check that two
    steps of just check can need, such as integration or api-prose-check, runs once."""
    run = None if args else same_run(name)
    if run:
        print(f'{recipe_of(name)}: it passed before in this run, {run}, on this tree, so it does not run again')
    return bool(run)


def line_hits(paths, root):
    """The hits of each line in the Cobertura reports PATHS, as a map from the path of a file, relative to ROOT, to a
    map from a line number to its hits. A line that one report runs counts as run."""
    files = {}
    for path in paths:
        tree = ElementTree.parse(path)
        for element, name in report_files(tree, root).items():
            if name is None:
                continue
            lines = files.setdefault(name, {})
            for line in element.iter('line'):
                try:
                    number, hits = int(line.get('number')), int(line.get('hits') or 0)
                except ValueError:
                    continue
                lines[number] = max(lines.get(number, 0), hits)
    return files


def union(paths, root):
    """One Cobertura report, as an ElementTree, with the lines of each file in the reports PATHS. Its one source is
    ROOT, and the name of each file is relative to it."""
    coverage = ElementTree.Element('coverage', version='0', timestamp='0')
    sources = ElementTree.SubElement(coverage, 'sources')
    ElementTree.SubElement(sources, 'source').text = str(root)
    classes = ElementTree.SubElement(ElementTree.SubElement(ElementTree.SubElement(coverage, 'packages'), 'package',
                                                            name='.'), 'classes')
    for name, lines in sorted(line_hits(paths, root).items()):
        run = sum(1 for hits in lines.values() if hits)
        element = ElementTree.SubElement(classes, 'class', name=name, filename=name,
                                         **{'line-rate': str(run / len(lines) if lines else 1), 'branch-rate': '0'})
        ElementTree.SubElement(element, 'methods')
        body = ElementTree.SubElement(element, 'lines')
        for number, hits in sorted(lines.items()):
            ElementTree.SubElement(body, 'line', number=str(number), hits=str(hits))
    return ElementTree.ElementTree(coverage)


def coverage(module=None):
    """Fail on each changed line of code that the tests do not run, as diff-cover against HEAD finds it.

    The report is the one of test. When integration counts, as integration_counts of MODULE says, it is the union of
    the reports of test and integration, so a line that only integration runs counts as run. The files of
    generated.txt and coverage-exclude.txt of the parent commit do not count, and nor do the test files. A line with
    # pragma: no cover is not in the report, so it counts as run. On the first commit, every line of code must run, a
    limit of 100%. A changed file that is not in the report fails too, because no test imports it. Returns the exit
    code.
    """
    root = top()
    excluded = listed(parent_list(GENERATED) + parent_list(COVERAGE_EXCLUDE))
    wanted = set(code_files(excluded))
    if has_parent():
        tracked, untracked = changed_code()
        tracked = [path for path in tracked if path in wanted]
        untracked = [path for path in untracked if path in wanted]
    else:
        tracked, untracked = [], sorted(wanted)
    changed = sorted(tracked + untracked)
    if not changed:
        print('coverage-check: no changed code')
        return 0
    names = [REPORT] + ([INTEGRATION] if module and integration_counts(module) else [])
    reports = [path for path in names if path.is_file()]
    if not reports:
        print(f'coverage-check: there is no coverage report {" or ".join(map(str, names))}, so write tests and run '
              f'just test', file=sys.stderr)
        return 1
    tree = union(reports, root)
    kept = filter_report(tree, root, wanted)
    code = 0
    if tracked:
        # diff-cover needs Python 3.11 or later, whatever .python-version of the project says.
        WORK.mkdir(parents=True, exist_ok=True)
        filtered = WORK / 'kept.xml'
        tree.write(filtered)
        code = subprocess.run(['uv', 'run', '--no-project', '--quiet', '--python', '>=3.11', '--with', DIFF_COVER,
                               'diff-cover', str(filtered), '--compare-branch', 'HEAD',
                               '--fail-under', '100']).returncode
    if not has_parent():
        print('coverage-check: the first commit, so every line of code must run in the tests', flush=True)
    # Each line of an untracked file is new, so each must run. diff-cover reads the untracked files with paths from
    # the current folder, which do not match the report in a project in a subfolder, so the step checks them itself.
    missed = missed_lines(tree, root, set(untracked))
    for line in missed:
        print(line)
    code = code or (1 if missed else 0)
    missing = [path for path in changed if path not in kept]
    for path in missing:
        print(f'{path}: a changed file that is not in the coverage report: no test imports it, or the coverage '
              'config omits it')
    code = code or (1 if missing else 0)
    if code:
        print('coverage-check: write tests for the missing lines. A line that no test can run gets # pragma: no '
              f'cover, and a file of generated code goes in {GENERATED}, in a commit of its own before this one',
              file=sys.stderr)
    return code


def deleter_lines(path):
    """The lines of each function of PATH with a decorator NAME.deleter, and of that decorator.

    interrogate leaves out a property setter, but not a deleter, and the getter documents both.
    """
    try:
        tree = ast.parse(Path(path).read_text(), filename=path)
    except (OSError, SyntaxError, ValueError):
        return set()
    lines = set()
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            marks = [d for d in node.decorator_list if isinstance(d, ast.Attribute) and d.attr == 'deleter']
            if marks:
                lines |= {node.lineno} | {d.lineno for d in node.decorator_list}
    return lines


def docs():
    """Fail on each module, class, function or method with no docstring, public or private, as lines FILE:LINE.

    interrogate finds them, with a limit of 100%. The test files and the files of generated.txt of the parent commit
    do not count. A magic method, such as __repr__, and __init__ do not count either: the protocol and the doc of
    the class say what they do. Nor do an @overload stub, a property setter and a property deleter, which the
    function and the getter document. Returns the exit code.
    """
    from interrogate import config, coverage as interrogate

    files = code_files(listed(parent_list(GENERATED)))
    if not files:
        print('docstring-check: no code')
        return 0
    conf = config.InterrogateConfig(ignore_magic=True, ignore_init_method=True, ignore_overloaded_functions=True,
                                    ignore_property_setters=True, fail_under=100)
    results = interrogate.InterrogateCoverage(paths=files, conf=conf).get_coverage()
    findings = sorted((Path(result.filename).as_posix(), node.lineno or 1, node.node_type, node.name)
                      for result in results.file_results for node in result.nodes if not node.covered
                      and (node.lineno or 1) not in deleter_lines(result.filename))
    for path, line, kind, name in findings:
        print(f'{path}:{line}: {kind} {name} has no docstring')
    if findings:
        print(f'docstring-check: {len(findings)} items have no docstring. Write a docstring for each one',
              file=sys.stderr)
        return 1
    return 0


def project_name():
    """The name of the project in pyproject.toml, as a Python name: my-app gives my_app. None when there is none."""
    try:
        text = Path('pyproject.toml').read_text()
    except (OSError, UnicodeDecodeError):
        return None
    try:
        import tomllib
    except ImportError:
        # Python 3.10 or older has no tomllib, so a regular expression reads the table instead.
        table = re.search(r'^\s*\[project\]\s*$(.*?)(?=^\s*\[|\Z)', text, re.MULTILINE | re.DOTALL)
        found = table and re.search(r'^\s*name\s*=\s*["\']([^"\']+)["\']', table.group(1), re.MULTILINE)
        name = found.group(1) if found else None
    else:
        try:
            data = tomllib.loads(text)
        except ValueError:
            return None
        table = lambda value: value if isinstance(value, dict) else {}
        name = table(data.get('project')).get('name') or table(table(data.get('tool')).get('poetry')).get('name')
    return re.sub(r'[-.]+', '_', name).lower() if isinstance(name, str) and name else None


def top_names(excluded):
    """The packages at the top of the project or of src/, which the API pages document, and the module of the name
    of the project. A package is a folder with an __init__.py of code. Other modules at the top are often scripts,
    such as noxfile.py, and an import would run them, so they are left out. The names that start with _ are private,
    and EXCLUDED holds the files of generated.txt."""
    files = set(code_files(excluded))
    own = project_name()
    names = set()
    for path in files:
        parts = Path(path).parts
        if parts[0] == 'src':
            parts = parts[1:]
        if len(parts) == 2 and parts[1] == '__init__.py':
            name = parts[0]
        elif len(parts) == 1 and parts[0] == f'{own}.py' and parts[0] not in SCRIPTS:
            name = own
        else:
            continue
        if name.isidentifier() and not name.startswith('_'):
            names.add(name)
    return sorted(names)


def api_settings(folder):
    """The folder of the smalldocs config that api-check uses, and a note. It is docs/ when docs/_smalldocs.yml has
    the key api. Otherwise it is FOLDER, with a config of the packages and modules that top_names finds. With no
    package and no module, it is None."""
    try:
        text = DOCS_CONFIG.read_text()
    except (OSError, UnicodeDecodeError):
        text = ''
    if re.search(r'^api\s*:', text, re.MULTILINE):
        return DOCS_CONFIG.parent, f'the api settings of {DOCS_CONFIG}'
    names = top_names(listed(parent_list(GENERATED)))
    if not names:
        return None, ('no package at the top of the project or in src/, and no module with the name of the project. '
                      f'The key api of {DOCS_CONFIG} can name the packages')
    (folder / '_smalldocs.yml').write_text('api:\n  packages: ' + json.dumps(names) + '\n  root: '
                                           + json.dumps(str(top())) + '\n')
    return folder, f'the packages and modules {", ".join(names)}'


def smalldocs(*args):
    """The command that runs smalldocs with ARGS in the environment of the project, so that it can import the code."""
    return ['uv', 'run', '--quiet', '--with', SMALLDOCS, *args]


def python_ok(asked):
    """The exit code when the Python of the project cannot run smalldocs, which needs 3.11 or later, or None when it
    can. The code is 1 when the project ASKED for the check, with the key api of docs/_smalldocs.yml. Otherwise the
    check passes with a note, so that a project on an older Python is not stopped by a default tool."""
    run = subprocess.run(['uv', 'run', '--quiet', 'python', '-c',
                          'import sys; print("%d.%d" % sys.version_info[:2]); sys.exit(sys.version_info < (3, 11))'],
                         capture_output=True, text=True)
    if not run.returncode:
        return None
    found = run.stdout.strip()
    if not found:
        print(f'api-check: uv cannot run the Python of the project: {run.stderr.strip()}', file=sys.stderr)
        return 1
    note = (f'smalldocs needs Python 3.11 or later, and the project has {found}. Raise requires-python in '
            f'pyproject.toml, or take the tool out with just uninstall api')
    if asked:
        print(f'api-check: {note}', file=sys.stderr)
        return 1
    print(f'api-check: the API is not checked: {note}')
    return 0


def api(action):
    """Run the api check: smalldocs api check with the settings of api_settings, for ACTION check. For ACTION prose,
    check the API page of each changed module with the checker of nossaifd. Returns the exit code."""
    if action == 'prose' and not PROSE_CHECKER.is_file():
        print(f'api-prose-check: no checker of nossaifd at {PROSE_CHECKER}, so the API pages are not checked. The prose '
              f'role installs it')
        return 0
    with tempfile.TemporaryDirectory() as temp:
        folder, about = api_settings(Path(temp))
        if folder is None:
            print(f'{"api-check" if action == "check" else "api-prose-check"}: {about}, so there is no API to check')
            return 0
        code = python_ok(folder == DOCS_CONFIG.parent)
        if code is not None:
            return code
        if action == 'check':
            print(f'api-check: smalldocs api check, with {about}', flush=True)
            code = subprocess.run(smalldocs('smalldocs', 'api', 'check', '--dir', str(folder))).returncode
            if code == 1:
                print('api-check: give each function, method and class a docstring, a type for each parameter and '
                      'for the return, and a docment: a comment after each parameter and after the return type',
                      file=sys.stderr)
            elif code:
                print(f'api-check: smalldocs cannot read the API, for example because an import failed. The key api '
                      f'of {DOCS_CONFIG} can name the packages to check', file=sys.stderr)
            return code
        excluded = listed(parent_list(GENERATED))
        if has_parent():
            tracked, untracked = changed_code()
            changed = sorted(set(tracked + untracked) & set(code_files(excluded)))
        else:
            changed = code_files(excluded)
        if not changed:
            print('api-prose-check: no changed code')
            return 0
        out = Path(temp) / 'pages'
        out.mkdir()
        code = subprocess.run(smalldocs('python', str(Path(__file__).resolve()), 'pages', str(folder), str(out),
                                        *changed)).returncode
        if code:
            return code
        pages = sorted(out.glob('*.md'))
        if not pages:
            print('api-prose-check: no changed module has an API page')
            return 0
        print(f'api-prose-check: the API pages of {", ".join(page.stem for page in pages)}', flush=True)
        code = subprocess.run(['uv', 'run', '--no-project', '--quiet', 'python', str(PROSE_CHECKER),
                               *map(str, pages)]).returncode
        if code:
            print('api-prose-check: fix each hard problem in the docstring that it comes from', file=sys.stderr)
        return code


def pages(folder, out, files):
    """Write the API page of each module of the api settings in FOLDER whose file is in FILES, as OUT/NAME.md.

    It runs in the environment of the project, with smalldocs, which imports the modules. Returns the exit code.
    """
    from smalldocs import api as smalldocs_api
    from smalldocs.config import load

    project = load(folder)
    settings = smalldocs_api.Settings.read(project.root, project.smalldocs.get('api') or {})
    settings.importable()
    wanted = {Path(os.path.realpath(name)) for name in files}
    for package in settings.packages:
        for module in smalldocs_api.package_modules(package):
            source = getattr(module, '__file__', None)
            if source and Path(os.path.realpath(source)) in wanted:
                text = smalldocs_api.markdown(module.__name__, settings.packages)
                (Path(out) / f'{module.__name__}.md').write_text(text)
    return 0


def main(argv):
    """Run the command of ARGV, as the docstring of the module lists them, and return its exit code."""
    if argv[:1] == ['coverage'] and len(argv) <= 2:
        return coverage(argv[1] if len(argv) == 2 else None)
    if argv == ['docs']:
        return docs()
    if argv[:1] == ['fresh'] and len(argv) == 3 and argv[1] in REPORTS:
        return 0 if fresh(argv[1], argv[2]) else 1
    if argv[:1] == ['ran'] and len(argv) >= 2 and argv[1] in REPORTS:
        return 0 if ran(argv[1], argv[2:]) else 1
    if argv[:1] == ['begin'] and len(argv) >= 2 and argv[1] in REPORTS:
        return begin(argv[1], argv[2:])
    if argv[:1] == ['stamp'] and len(argv) == 2 and argv[1] in REPORTS:
        return stamp(argv[1])
    if argv[:1] == ['api'] and argv[1:] in (['check'], ['prose']):
        return api(argv[1])
    if argv[:1] == ['pages'] and len(argv) >= 3:
        return pages(argv[1], argv[2], argv[3:])
    print('usage: steps.py coverage [MODULE] | docs | fresh NAME MODULE | ran NAME [ARG...] | begin NAME [ARG...] | '
          'stamp NAME | api check | api prose | pages FOLDER OUT [FILE...]',
          file=sys.stderr)
    return 2


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
