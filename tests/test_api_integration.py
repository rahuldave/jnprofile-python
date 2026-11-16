"""Run the recipes of the integration and api tools with real just, uv, git, pytest and smalldocs."""

import json
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
STEPS = ["fmt-check", "lint", "typecheck", "test", "coverage-check", "integration", "docstring-check", "docs-check",
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
        code, out = self.just("python::coverage-check", env=env)
        self.assertEqual(code, 0, out)
        self.assertIn("no report of the integration tests of this run and this tree, so they run now", out)
        # The step integration of the same run does not run the tests again.
        code, out = self.just("python::integration", env=env)
        self.assertEqual(code, 0, out)
        self.assertIn("integration: it passed before in this run, run-1, on this tree", out)
        self.assertNotIn("test_flow.py", out)

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

    def test_docstring_check_runs_api_check_when_docs_check_does_not(self) -> None:
        self.write("m.py", TYPED + UNTYPED)
        code, out = self.just("python::docstring-check")
        self.assertEqual(code, 1, out)
        self.assertIn("api-check: the step docs-check does not run it, so it runs now", out)
        self.assertIn("m:sub(a): no docment", out)

    def test_with_the_docs_role_docs_check_runs_api_check_and_docstring_check_does_not(self) -> None:
        self.write("Justfile", ROOT + DOCS_ROLE)
        self.write("m.py", TYPED + UNTYPED)
        code, out = self.just("python::docstring-check")
        self.assertEqual(code, 0, out)
        self.assertIn("api-check: the step docs-check runs it", out)
        code, out = self.just("docs-check")
        self.assertEqual(code, 1, out)
        self.assertIn("m:sub(a): no docment", out)

    def test_api_check_runs_once_in_a_run(self) -> None:
        env = dict(self.env, JLOG_RUN="run-1")
        code, out = self.just("python::api-check", env=env)
        self.assertEqual(code, 0, out)
        code, out = self.just("api-check", env=env)
        self.assertEqual(code, 0, out)
        self.assertIn("api: it passed before in this run, run-1, on this tree", out)
        # A changed tree runs it again, and fails it.
        self.write("m.py", TYPED + UNTYPED)
        code, out = self.just("api-check", env=env)
        self.assertEqual(code, 1, out)

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

    def test_api_check_runs_the_prose_check_of_the_pages_when_prose_check_does_not(self) -> None:
        self.write(".agents/skills/nossaifd/scripts/check.py", CHECKER)
        self.write("m.py", TYPED.replace('"""Add A and B."""', '"""Add A and B, basically."""'))
        code, out = self.just("python::api-check")
        self.assertEqual(code, 1, out)
        self.assertIn("api-prose-check: the step prose-check does not run it, so it runs now", out)
        self.assertIn("m.md: 1 hard", out)

    def test_with_no_checker_the_api_pages_are_not_checked(self) -> None:
        code, out = self.just("python::api-prose-check")
        self.assertEqual(code, 0, out)
        self.assertIn("no checker of nossaifd", out)

    def status(self) -> str:
        """The output of git status, with the untracked files."""
        return subprocess.run(["git", "status", "--porcelain", "--untracked-files=all"], cwd=self.root,
                              capture_output=True, text=True).stdout


if __name__ == "__main__":
    unittest.main()
