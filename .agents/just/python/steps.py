"""The helper of the steps of the python profile: coverage-check and docstring-check.

The recipes in this folder run it with uv: python steps.py coverage, docs, fresh, begin ARG... and stamp. begin, stamp
and fresh tie the coverage report to the run ID JLOG_RUN of the root Justfile and to the worktree tree, so that
coverage-check reads the report of test only in the same run. It needs Python 3.9 or later. The step coverage-check
also needs diff-cover, which it runs with uv and Python 3.11 or later. docs runs in the environment of the project, with interrogate, so that
it parses the code with the Python of the project.

The lists .agents/generated.txt and .agents/coverage-exclude.txt come from the parent commit, through
git show HEAD:./PATH, so a commit cannot exempt its own code. With no parent, both lists are empty. git matches
their patterns, as pathspecs with the magic word glob. Every path is relative to the current folder, the top of
the project, which can be a subfolder of the git repository.
"""
import ast
import json
import os
from pathlib import Path
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
# The data file of coverage.py for test, so that an --cov-append of the project adds to no old run.
DATA = WORK / '.coverage'
RUN = WORK / 'run.json'
PENDING = WORK / 'run.pending'


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


def begin(args):
    """Save the run ID and the worktree tree before a run of the tests, in .jnprofile-python/run.pending.

    Only a run of all the tests, with no ARGS, inside a run of just that has JLOG_RUN saves them. Any other run
    saves nothing, so coverage-check runs the tests again. The old report goes, so a failed run leaves none. Returns
    the exit code, always 0.
    """
    for path in (RUN, PENDING, REPORT, DATA):
        path.unlink(missing_ok=True)
    run = os.environ.get('JLOG_RUN', '')
    tree = worktree_tree() if not args and run else None
    if tree:
        PENDING.write_text(json.dumps({'run': run, 'tree': tree}) + '\n')
    return 0


def stamp():
    """After the tests passed, keep the saved run as .jnprofile-python/run.json when the tree did not change.

    A change to a file while the tests ran means that the report may come from the old code, so the run is dropped.
    Returns the exit code, always 0.
    """
    try:
        saved = json.loads(PENDING.read_text())
    except (OSError, ValueError):
        return 0
    finally:
        PENDING.unlink(missing_ok=True)
    if isinstance(saved, dict) and saved.get('tree') and saved['tree'] == worktree_tree():
        RUN.write_text(json.dumps(saved) + '\n')
    else:
        print('test: a file changed while the tests ran, so coverage-check runs them again', file=sys.stderr)
    return 0


def fresh():
    """True when the report of the tests comes from this run of just, JLOG_RUN, and from the current worktree tree.

    A person can set JLOG_RUN by hand, so the tree must match too. An old run of the same tree is a valid run.
    """
    run = os.environ.get('JLOG_RUN', '')
    try:
        saved = json.loads(RUN.read_text())
    except (OSError, ValueError):
        saved = None
    if (run and isinstance(saved, dict) and saved.get('run') == run and REPORT.is_file()
            and saved.get('tree') and saved['tree'] == worktree_tree()):
        print(f'coverage-check: the tests of this run, {run}, wrote the report, so they do not run again')
        return True
    print('coverage-check: no report of this run and this tree, so the tests run now', flush=True)
    return False


def coverage():
    """Fail on each changed line of code that the tests do not run, as diff-cover against HEAD finds it.

    The files of generated.txt and coverage-exclude.txt of the parent commit do not count, and nor do the test files.
    A line with # pragma: no cover is not in the report, so it counts as run. On the first commit, every line of code
    must run, a limit of 100%. A changed file that is not in the report fails too, because no test imports it.
    Returns the exit code.
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
    if not REPORT.is_file():
        print(f'coverage-check: there is no coverage report {REPORT}, so write tests and run just test',
              file=sys.stderr)
        return 1
    tree = ElementTree.parse(REPORT)
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


def main(argv):
    """Run the command of ARGV, coverage, docs, fresh, begin ARG... or stamp, and return its exit code."""
    if argv == ['coverage']:
        return coverage()
    if argv == ['docs']:
        return docs()
    if argv == ['fresh']:
        return 0 if fresh() else 1
    if argv[:1] == ['begin']:
        return begin(argv[1:])
    if argv == ['stamp']:
        return stamp()
    print('usage: steps.py coverage | docs | fresh | begin [ARG...] | stamp', file=sys.stderr)
    return 2


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
