"""Run the recipes of the integration and api tools with real just, uv, git, pytest and smalldocs."""

import json
import os
from pathlib import Path
import subprocess
import unittest

from test_steps import CODE, MODULE, TEST, TOOLS, ProjectCase

# The module with the integration and api tools too.
FULL = MODULE + "import? 'python/integration.just'\nimport? 'python/api.just'\n"
# A root Justfile like the one of jnterfaces, with the combined recipe api-check of the index.
ROOT = ('export JLOG_RUN := env("JLOG_RUN", uuid())\nmod python ".agents/just/python.just"\n\n'
        'api-check:\n    just --justfile {{quote(justfile())}} python api-check\n')
# The step docs-check of the docs role of jnterfaces: it runs the api-check of each language.
DOCS_ROLE = ('\ndocs-check:\n    recipes="$(just --justfile {{quote(justfile())}} --summary)" && if printf \'%s\\n\' '
             '$recipes | grep -qx api-check; then just --justfile {{quote(justfile())}} api-check; fi\n')
STEPS = ["fmt-check", "lint", "typecheck", "test", "integration", "coverage-check", "docstring-check", "docs-check",
         "prose-check", "diff-check"]
# Code with every docstring, type and docment that smalldocs api check wants.
TYPED = ('"""Math."""\n\n\ndef add(\n    a: int,  # The first number\n    b: int,  # The second number\n'
         ') -> int:  # The sum\n    """Add A and B."""\n    return a + b\n')
UNTYPED = '\n\ndef sub(a, b):\n    """Subtract B from A."""\n    return a - b\n'
# A stand-in for the checker of nossaifd: a page with the word "basically" has a hard problem.
CHECKER = ('import sys\nfrom pathlib import Path\nbad = False\nfor name in sys.argv[1:]:\n'
           '    hard = "basically" in Path(name).read_text()\n'
           '    print(f"{Path(name).name}: {int(hard)} hard, 0 soft")\n    bad = bad or hard\nsys.exit(1 if bad else 0)\n')


@unittest.skipUnless(TOOLS, "needs just, uv and git")
class IntegrationTests(ProjectCase):
    def setUp(self) -> None:
        super().setUp()
        self.write(".agents/just/python.just", FULL)
        self.write("m.py", CODE + UNTYPED)
        self.write("tests/integration/test_flow.py", "from m import sub\n\n\ndef test_sub():\n    assert sub(3, 1) == 2\n")

    def steps(self, names: list) -> None:
        self.write(".agents/stack.json", json.dumps({"steps": names}) + "\n")

    def test_a_line_that_only_integration_runs_passes_when_integration_is_in_check(self) -> None:
        self.steps(STEPS)
        self.write("m.py", CODE)
        self.commit()
        self.write("m.py", CODE + UNTYPED)
        env = dict(self.env, JLOG_RUN="run-1")
        # just check runs integration, then coverage-check, which reads the report of that run.
        code, out = self.just("python::integration", env=env)
        self.assertEqual(code, 0, out)
        code, out = self.just("python::coverage-check", env=env)
        self.assertEqual(code, 0, out)
        self.assertIn("the integration tests of this run, run-1, wrote the report, so they do not run again", out)
        self.assertNotIn("test_flow.py", out)

    def test_coverage_check_runs_the_integration_tests_when_their_report_is_old(self) -> None:
        self.steps(STEPS)
        self.write("m.py", CODE)
        self.commit()
        self.write("m.py", CODE + UNTYPED)
        self.just("python::integration", env=dict(self.env, JLOG_RUN="run-1"))
        code, out = self.just("python::coverage-check", env=dict(self.env, JLOG_RUN="run-2"))
        self.assertEqual(code, 0, out)
        self.assertIn("no report of the integration tests of this run and this tree, so they run now", out)

    def test_a_line_that_only_integration_runs_fails_when_integration_is_not_in_check(self) -> None:
        self.steps([step for step in STEPS if step != "integration"])
        self.write("m.py", CODE)
        self.commit()
        self.write("m.py", CODE + UNTYPED)
        code, out = self.just("python::coverage-check")
        self.assertEqual(code, 1, out)
        self.assertIn("m.py (50.0%): Missing lines 11", out)
        self.assertNotIn("integration tests", out)

    def test_test_leaves_out_the_integration_tests_and_integration_runs_them(self) -> None:
        self.write("tests/integration/test_flow.py", "def test_flow():\n    assert False\n")
        code, out = self.just("python::test")
        self.assertEqual(code, 0, out)
        self.assertNotIn("test_flow", out)
        code, out = self.just("python::integration")
        self.assertEqual(code, 1, out)
        self.assertIn("tests/integration/test_flow.py F", out)
        self.assertNotIn("test_m.py", out)

    def test_only_integration_tests_still_fail_test_when_one_fails(self) -> None:
        # With no unit test, test passes: the integration tests do not count as tests that it finds.
        (self.root / "tests/test_m.py").unlink()
        code, out = self.just("python::test")
        self.assertEqual(code, 0, out)
        self.assertIn("just test: no tests yet", out)

    def test_integration_with_no_folder_passes_and_runs_once_in_a_run(self) -> None:
        (self.root / "tests/integration/test_flow.py").unlink()
        (self.root / "tests/integration").rmdir()
        env = dict(self.env, JLOG_RUN="run-1")
        code, out = self.just("python::integration", env=env)
        self.assertEqual(code, 0, out)
        self.assertIn("no integration tests yet", out)
        code, out = self.just("python::integration", env=env)
        self.assertEqual(code, 0, out)
        self.assertIn("integration: it passed before in this run, run-1", out)

    def test_without_the_integration_tool_test_runs_tests_integration(self) -> None:
        # Nothing else runs them then, so a failing one must fail test.
        self.write(".agents/just/python.just", MODULE)
        self.write("tests/integration/test_flow.py", "def test_flow():\n    assert False\n")
        code, out = self.just("python::test")
        self.assertEqual(code, 1, out)
        self.assertIn("tests/integration/test_flow.py F", out)

    def test_a_failed_integration_test_fails_coverage_check_that_runs_it(self) -> None:
        self.steps(STEPS)
        self.write("tests/integration/test_flow.py", "def test_flow():\n    assert False\n")
        code, out = self.just("python::coverage-check")
        self.assertNotEqual(code, 0, out)


@unittest.skipUnless(TOOLS, "needs just, uv and git")
class ApiTests(ProjectCase):
    def setUp(self) -> None:
        super().setUp()
        self.write(".agents/just/python.just", FULL)
        self.write("Justfile", ROOT)
        # The project is named m, so the module m.py is the module of the project, which api-check finds.
        text = (self.root / "pyproject.toml").read_text()
        self.write("pyproject.toml", text.replace(">=3.9", ">=3.11").replace('name = "app"', 'name = "m"'))
        subprocess.run(["uv", "lock", "--quiet"], cwd=self.root, check=True, env=self.env)
        self.write("m.py", TYPED)
        self.write("tests/test_m.py", TEST)

    def test_a_public_function_with_no_docments_fails_api_check(self) -> None:
        code, out = self.just("python::api-check")
        self.assertEqual(code, 0, out)
        self.assertIn("with the packages and modules m", out)
        self.write("m.py", TYPED + UNTYPED)
        code, out = self.just("python::api-check")
        self.assertEqual(code, 1, out)
        self.assertIn("m:sub(a): no docment", out)
        self.assertIn("m:sub: no return type", out)
        self.assertIn("a docment: a comment after each parameter", out)

    def test_docstring_check_does_not_check_the_docments(self) -> None:
        # Without the docs role, no step runs api-check: the docments are a check of the docs site.
        self.write("m.py", TYPED + UNTYPED)
        code, out = self.just("python::docstring-check")
        self.assertEqual(code, 0, out)
        self.assertNotIn("api-check", out)

    def test_the_docs_check_of_the_docs_role_runs_api_check(self) -> None:
        self.write("Justfile", ROOT + DOCS_ROLE)
        self.write("m.py", TYPED + UNTYPED)
        code, out = self.just("docs-check")
        self.assertEqual(code, 1, out)
        self.assertIn("m:sub(a): no docment", out)
        self.write("m.py", TYPED)
        code, out = self.just("docs-check")
        self.assertEqual(code, 0, out)
        self.assertIn("api-check: smalldocs api check", out)

    def test_api_prose_check_runs_once_in_a_run(self) -> None:
        # api-check runs it, and a later prose-check that calls it does not run it again.
        self.write(".agents/skills/nossaifd/scripts/check.py", CHECKER)
        env = dict(self.env, JLOG_RUN="run-1")
        code, out = self.just("api-check", env=env)
        self.assertEqual(code, 0, out)
        self.assertIn("m.md: 0 hard", out)
        code, out = self.just("python::api-prose-check", env=env)
        self.assertEqual(code, 0, out)
        self.assertIn("api-prose-check: it passed before in this run, run-1, on this tree", out)
        # A changed tree runs it again, and fails it.
        self.write("m.py", TYPED.replace('"""Add A and B."""', '"""Add A and B, basically."""'))
        code, out = self.just("python::api-prose-check", env=env)
        self.assertEqual(code, 1, out)
        self.assertIn("m.md: 1 hard", out)

    def test_the_api_settings_of_the_docs_config_win(self) -> None:
        self.write("m.py", TYPED + UNTYPED)
        self.write("pkg/__init__.py", '"""Pkg."""\n')
        self.write("pkg/core.py", TYPED)
        self.write("docs/_smalldocs.yml", "project:\n  type: website\napi:\n  packages: [pkg]\n")
        code, out = self.just("python::api-check")
        self.assertEqual(code, 0, out)
        self.assertIn("with the api settings of docs/_smalldocs.yml", out)
        self.assertNotIn("m:sub", out)

    def test_the_packages_are_found_at_the_top_and_in_src(self) -> None:
        self.write("src/pkg/__init__.py", '"""Pkg."""\n')
        self.write("src/pkg/core.py", TYPED + UNTYPED)
        self.write("_private/__init__.py", '"""P."""\n\n\ndef f(x):\n    """F."""\n    return x\n')
        code, out = self.just("python::api-check")
        self.assertEqual(code, 1, out)
        self.assertIn("with the packages and modules m, pkg", out)
        self.assertIn("pkg.core:sub(a): no docment", out)
        self.assertNotIn("_private", out)

    def test_a_script_at_the_top_is_not_imported(self) -> None:
        # Only the module with the name of the project counts. An import of a script could fail, or write a file.
        self.write("noxfile.py", "import nox\n")
        self.write("make_data.py", "from pathlib import Path\nPath('data.txt').write_text('x')\n")
        self.write("setup.py", "raise SystemExit('an import runs me')\n")
        code, out = self.just("python::api-check")
        self.assertEqual(code, 0, out)
        self.assertIn("with the packages and modules m\n", out)
        self.assertFalse((self.root / "data.txt").exists())

    def test_a_failed_import_says_so(self) -> None:
        self.write("pkg/__init__.py", '"""Pkg."""\nimport nox\n')
        code, out = self.just("python::api-check")
        self.assertEqual(code, 2, out)
        self.assertIn("smalldocs cannot read the API, for example because an import failed", out)
        self.assertNotIn("a docment: a comment", out)

    def test_a_project_with_no_code_passes(self) -> None:
        (self.root / "m.py").unlink()
        code, out = self.just("python::api-check")
        self.assertEqual(code, 0, out)
        self.assertIn("no package at the top of the project or in src/", out)

    def test_a_project_on_python_3_9_passes_with_a_note_unless_it_asks_for_the_check(self) -> None:
        self.write("pyproject.toml", (self.root / "pyproject.toml").read_text().replace(">=3.11", ">=3.9"))
        self.write(".python-version", "3.9\n")
        code, out = self.just("python::api-check")
        self.assertEqual(code, 0, out)
        self.assertIn("the API is not checked: smalldocs needs Python 3.11 or later, and the project has 3.9", out)
        # The key api of the docs config asks for the check, so it fails.
        self.write("docs/_smalldocs.yml", "project:\n  type: website\napi:\n  packages: [m]\n")
        code, out = self.just("python::api-check")
        self.assertEqual(code, 1, out)
        self.assertIn("smalldocs needs Python 3.11 or later, and the project has 3.9", out)

    def test_the_api_page_of_each_changed_module_goes_to_the_prose_checker(self) -> None:
        self.write(".agents/skills/nossaifd/scripts/check.py", CHECKER)
        self.write("n/__init__.py", TYPED.replace('"""Add A and B."""', '"""Add A and B, basically."""'))
        self.commit()
        # Only m.py changed, so only its page is checked, and it passes.
        self.write("m.py", TYPED + "\n")
        code, out = self.just("python::api-prose-check")
        self.assertEqual(code, 0, out)
        self.assertIn("the API pages of m", out)
        self.assertIn("m.md: 0 hard", out)
        self.assertNotIn("n.md", out)
        # A change to the package n checks its page, and the hard problem fails the check. The pages go to no file of the project.
        self.write("n/__init__.py", (self.root / "n/__init__.py").read_text() + "\n")
        before = self.status()
        code, out = self.just("python::api-prose-check")
        self.assertEqual(code, 1, out)
        self.assertIn("n.md: 1 hard", out)
        self.assertIn("fix each hard problem in the docstring", out)
        self.assertEqual(self.status(), before)

    def test_api_check_runs_the_prose_check_of_the_pages(self) -> None:
        self.write(".agents/skills/nossaifd/scripts/check.py", CHECKER)
        self.write("m.py", TYPED.replace('"""Add A and B."""', '"""Add A and B, basically."""'))
        code, out = self.just("python::api-check")
        self.assertEqual(code, 1, out)
        self.assertIn("api-prose-check: the API pages of m", out)
        self.assertIn("m.md: 1 hard", out)

    def test_with_no_checker_the_api_pages_are_not_checked(self) -> None:
        code, out = self.just("python::api-prose-check")
        self.assertEqual(code, 0, out)
        self.assertIn("no checker of nossaifd", out)

    def status(self) -> str:
        """The output of git status, with the untracked files."""
        return subprocess.run(["git", "status", "--porcelain", "--untracked-files=all"], cwd=self.root,
                              capture_output=True, text=True).stdout


# prose_gate.py of nossaifd, whose base_commit gives the base. JNPROFILE_PROSE_GATE names another copy; NOSSAIFD_GATE is the on-off switch of nossaifd.
GATE = Path(os.environ.get("JNPROFILE_PROSE_GATE", Path.home() / "Projects/nossaifd/.agents/skills/nossaifd/scripts/prose_gate.py"))
HAS_GATE = GATE.is_file() and "def base_commit(" in GATE.read_text()
# A prose_gate.py from before nossaifd #17, with no base_commit.
OLD_GATE = "def ci_set():\n    return True\n"
# A small prose_gate.py with the interface of nossaifd: the merge base of --base, or in CI of origin/GITHUB_BASE_REF.
# With it, the tests of the base run on a machine with no copy of nossaifd.
FAKE_GATE = """import os, subprocess


def ci_set():
    return os.environ.get('CI', '') not in ('', 'false', '0')


def base_commit(root, option):
    ref = option or 'origin/' + os.environ.get('GITHUB_BASE_REF', '')
    found = subprocess.run(['git', '-C', str(root), 'merge-base', ref, 'HEAD'], capture_output=True, text=True)
    if found.returncode:
        return None, f'the base {ref} does not resolve to a commit'
    return found.stdout.strip(), f'the fake base {ref}'
"""
# A prose_gate.py whose base_commit takes other arguments.
WRONG_GATE = "def ci_set():\n    return True\n\n\ndef base_commit(root):\n    return None, 'never'\n"
# A prose_gate.py that fails on import.
BROKEN_GATE = "raise RuntimeError('broken')\n"
BAD = TYPED.replace('"""Add A and B."""', '"""Add A and B, basically."""')
# The variables of CI that the steps read. The tests set them, so the CI of a machine does not change them.
CI_VARIABLES = ("CI", "GITHUB_BASE_REF", "GITHUB_REF", "GITHUB_EVENT_NAME", "GITHUB_EVENT_PATH")


@unittest.skipUnless(TOOLS, "needs just, uv and git")
class ProseBaseTests(ProjectCase):
    """api-prose-check takes the base of check-changed of nossaifd: in CI, or with --base REF."""

    def setUp(self) -> None:
        super().setUp()
        for name in CI_VARIABLES:
            self.env.pop(name, None)
        self.write(".agents/just/python.just", FULL)
        self.write("Justfile", ROOT)
        text = (self.root / "pyproject.toml").read_text()
        self.write("pyproject.toml", text.replace(">=3.9", ">=3.11").replace('name = "app"', 'name = "m"'))
        subprocess.run(["uv", "lock", "--quiet"], cwd=self.root, check=True, env=self.env)
        self.write("m.py", TYPED)
        self.write("tests/test_m.py", TEST)
        self.write(".agents/skills/nossaifd/scripts/check.py", CHECKER)
        if HAS_GATE:
            self.write(".agents/skills/nossaifd/scripts/prose_gate.py", GATE.read_text())
        # main, with origin/main as a fake remote branch, then a branch that adds the package n with a bad docstring.
        self.git("checkout", "-q", "-b", "main")
        self.commit()
        self.git("update-ref", "refs/remotes/origin/main", "HEAD")
        self.git("checkout", "-q", "-b", "feature")
        self.write("n/__init__.py", BAD)
        self.commit()

    def ci(self, **more: str) -> dict:
        """The environment of a pull request on GitHub into main."""
        return {**self.env, "CI": "true", "GITHUB_BASE_REF": "main", "GITHUB_EVENT_NAME": "pull_request", **more}

    @unittest.skipUnless(HAS_GATE, "needs prose_gate.py of nossaifd with base_commit")
    def test_in_ci_a_bad_docstring_of_a_module_changed_since_the_merge_base_fails(self) -> None:
        # The checkout is clean, so the changes since HEAD hold no module.
        code, out = self.just("python::api-prose-check")
        self.assertEqual(code, 0, out)
        self.assertIn("api-prose-check: no code changed since HEAD", out)
        code, out = self.just("python::api-prose-check", env=self.ci())
        self.assertEqual(code, 1, out)
        self.assertIn("the modules changed since the merge base of origin/main and HEAD", out)
        self.assertIn("n.md: 1 hard", out)
        self.assertNotIn("m.md", out)

    @unittest.skipUnless(HAS_GATE, "needs prose_gate.py of nossaifd with base_commit")
    def test_with_base_a_bad_docstring_since_the_base_fails(self) -> None:
        for args in (["--base", "main"], ["--base=main"]):
            code, out = self.just("python::api-prose-check", *args)
            self.assertEqual(code, 1, out)
            self.assertIn("n.md: 1 hard", out)
        # A change in the working tree counts too.
        self.write("m.py", BAD)
        code, out = self.just("python::api-prose-check", "--base", "main")
        self.assertIn("m.md: 1 hard", out)

    @unittest.skipUnless(HAS_GATE, "needs prose_gate.py of nossaifd with base_commit")
    def test_a_base_that_does_not_resolve_fails_with_2(self) -> None:
        code, out = self.just("python::api-prose-check", env=self.ci(GITHUB_BASE_REF="nope"))
        self.assertEqual(code, 2, out)
        self.assertIn("api-prose-check: the base origin/nope does not resolve to a commit", out)
        code, out = self.just("python::api-prose-check", "--base", "nope")
        self.assertEqual(code, 2, out)
        self.assertIn("api-prose-check: the base nope does not resolve to a commit", out)

    @unittest.skipUnless(HAS_GATE, "needs prose_gate.py of nossaifd with base_commit")
    def test_a_run_with_another_base_runs_again(self) -> None:
        env = dict(self.env, JLOG_RUN="run-1")
        code, out = self.just("python::api-prose-check", env=env)
        self.assertEqual(code, 0, out)
        # The same call again in the same run does not run again.
        code, out = self.just("python::api-prose-check", env=env)
        self.assertIn("api-prose-check: it passed before in this run, run-1", out)
        # The changes since HEAD passed, but a call with a base checks other changes, so it runs, and fails.
        code, out = self.just("python::api-prose-check", "--base", "main", env=env)
        self.assertEqual(code, 1, out)
        self.assertNotIn("passed before", out)
        code, out = self.just("python::api-prose-check", env=self.ci(JLOG_RUN="run-1"))
        self.assertEqual(code, 1, out)
        self.assertNotIn("passed before", out)

    def test_an_old_prose_gate_with_no_base_commit_fails_in_ci_and_with_base(self) -> None:
        self.write(".agents/skills/nossaifd/scripts/prose_gate.py", OLD_GATE)
        self.commit()
        for args, env in (([], self.ci()), (["--base", "main"], self.env)):
            code, out = self.just("python::api-prose-check", *args, env=env)
            self.assertEqual(code, 2, out)
            self.assertIn("needs base_commit of .agents/skills/nossaifd/scripts/prose_gate.py", out)
            self.assertIn("Run just install to update the prose role", out)
            self.assertNotIn("no code changed", out)
        # Without CI and without --base, nothing changes.
        code, out = self.just("python::api-prose-check")
        self.assertEqual(code, 0, out)
        self.assertIn("no code changed since HEAD", out)

    def test_no_prose_gate_fails_in_ci(self) -> None:
        (self.root / ".agents/skills/nossaifd/scripts/prose_gate.py").unlink(missing_ok=True)
        self.commit()
        code, out = self.just("python::api-prose-check", env=self.ci())
        self.assertEqual(code, 2, out)
        self.assertIn("needs base_commit", out)

    def test_without_the_prose_role_it_still_passes_in_ci(self) -> None:
        for name in ("check.py", "prose_gate.py"):
            (self.root / ".agents/skills/nossaifd/scripts" / name).unlink(missing_ok=True)
        code, out = self.just("python::api-prose-check", "--base", "main", env=self.ci())
        self.assertEqual(code, 0, out)
        self.assertIn("no checker of nossaifd", out)

    def test_a_fake_gate_gives_the_base_in_ci_and_with_base(self) -> None:
        self.write(".agents/skills/nossaifd/scripts/prose_gate.py", FAKE_GATE)
        self.commit()
        for args, env in (([], self.ci()), (["--base", "main"], self.env)):
            code, out = self.just("python::api-prose-check", *args, env=env)
            self.assertEqual(code, 1, out)
            self.assertIn("the modules changed since the fake base", out)
            self.assertIn("n.md: 1 hard", out)
        code, out = self.just("python::api-prose-check", env=self.ci(GITHUB_BASE_REF="nope"))
        self.assertEqual(code, 2, out)
        self.assertIn("api-prose-check: the base origin/nope does not resolve to a commit", out)

    def test_v_does_nothing_and_the_last_base_counts(self) -> None:
        self.write(".agents/skills/nossaifd/scripts/prose_gate.py", FAKE_GATE)
        self.commit()
        for args in (["-v", "--base", "main"], ["--base", "nope", "--base=main"]):
            code, out = self.just("python::api-prose-check", *args)
            self.assertEqual(code, 1, (args, out))
            self.assertIn("the fake base main", out)
        code, out = self.just("python::api-prose-check", "-v")
        self.assertEqual(code, 0, out)
        self.assertIn("no code changed since HEAD", out)

    def test_a_broken_prose_gate_changes_nothing_without_ci_and_without_base(self) -> None:
        self.write(".agents/skills/nossaifd/scripts/prose_gate.py", BROKEN_GATE)
        self.commit()
        code, out = self.just("python::api-prose-check")
        self.assertEqual(code, 0, out)
        self.assertIn("no code changed since HEAD", out)
        code, out = self.just("python::api-prose-check", env=self.ci())
        self.assertEqual(code, 2, out)
        self.assertIn("cannot be loaded", out)

    def test_a_base_commit_that_fails_gives_2(self) -> None:
        self.write(".agents/skills/nossaifd/scripts/prose_gate.py", WRONG_GATE)
        self.commit()
        code, out = self.just("python::api-prose-check", env=self.ci())
        self.assertEqual(code, 2, out)
        self.assertIn("api-prose-check: base_commit of .agents/skills/nossaifd/scripts/prose_gate.py failed", out)
        self.assertNotIn("Traceback", out)

    def test_a_run_on_another_head_with_the_same_tree_runs_again(self) -> None:
        env = dict(self.env, JLOG_RUN="run-1")
        code, out = self.just("python::api-prose-check", env=env)
        self.assertEqual(code, 0, out)
        code, out = self.just("python::api-prose-check", env=env)
        self.assertIn("passed before", out)
        self.git("commit", "-q", "--allow-empty", "-m", "empty")
        code, out = self.just("python::api-prose-check", env=env)
        self.assertEqual(code, 0, out)
        self.assertNotIn("passed before", out)

    def test_an_unknown_argument_fails_with_2(self) -> None:
        for args in (["--bse", "main"], ["--base"], ["--base="], ["main"]):
            code, out = self.just("python::api-prose-check", *args)
            self.assertEqual(code, 2, (args, out))
            self.assertIn("api-prose-check:", out)


if __name__ == "__main__":
    unittest.main()
